#!/usr/bin/env python3
"""Public product tour, SSR, responsive geometry and conversion paths.

API responses are isolated fixtures here. Docker E2E exercises real persistence.
"""
import json
import os
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
from visual_qa_experience import navigate
BASE=os.getenv('FORGEGOV_QA_BASE_URL','http://127.0.0.1:3100').rstrip('/')
OUT=Path(os.getenv('FORGEGOV_QA_ARTIFACT_DIR','artifacts/visual-qa'))/'public'
OUT.mkdir(parents=True,exist_ok=True)
html=urlopen(BASE).read().decode()
for text in ['Find the opportunity.','Bring the pursuit together.','$2,000','Different companies.','canonical','og:image']:
    assert text in html, f'SSR content missing: {text}'
results=[]
with sync_playwright() as p:
    names=os.getenv('FORGEGOV_QA_BROWSERS','chromium,firefox,webkit').split(',')
    for name in names:
        options={}
        if name=='chromium' and os.getenv('FORGEGOV_QA_CHROMIUM_PATH'):
            options={'executable_path':os.environ['FORGEGOV_QA_CHROMIUM_PATH'],'args':['--no-sandbox','--disable-dev-shm-usage']}
        browser=getattr(p,name).launch(**options)
        for w,h in [(320,800),(390,844),(768,1024),(1024,768),(1440,1000),(1920,1080)]:
            context=browser.new_context(viewport={'width':w,'height':h},color_scheme='dark' if w==1024 else 'light')
            page=context.new_page(); errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def api(route):
                path=route.request.url
                if '/registration-config/' in path:
                    payload={'mode':'private_beta','public_registration':False};status=200
                elif '/csrf/' in path:payload={'csrfToken':'isolated-public-qa'};status=200
                elif '/public/inquiries/' in path:payload={'status':'received','reference':'isolated-qa-reference'};status=201
                else:payload={'detail':'Not authenticated'};status=401
                route.fulfill(status=status,content_type='application/json',body=json.dumps(payload))
            page.route('**/api/**',api)
            navigate(page, BASE,wait_until='networkidle')
            expect(page.get_by_role('heading',level=1)).to_contain_text('Find the opportunity.')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'{name} {w} overflow'
            assert page.locator('#tour-panel img').evaluate('(i)=>i.complete&&i.naturalWidth>0'), 'tour image missing'
            for tab in ['Discover','Qualify','Capture','Project Rooms','ForgeAI']:
                page.get_by_role('tab',name=tab,exact=True).click()
                expect(page.get_by_role('tab',name=tab,exact=True)).to_have_attribute('aria-selected','true')
            page.get_by_role('tab',name='ForgeAI',exact=True).press('Home')
            expect(page.get_by_role('tab',name='Discover',exact=True)).to_be_focused()
            page.get_by_role('button',name='Enlarge screenshot').click()
            expect(page.get_by_role('dialog')).to_be_visible()
            page.keyboard.press('Escape');expect(page.get_by_role('dialog')).not_to_be_visible()
            page.get_by_role('tab',name='Capture',exact=True).click()
            page.get_by_role('link',name='See the $2,000/year plan',exact=True).click()
            assert page.url.endswith('#pricing')
            page.evaluate('scrollTo(0,0)')
            if w in (390,768,1440):page.screenshot(path=str(OUT/f'{name}-{w}.png'),full_page=True)
            page.get_by_role('link',name='Request access',exact=True).first.click()
            page.get_by_label('Your name',exact=True).fill('Isolated QA')
            page.get_by_label('Work email',exact=True).fill('qa@example.invalid')
            page.get_by_label('Company',exact=True).fill('Isolated QA Company')
            page.get_by_role('checkbox').check()
            page.get_by_role('button',name='Submit access request',exact=True).click()
            expect(page.get_by_role('heading',name='Request received.')).to_be_visible()
            navigate(page, BASE+'/register',wait_until='networkidle')
            page.get_by_role('link',name='Submit an access request').click()
            expect(page.get_by_role('heading',name='Bring your team into ForgeGov.')).to_be_visible()
            navigate(page, BASE+'/support',wait_until='networkidle')
            expect(page.get_by_role('heading',name='How can we help?')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            for path,heading in [('/sign-in','Sign in'),('/terms','ForgeGov Terms of Use'),('/privacy','ForgeGov Privacy Notice')]:
                navigate(page, BASE+path,wait_until='networkidle')
                expect(page.get_by_role('heading',name=heading,exact=False).first).to_be_visible()
            # Public registration follows the live configuration without bypassing the gate.
            page.unroute('**/api/**', api)
            def public_api(route):
                if '/registration-config/' in route.request.url:
                    route.fulfill(status=200,content_type='application/json',body=json.dumps({'mode':'public','public_registration':True}))
                else:
                    api(route)
            page.route('**/api/**',public_api)
            navigate(page, BASE,wait_until='networkidle')
            account=page.get_by_role('link',name='Create your account',exact=True).first
            try:
                expect(account).to_have_attribute('href','/register')
            except Exception:
                print('Registration-state diagnostics:',page.inner_text('body')[:900],flush=True)
                page.screenshot(path=str(OUT/'registration-state-failure.png'),full_page=True)
                raise
            account.click()
            expect(page.get_by_role('heading',name='Create your ForgeGov account')).to_be_visible()
            assert not errors,errors
            results.append({'browser':name,'width':w,'passed':True})
            context.close()
        browser.close()
(OUT/'report.json').write_text(json.dumps({'ssr':True,'cases':results},indent=2))
print(f'{len(results)} public browser cases passed; SSR, screenshots, CTAs, registration gate, modal, keyboard, forms, and overflow.')
