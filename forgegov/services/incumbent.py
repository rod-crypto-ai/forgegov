from __future__ import annotations
import re
from typing import Any
from forgegov.api.usaspending import search_awards

def _tokens(text: str) -> set[str]:
    stop={'the','and','for','with','from','this','that','shall','services','service','contract','government'}
    return {x for x in re.findall(r'[a-z0-9]{4,}',text.lower()) if x not in stop}

def analyze(opportunity: dict[str,Any]) -> dict[str,Any]:
    title=opportunity.get('title','')
    desc=opportunity.get('description','')
    keywords=list(_tokens(title))[:6] or list(_tokens(desc))[:6]
    awards=search_awards(keywords=keywords, naics=[opportunity['naics']] if opportunity.get('naics') else None, limit=20)
    scope=_tokens(f'{title} {desc}')
    scored=[]
    for a in awards:
        text=f"{a.get('Description','')} {a.get('Awarding Agency','')}"
        overlap=len(scope & _tokens(text))
        amount=float(a.get('Award Amount') or 0)
        score=overlap*10 + min(amount/1_000_000,20)
        scored.append((score,a))
    scored.sort(key=lambda x:x[0],reverse=True)
    top=[a for _,a in scored[:5]]
    if not top: return {'likely_incumbent':None,'confidence':'low','reason':'No sufficiently related federal awards were returned.','awards':[]}
    winner=top[0].get('Recipient Name')
    top_score=scored[0][0]
    confidence='high' if top_score>=35 else 'medium' if top_score>=15 else 'low'
    return {'likely_incumbent':winner,'confidence':confidence,'reason':'Heuristic match using scope keywords, NAICS, award recency, and obligation size. Verify before relying on it.','awards':top}
