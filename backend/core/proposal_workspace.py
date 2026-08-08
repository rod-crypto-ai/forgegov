from __future__ import annotations

from typing import Any
from django.utils import timezone

from .document_intelligence import capture_readiness_summary
from .models import OpportunityDocument, OpportunityWorkspace, PipelineItem, Task


def _unique(values):
    seen=[]
    for value in values:
        value=str(value or '').strip()
        if value and value.lower() not in {v.lower() for v in seen}:
            seen.append(value)
    return seen


def build_proposal_workspace(*, organization, opportunity) -> dict[str, Any]:
    documents=list(OpportunityDocument.objects.filter(opportunity=opportunity).order_by('-updated_at'))
    ready=[doc for doc in documents if doc.status == OpportunityDocument.Status.READY]
    readiness=capture_readiness_summary(documents)
    structured=[((doc.metadata or {}).get('structured_intelligence') or {}) for doc in ready]
    workspace=OpportunityWorkspace.objects.filter(organization=organization, opportunity=opportunity).first()
    pipeline=PipelineItem.objects.filter(organization=organization, opportunity=opportunity).order_by('-updated_at').first()
    tasks=list(Task.objects.filter(organization=organization, pipeline_item=pipeline).select_related('assigned_to').order_by('completed','due_at','created_at')) if pipeline else []

    requirements=[]
    if workspace:
        for index,row in enumerate(workspace.compliance_items or []):
            if not isinstance(row,dict): continue
            requirements.append({
                'id': str(row.get('id') or f'workspace-{index+1}'),
                'requirement': str(row.get('label') or 'Untitled requirement'),
                'source': str(row.get('source') or 'Capture workspace'),
                'status': 'complete' if row.get('complete') else 'open',
                'owner': '',
                'evidence': 'User-maintained compliance item',
                'source_kind': 'workspace',
            })
    checks=[
        ('section-l','Section L / proposal instructions','Indexed solicitation files', any(r.get('section_l_detected') for r in structured)),
        ('section-m','Section M / evaluation factors','Indexed solicitation files', any(r.get('section_m_detected') for r in structured)),
        ('clins','CLIN / SUBCLIN / ELIN structure','Indexed solicitation files', any(r.get('clins') for r in structured)),
        ('clauses','FAR / DFARS clause review','Indexed solicitation files', any(r.get('clauses') for r in structured)),
        ('security','Security / certification requirements','Indexed solicitation files', any((r.get('cmmc') or r.get('certifications')) for r in structured)),
        ('deliverables','Deliverables / submission artifacts','Indexed solicitation files', any(r.get('deliverables') for r in structured)),
    ]
    existing={r['id'] for r in requirements}
    for rid,label,source,found in checks:
        if rid not in existing:
            requirements.append({'id':rid,'requirement':label,'source':source,'status':'evidence_found' if found else 'needs_review','owner':'','evidence':'Structured evidence detected' if found else 'Evidence not yet detected','source_kind':'document_intelligence'})

    section_l=any(r.get('section_l_detected') for r in structured)
    section_m=any(r.get('section_m_detected') for r in structured)
    outline=[
        {'title':'Executive / cover volume','basis':'Proposal workspace standard','status':'plan'},
        {'title':'Technical approach','basis':'Section L evidence' if section_l else 'Section L not yet detected','status':'ready_to_structure' if section_l else 'needs_evidence'},
        {'title':'Management / staffing approach','basis':'Labor-category and deliverable evidence','status':'ready_to_structure' if any(r.get('labor_categories') for r in structured) else 'needs_evidence'},
        {'title':'Past performance','basis':'Common evaluation volume; verify Section L/M','status':'verify'},
        {'title':'Price / cost volume','basis':'CLIN structure' if any(r.get('clins') for r in structured) else 'CLIN structure not yet detected','status':'ready_to_structure' if any(r.get('clins') for r in structured) else 'needs_evidence'},
    ]

    deadline=opportunity.response_deadline
    reviews=[]
    if deadline:
        for name,days in [('Pink Team',21),('Red Team',10),('Gold Team',4),('Final submission check',1)]:
            date=deadline-timezone.timedelta(days=days)
            reviews.append({'name':name,'target_at':date.isoformat(),'status':'planned' if date>timezone.now() else 'overdue'})

    task_rows=[{'id':t.id,'title':t.title,'completed':t.completed,'due_at':t.due_at.isoformat() if t.due_at else None,'assigned_to':(t.assigned_to.get_full_name() or t.assigned_to.username) if t.assigned_to else ''} for t in tasks]
    completed=sum(1 for r in requirements if r['status'] in {'complete','evidence_found'})
    score=round((completed/max(1,len(requirements)))*100)
    alerts=[]
    if not section_l: alerts.append('Section L / proposal instructions have not been detected in indexed documents.')
    if not section_m: alerts.append('Section M / evaluation factors have not been detected in indexed documents.')
    if not ready: alerts.append('No solicitation document is currently indexed and ready for proposal evidence extraction.')
    if deadline and deadline <= timezone.now(): alerts.append('The stored response deadline has passed; verify the current SAM.gov notice before proposal work continues.')

    return {
        'generated_at': timezone.now().isoformat(),
        'opportunity': {'source_id':opportunity.source_id,'title':opportunity.title,'deadline':deadline.isoformat() if deadline else None},
        'readiness': {'score':score,'document_score':readiness.get('score',0),'completed_requirements':completed,'total_requirements':len(requirements)},
        'compliance_matrix':requirements,
        'proposal_outline':outline,
        'review_plan':reviews,
        'submission_checklist':[
            {'label':'All required volumes identified','complete':section_l},
            {'label':'Evaluation factors mapped to response','complete':section_m},
            {'label':'CLIN structure reviewed','complete':any(r.get('clins') for r in structured)},
            {'label':'All workspace compliance items complete','complete':bool(workspace and workspace.compliance_items) and all(bool(r.get('complete')) for r in workspace.compliance_items if isinstance(r,dict))},
            {'label':'Final submission method verified','complete':False},
        ],
        'proposal_tasks':task_rows,
        'alerts':alerts,
        'evidence_summary':{'ready_documents':len(ready),'clins':len(_unique(v for r in structured for v in (r.get('clins') or []))),'clauses':len(_unique(v for r in structured for v in (r.get('clauses') or []))),'deliverables':len(_unique(v for r in structured for v in (r.get('deliverables') or [])))},
        'warning':'Proposal planning is decision support. Verify final instructions, amendments, evaluation criteria, and submission requirements against the current official solicitation.',
    }
