from __future__ import annotations
import os, requests
from typing import Any

BASE='https://api.sam.gov/opportunities/v2/search'

def _text(v: Any) -> str:
    if v is None: return ''
    if isinstance(v,str): return v
    if isinstance(v,dict): return ', '.join(str(x) for x in v.values() if x)
    return str(v)

def normalize(raw: dict[str,Any]) -> dict[str,Any]:
    office=raw.get('officeAddress') or {}
    pop=raw.get('placeOfPerformance') or {}
    notice_id=str(raw.get('noticeId') or raw.get('noticeID') or raw.get('solicitationNumber') or '')
    return {
      'notice_id': notice_id,
      'title': raw.get('title') or 'Untitled opportunity',
      'solicitation_number': raw.get('solicitationNumber') or '',
      'agency': raw.get('fullParentPathName') or raw.get('department') or raw.get('organizationName') or '',
      'office': office.get('city') or raw.get('office') or '',
      'naics': str(raw.get('naicsCode') or ''),
      'set_aside': raw.get('typeOfSetAsideDescription') or raw.get('typeOfSetAside') or '',
      'posted_date': raw.get('postedDate') or '',
      'response_deadline': raw.get('responseDeadLine') or raw.get('responseDeadline') or '',
      'place_of_performance': _text(pop),
      'description': raw.get('description') or raw.get('additionalInfoLink') or '',
      'url': raw.get('uiLink') or f'https://sam.gov/opp/{notice_id}/view',
      'raw': raw,
    }

def search(*, posted_from: str, posted_to: str, keyword: str='', naics: str='', set_aside: str='', limit: int=100) -> list[dict[str,Any]]:
    key=os.getenv('SAM_API_KEY')
    if not key: raise RuntimeError('SAM_API_KEY is missing. Add it to .env; never place it in source code.')
    params={'api_key':key,'postedFrom':posted_from,'postedTo':posted_to,'limit':min(limit,1000),'offset':0}
    if keyword: params['q']=keyword
    if naics: params['ncode']=naics
    if set_aside: params['typeOfSetAside']=set_aside
    r=requests.get(BASE,params=params,timeout=35)
    r.raise_for_status()
    data=r.json()
    items=data.get('opportunitiesData') or data.get('data') or []
    return [normalize(x) for x in items if (x.get('noticeId') or x.get('solicitationNumber'))]
