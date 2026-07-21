from __future__ import annotations
import requests
from typing import Any
BASE='https://api.usaspending.gov/api/v2'

def search_awards(*, keywords: list[str], agencies: list[str]|None=None, naics: list[str]|None=None, start_date: str='2021-01-01', end_date: str='2026-12-31', limit: int=25) -> list[dict[str,Any]]:
    filters: dict[str,Any]={'time_period':[{'start_date':start_date,'end_date':end_date}], 'award_type_codes':['A','B','C','D']}
    if keywords: filters['keywords']=keywords
    if agencies: filters['agencies']=[{'type':'awarding','tier':'toptier','name':a} for a in agencies if a]
    if naics: filters['naics_codes']=naics
    payload={'filters':filters,'fields':['Award ID','Recipient Name','Award Amount','Description','Start Date','End Date','Awarding Agency','NAICS Code'],'page':1,'limit':limit,'subawards':False}
    r=requests.post(f'{BASE}/search/spending_by_award/',json=payload,timeout=40)
    r.raise_for_status()
    return r.json().get('results',[])
