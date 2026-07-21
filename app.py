from __future__ import annotations
import json, os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from forgegov.api.sam import search
from forgegov.db.database import init_db,upsert_opportunity,add_to_pipeline,pipeline_rows,update_pipeline,save_search,saved_searches
from forgegov.services.incumbent import analyze

load_dotenv(); init_db()
st.set_page_config(page_title='ForgeGov',page_icon='⚒️',layout='wide')
st.markdown('''<style>.block-container{padding-top:1.2rem}.fg-card{border:1px solid #283241;border-radius:14px;padding:16px;background:#111827}</style>''',unsafe_allow_html=True)

st.sidebar.title('⚒️ ForgeGov')
page=st.sidebar.radio('Workspace',['Executive Dashboard','Opportunity Discovery','Capture Pipeline','Saved Searches','Market Intelligence'])
st.sidebar.caption('Federal intelligence and capture management. Real data only.')

if page=='Executive Dashboard':
    st.title('Executive Dashboard')
    rows=pipeline_rows(); df=pd.DataFrame(rows)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Active pursuits',len(rows))
    c2.metric('Pipeline value',f"${df['estimated_value'].sum():,.0f}" if not df.empty else '$0')
    weighted=(df['estimated_value']*df['probability']/100).sum() if not df.empty else 0
    c3.metric('Weighted value',f'${weighted:,.0f}')
    deadlines=0
    if not df.empty and 'response_deadline' in df:
        deadlines=sum(pd.to_datetime(df.response_deadline,errors='coerce').between(pd.Timestamp.today(),pd.Timestamp.today()+pd.Timedelta(days=14)))
    c4.metric('Deadlines ≤14 days',int(deadlines))
    st.subheader('Pipeline by stage')
    if df.empty: st.info('No pursuits yet. Search live opportunities and add qualified records to the pipeline.')
    else:
        st.bar_chart(df.groupby('stage').size())
        st.dataframe(df[['title','agency','stage','probability','estimated_value','response_deadline']],use_container_width=True,hide_index=True)

elif page=='Opportunity Discovery':
    st.title('Opportunity Discovery')
    with st.form('search'):
        c1,c2,c3=st.columns(3)
        keyword=c1.text_input('Keywords',placeholder='vehicle maintenance, logistics, construction')
        naics=c2.text_input('NAICS',placeholder='811111')
        set_aside=c3.text_input('Set-aside code',placeholder='SBA, SDVOSBC, 8A')
        c4,c5=st.columns(2)
        start=c4.date_input('Posted from',date.today()-timedelta(days=30))
        end=c5.date_input('Posted to',date.today())
        submitted=st.form_submit_button('Search SAM.gov',type='primary')
    if submitted:
        try:
            with st.spinner('Pulling live SAM.gov opportunities...'):
                results=search(posted_from=start.strftime('%m/%d/%Y'),posted_to=end.strftime('%m/%d/%Y'),keyword=keyword,naics=naics,set_aside=set_aside)
                for o in results: upsert_opportunity(o)
                st.session_state.results=results
            st.success(f'{len(results)} live opportunities loaded and normalized.')
        except Exception as e: st.error(str(e))
    results=st.session_state.get('results',[])
    if results:
        export=pd.DataFrame([{k:o.get(k) for k in ['notice_id','title','solicitation_number','agency','naics','set_aside','posted_date','response_deadline','url']} for o in results])
        st.download_button('Export results CSV',export.to_csv(index=False),'forgegov_opportunities.csv','text/csv')
        for i,o in enumerate(results):
            with st.expander(f"{o['title']} — {o.get('solicitation_number','')}"):
                st.write(f"**Agency:** {o.get('agency') or 'Not provided'}")
                st.write(f"**NAICS:** {o.get('naics') or '—'}  |  **Set-aside:** {o.get('set_aside') or '—'}")
                st.write(f"**Deadline:** {o.get('response_deadline') or '—'}")
                st.write(o.get('description') or 'No description returned in search payload.')
                b1,b2,b3=st.columns(3)
                if b1.button('Add to pipeline',key=f'add{i}'):
                    add_to_pipeline(o['notice_id']); st.success('Added to capture pipeline.')
                if b2.button('Analyze incumbent',key=f'inc{i}'):
                    with st.spinner('Matching related USASpending awards...'):
                        try: st.session_state[f'inc_{o["notice_id"]}']=analyze(o)
                        except Exception as e: st.error(str(e))
                b3.link_button('Open SAM.gov',o['url'])
                inc=st.session_state.get(f'inc_{o["notice_id"]}')
                if inc:
                    st.markdown(f"### Likely incumbent: {inc.get('likely_incumbent') or 'Not identified'}")
                    st.write(f"Confidence: **{inc['confidence']}** — {inc['reason']}")
                    if inc['awards']: st.dataframe(pd.DataFrame(inc['awards']),use_container_width=True,hide_index=True)
        with st.form('save-search'):
            name=st.text_input('Saved search name')
            alerts=st.checkbox('Enable alert flag')
            if st.form_submit_button('Save this search') and name:
                save_search(name,{'keyword':keyword,'naics':naics,'set_aside':set_aside,'posted_from':str(start),'posted_to':str(end)},alerts); st.success('Saved.')

elif page=='Capture Pipeline':
    st.title('Capture Pipeline')
    rows=pipeline_rows()
    if not rows: st.info('Pipeline is empty. Add opportunities from Opportunity Discovery.')
    stages=['New','Researching','Qualified','Bid Prep','Submitted','Won','Lost','Teamed']
    for r in rows:
        with st.expander(f"[{r['stage']}] {r['title']}"):
            c1,c2,c3=st.columns(3)
            stage=c1.selectbox('Stage',stages,index=stages.index(r['stage']) if r['stage'] in stages else 0,key=f's{r["id"]}')
            owner=c2.text_input('Owner',r.get('owner') or '',key=f'o{r["id"]}')
            probability=c3.slider('Win probability',0,100,int(r.get('probability') or 0),5,key=f'p{r["id"]}')
            c4,c5=st.columns(2)
            value=c4.number_input('Estimated value',min_value=0.0,value=float(r.get('estimated_value') or 0),step=1000.0,key=f'v{r["id"]}')
            due=c5.text_input('Internal due date',r.get('due_date') or '',key=f'd{r["id"]}')
            notes=st.text_area('Capture notes',r.get('notes') or '',key=f'n{r["id"]}')
            if st.button('Save pursuit',key=f'save{r["id"]}',type='primary'):
                update_pipeline(r['id'],stage=stage,owner=owner,probability=probability,estimated_value=value,due_date=due,notes=notes); st.success('Pursuit updated.'); st.rerun()
            st.link_button('Open source notice',r['url'])

elif page=='Saved Searches':
    st.title('Saved Searches & Alerts')
    searches=saved_searches()
    if not searches: st.info('No saved searches yet.')
    for s in searches:
        st.markdown(f"### {s['name']}")
        st.json(s['query'])
        st.caption('Alert enabled' if s['alerts_enabled'] else 'Alert disabled')

else:
    st.title('Market Intelligence')
    st.write('Search historical federal awards from USASpending without a paid data subscription.')
    from forgegov.api.usaspending import search_awards
    with st.form('awards'):
        q=st.text_input('Scope keywords',placeholder='heavy equipment maintenance')
        n=st.text_input('NAICS filter')
        go=st.form_submit_button('Search awards',type='primary')
    if go:
        try:
            awards=search_awards(keywords=[x for x in q.split() if x],naics=[n] if n else None,limit=50)
            if awards:
                df=pd.DataFrame(awards); st.dataframe(df,use_container_width=True,hide_index=True)
                st.download_button('Export awards CSV',df.to_csv(index=False),'forgegov_awards.csv','text/csv')
            else: st.info('No matching awards returned.')
        except Exception as e: st.error(str(e))
