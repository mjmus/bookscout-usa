#!/usr/bin/env python3
"""BookScout USA hourly discovery, official-page change monitoring & alerts.

Only public feeds and robots-allowed organizer pages. A headline is not a verified sale.
Every check records last-attempt and retains last-success for transparency.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import urlopen, Request
from monitor_core import (get,utcnow,readjson,savejson,parsed_feed,normalize_lead,
                          page_fingerprint,notify_discord,clean)

ROOT=Path(__file__).resolve().parents[1]
SEED=readjson(ROOT/'data-seed.json',[])
FEEDS=ROOT/'config/feeds.json'; PAGES=ROOT/'config/watch_pages.json'; OUTPUT=ROOT/'web/data/live.json'

def is_isodate(value):
    return bool(re.fullmatch(r'20\d\d-\d\d-\d\d',str(value or '')[:10]))

def parse_events_from_jsonld(raw,page,when):
    """Only official structured Event data, not speculative text-date regex."""
    page_text=raw.decode('utf8','replace')
    scripts=re.findall(r'<script\b[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',page_text,re.I|re.S)
    events=[]
    def objs(v):
        if isinstance(v,list):
            for item in v: yield from objs(item)
        elif isinstance(v,dict):
            if '@graph' in v: yield from objs(v['@graph'])
            yield v
    for script in scripts[:30]:
        try: doc=json.loads(script.strip())
        except (ValueError,TypeError): continue
        for obj in objs(doc):
            ty=obj.get('@type',[])
            if isinstance(ty,str): ty=[ty]
            if not any('event' in str(x).lower() for x in ty): continue
            title=clean(obj.get('name',''),180)
            # Only relevant if event itself has book-sale text, not any calendar event.
            if not re.search(r'book\s*sale|used books?|library sale|book fair|book liquidation|books for sale',title,re.I): continue
            start=str(obj.get('startDate',''))[:10]; end=str(obj.get('endDate') or start)[:10]
            if not is_isodate(start) or not is_isodate(end): continue
            today=when[:10]
            if end<today or start>str(int(today[:4])+2)+'-01-01': continue
            loc=obj.get('location',{})
            if isinstance(loc,list):loc=next((x for x in loc if isinstance(x,dict)),{})
            if not isinstance(loc,dict):loc={}
            adr=loc.get('address',{})
            if isinstance(adr,str):adr={'streetAddress':adr}
            if not isinstance(adr,dict):adr={}
            geo=loc.get('geo',{}) if isinstance(loc.get('geo',{}),dict) else {}
            try:
                lat=float(geo['latitude']);lon=float(geo['longitude'])
                if not(-90<=lat<=90 and -180<=lon<=180):lat=lon=None
            except (ValueError,KeyError,TypeError):lat=lon=None
            st=str(adr.get('addressRegion') or page.get('state','US')).upper()
            if len(st)>2:st=page.get('state','US')
            url=obj.get('url')
            if not isinstance(url,str) or not url.startswith('https://'):url=page['url']
            event_id='evt_'+hashlib.sha256((page['url']+'|'+title+'|'+start).encode()).hexdigest()[:18]
            events.append(dict(id=event_id,title=title,kind='Sale',city=str(adr.get('addressLocality') or ''),state=st,lat=lat,lon=lon,start=start,end=end,price='Not reported',qty=None,shipping='unknown',addr=clean(adr.get('streetAddress') or '',150),url=url,origin='official JSON-LD event on monitored page',confidence='Structured organizer listing; verify details',source_id=page['id'],found_at=when,details=clean(obj.get('description') or '',350),repeat='dated',screening='unknown',scanners='unknown'))
    return events

def checked_feed(src,when,fetch):
    try:
        data=fetch(src['url']);rows=parsed_feed(data);leads=[]
        for row in rows:
            v=normalize_lead(row,src,when)
            if v:
                v['category']=src.get('category','sales')
                v['location_confidence']='State or national search region only; not verified article location'
                leads.append(v)
        return dict(kind='feed',source=src,leads=leads,ok=True)
    except Exception as e:
        return dict(kind='feed',source=src,ok=False,error=f'{type(e).__name__}: {str(e)[:160]}')


# Extract first-party book-sale/surplus *links*, not undocumented sale dates.
# A link is a discovery candidate; the owner must verify what inventory exists.
LINK_TOPIC = re.compile(
    r'\b(?:book\s*(?:sales?|fairs?|shops?|stores?|auctions?|lots?|liquidations?)|'
    r'booksale|used\s*books?|friends\s+of\s+the\s+library|'
    r'library\s+(?:sales?|surplus|withdrawals?|deaccessions?)|'
    r'(?:school|university|government|public)\s+surplus|'
    r'surplus\s+(?:sales?|auctions?|books?)|'
    r'(?:deaccessioned|withdrawn|weeded|obsolete)\s+(?:books?|collections?|materials?|curriculum)|'
    r'gaylords?|pallets?\s+of\s+books?|book\s*(?:pallets?|gaylords?|truckloads?)|'
    r'wholesale\s+(?:used\s+)?books?|(?:unsorted|unscanned|raw)\s+(?:used\s+)?books?)\b',re.I)
BAD_LINK = re.compile(r'\.(?:jpg|jpeg|png|gif|svg|webp|pdf|zip|mp4|woff|ico)(?:$|[?#])', re.I)
OLD_YEAR = re.compile(r'\b(?:201[0-9]|202[0-5])\b')

class SourceLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = None
        self.found = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript','template'):
            self.skip += 1
        if tag == 'a' and not self.skip:
            attrs = dict(attrs)
            href = attrs.get('href') or ''
            if href:
                self.active = {'href':href, 'text':[], 'title':attrs.get('title','')}
    def handle_data(self, data):
        if self.active is not None and not self.skip:
            self.active['text'].append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.active['text'] = clean(' '.join(self.active['text']),220)
            self.found.append(self.active)
            self.active = None
        if tag in ('script','style','noscript','template') and self.skip:
            self.skip -= 1

def parse_official_links(raw, source, when):
    parser=SourceLinkParser()
    parser.feed(raw.decode('utf8','replace'))
    host=urlparse(source['url']).hostname or ''
    found={}
    for item in parser.found:
        target=urldefrag(urljoin(source['url'],item['href']))[0]
        parsed=urlparse(target)
        if parsed.scheme!='https' or parsed.hostname!=host or BAD_LINK.search(target):continue
        name=(item['text'] or item['title']).strip()
        # No generic unlabeled navigation; no links explicitly advertising past years.
        if not name or len(name)<6 or OLD_YEAR.search(name) or OLD_YEAR.search(parsed.path):continue
        if not LINK_TOPIC.search(name+' '+parsed.path.replace('-',' ')):continue
        target=target.rstrip('/')
        if target.rstrip('/')==source['url'].rstrip('/'):continue
        key='org_'+hashlib.sha256((source['id']+'|'+target).encode()).hexdigest()[:19]
        found[key]=dict(id=key,title=name[:180],summary='A relevant link appeared on the monitored official site. Dates, quantity, condition and availability have not been verified.',url=target,source_id=source['id'],source_name=source['name'],state=source['state'],published_at=None,first_seen=when,last_seen=when,origin='official monitored page link',verification='Official website link, not a confirmed dated sale or active inventory.')
        if len(found)>=35: break
    return list(found.values())

def checked_page(src,when,fetch):
    try:
        raw=fetch(src['url']);digest=page_fingerprint(raw)
        return dict(kind='page',source=src,hash=digest,events=parse_events_from_jsonld(raw,src,when),leads=parse_official_links(raw,src,when),ok=True)
    except Exception as e:
        return dict(kind='page',source=src,ok=False,error=f'{type(e).__name__}: {str(e)[:160]}')

def finish_report(previous,selected,results,when,seed=SEED):
    runs=int(previous.get('run_count',0))+1
    oldleads={x['id']:x for x in previous.get('leads',[]) if 'id' in x}
    oldevents={x['id']:x for x in previous.get('events',[]) if 'id' in x}
    oldpages={x['id']:x for x in previous.get('pages',[]) if 'id' in x}
    oldchecks={x['id']:x for x in previous.get('checks',[]) if 'id' in x}
    configured={s['id'] for s in readjson(FEEDS,[])+readjson(PAGES,[])}
    oldchecks={k:v for k,v in oldchecks.items() if k in configured}
    oldpages={k:v for k,v in oldpages.items() if k in configured}
    had_before=bool(previous.get('last_checked'))
    newleads=[];changed=[];newevents=[];checks=oldchecks.copy();pages=oldpages.copy();items=oldleads.copy();events=oldevents.copy()
    for result in results:
        src=result['source'];id=src['id'];ok=result['ok'];kind=result['kind']
        prior=oldchecks.get(id,{})
        ch=dict(id=id,name=src['name'],state=src['state'],category=src.get('category',kind),kind=kind,url=src['url'],status='ok' if ok else 'error',last_attempt=when,last_success=when if ok else prior.get('last_success'),detail=result.get('error',''),found=len(result.get('leads',[])) + len(result.get('events',[])))
        checks[id]=ch
        if kind=='feed' and ok:
            for x in result['leads']:
                if x['id'] in items:x['first_seen']=items[x['id']].get('first_seen',when)
                elif had_before:newleads.append(x)
                items[x['id']]=x
        if kind=='page':
            prev=oldpages.get(id,{})
            # Never classify the first extraction of existing page links as a newly posted sale.
            prior_links=set(prev.get('link_ids',[]))
            for lead in result.get('leads',[]) if ok else []:
                if lead['id'] in items:
                    lead['first_seen']=items[lead['id']].get('first_seen',when)
                elif had_before and 'link_ids' in prev and lead['id'] not in prior_links:
                    newleads.append(lead)
                items[lead['id']]=lead
            changed_content=bool(ok and prev.get('fingerprint') and prev['fingerprint']!=result['hash'])
            pages[id]=dict(**src,fingerprint=result.get('hash',prev.get('fingerprint')),status=ch['status'],changed=changed_content,last_attempt=when,last_success=ch['last_success'],last_change=when if changed_content else prev.get('last_change'),link_ids=sorted(x['id'] for x in result.get('leads',[])) if ok else prev.get('link_ids',[]),detail=ch['detail'])
            if changed_content:changed.append(pages[id])
            if ok:
                for ev in result['events']:
                    if ev['id'] not in events and had_before:newevents.append(ev)
                    events[ev['id']]=ev
    today=when[:10]
    cutoff=(datetime.fromisoformat(when.replace('Z','+00:00'))-timedelta(days=60)).date().isoformat()
    items={k:v for k,v in items.items() if v.get('last_seen','')[:10]>=cutoff and not (v.get('origin')=='official monitored page link' and (OLD_YEAR.search(urlparse(v.get('url','')).path) or OLD_YEAR.search(v.get('title',''))))}
    events={k:v for k,v in events.items() if v.get('end','')>=today}
    alerts_sent=set(previous.get('alerts_sent',[]))
    alerts=[]
    if had_before:
        for x in newleads:
            alerts.append(dict(id='new:'+x['id'],type='new',title=x['title'],url=x['url'],state=x.get('state'),at=when,detail='Official-page link or other unverified discovery lead'))
        for x in newevents:
            alerts.append(dict(id='event:'+x['id'],type='event',title=x['title'],url=x['url'],state=x.get('state'),at=when,detail='Structured event; check organizer'))
        for p in changed:
            alerts.append(dict(id='changed:'+p['id']+':'+p['fingerprint'][:12],type='changed',title=p['name']+' updated',url=p['url'],state=p['state'],at=when,detail='Page changed; specific sale not confirmed'))
        future=(datetime.fromisoformat(today)+timedelta(days=1)).date().isoformat()
        for x in [*seed,*events.values()]:
            if not x.get('start') or not x.get('end'): continue
            if today<=x['end']<=future:
                key='ending:'+x['id']+':'+x['end']
                if key not in alerts_sent:
                    alerts.append(dict(id=key,type='ending',title=x['title'],url=x.get('url',''),state=x.get('state'),at=when,detail='Scheduled end date '+x['end']+'; exact closing time not confirmed'))
    # Prevent duplicate outbound notifications across repeated updates.
    previous_alert_ids={a['id'] for a in previous.get('alerts',[]) if 'id' in a}
    distinct=[a for a in alerts if a['id'] not in previous_alert_ids]
    allowed_states=set(x.strip().upper() for x in os.environ.get('ALERT_STATES','').split(',') if x.strip())
    # Retain a small unsent backlog so transient webhook failures can be retried.
    notify=[a for a in distinct+previous.get('alerts',[]) if a['id'] not in alerts_sent and (not allowed_states or a.get('state') in allowed_states or a.get('state')=='US')][:20]
    # Only mark as sent when an actual webhook exists; dashboard alerts remain independent.
    notify_status='not_configured'
    if os.environ.get('DISCORD_WEBHOOK_URL') and notify:
        from urllib.request import Request,urlopen
        msg='📚 BookScout USA · '+str(len(notify))+' new alerts\n'+'\n'.join('• '+x['title'][:80]+' '+x.get('url','') for x in notify[:10])
        req=Request(os.environ['DISCORD_WEBHOOK_URL'],data=json.dumps({'content':msg[:1900]}).encode(),headers={'Content-Type':'application/json','User-Agent':'BookScoutUSA/2.0'},method='POST')
        try:
            with urlopen(req,timeout=12) as resp:notify_status='sent' if 200<=resp.status<300 else 'HTTP '+str(resp.status)
        except Exception as e:notify_status='error:'+type(e).__name__
        if notify_status=='sent':alerts_sent.update(x['id'] for x in notify)
    report=dict(schema=2,run_count=runs,last_checked=when,status='partial' if any(not x['ok'] for x in results) else 'ok',checks=sorted(checks.values(),key=lambda x:(x['state'],x['name'])),pages=sorted(pages.values(),key=lambda x:x['name']),leads=sorted(items.values(),key=lambda x:x['first_seen'],reverse=True)[:1500],events=sorted(events.values(),key=lambda x:x['start'])[:2000],alerts=(distinct+previous.get('alerts',[]))[:500],alerts_sent=sorted(alerts_sent)[-1000:],notification_status=notify_status,monitoring=dict(feeds_total=len(readjson(FEEDS,[])),pages_total=len(readjson(PAGES,[])),checked_this_run=len(results),hourly=True),notice='Official site links are discovery leads, NOT verified available lots or dated sales. Page changes are not proof of new inventory. Failed checks remain visible. No automated Amazon or eBay price/rank claims.')
    return report

def run(fetch=get,previous=None,now=None,feeds=None,pages=None,max_workers=4):
    when=now or utcnow();previous=previous if previous is not None else readjson(OUTPUT,{})
    feeds=feeds if feeds is not None else readjson(FEEDS,[]);pages=pages if pages is not None else readjson(PAGES,[])
    # Alternate 50-state feed topics each run: every state is searched hourly,
    # each topic per state every two hours. Page checks rotate over four runs.
    run_no=int(previous.get('run_count',0));chosen=[]
    for src in feeds:
        chosen.append(('feed',src))
    for src in pages:
        chosen.append(('page',src))
    def task(v):
        kind,src=v
        return checked_feed(src,when,fetch) if kind=='feed' else checked_page(src,when,fetch)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        results=list(pool.map(task,chosen))
    return finish_report(previous,chosen,results,when)

def main():
    report=run()
    savejson(OUTPUT,report)
    (ROOT/'web/data/live-data.js').write_text('window.BOOKSCOUT_LIVE_DATA='+json.dumps(report,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n',encoding='utf8')
    successes=sum(x['status']=='ok' for x in report['checks'] if x.get('last_attempt')==report['last_checked'])
    failures=sum(x['status']=='error' for x in report['checks'] if x.get('last_attempt')==report['last_checked'])
    print(f"BookScout USA {report['last_checked']} run={report['run_count']} ok={successes} errors={failures} leads={len(report['leads'])} events={len(report['events'])}")

if __name__=='__main__':main()
