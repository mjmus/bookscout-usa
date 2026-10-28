#!/usr/bin/env python3
"""BookScout open-RSS discovery and official-source change detection.

No paid API, no scraping behind logins, no invented auction bids, sales counts,
ISBN rankings, event dates, or shipping terms. Changes are leads, not listings.
"""
from __future__ import annotations
import argparse
import calendar
import hashlib
import html
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib import robotparser
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UA = 'BookScoutSourceMonitor/1.0 (book sourcing, respectful public-source checks; contact via repo)' 
TIMEOUT = 16
MAX_BYTES = 1_500_000
POSITIVE = re.compile(r'\b(?:book\s+sale|used\s+book\s+sale|library\s+sale|book\s+lot|lot\s+of\s+books|bulk\s+books?|books?\s+auction|books?\s+pallets?|gaylord(?:s)?\s+of\s+books|book\s+liquidation|friends\s+of\s+the\s+library|textbook\s+sale|library\s+surplus|deaccession(?:ed|ing)?\s+(?:books?|library|collection)|(?:withdrawn|weeded|discarded)\s+(?:library\s+)?(?:books?|materials?|collections?)|obsolete\s+(?:textbooks?|curriculum|school\s+books?)|library\s+(?:contents|collection\s+(?:sale|liquidation))|institutional\s+cleanout|boxed\s+(?:books|media)|(?:school|university|library|college)\s+(?:surplus|liquidation|auction)|surplus\s+(?:textbooks?|books?))\b', re.I)
EXCLUDE = re.compile(r'\b(?:book\s+review|book\s+signing|cookbook\s+recipe|book\s+club|book\s+ban|book\s+tour)\b', re.I)
ROBOTS_CACHE = {}

def utcnow(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def readjson(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default

def savejson(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)+'\n',encoding='utf-8')

def is_public_https(url):
    p=urlparse(url)
    return (p.scheme=='https' and p.hostname and not re.search(r'(^localhost$|\.local$|^127\.|^10\.|^192\.168\.|^169\.254\.)',p.hostname,re.I) and not p.username)

def allowed_by_robots(url):
    p=urlparse(url); base=f'{p.scheme}://{p.netloc}'
    if base not in ROBOTS_CACHE:
        rp=robotparser.RobotFileParser(); rp.set_url(base+'/robots.txt')
        try:
            rp.read()
            ROBOTS_CACHE[base]=rp
        except Exception as exc:
            raise RuntimeError(f'robots.txt unavailable for {p.netloc}: {exc}')
    return ROBOTS_CACHE[base].can_fetch(UA,url)

def get(url):
    if not is_public_https(url): raise ValueError('URL must be a public HTTPS address')
    if not allowed_by_robots(url): raise PermissionError('robots.txt disallows this path')
    req=Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml, application/atom+xml, application/xml, text/html;q=0.9,*/*;q=0.7'})
    with urlopen(req,timeout=TIMEOUT) as resp:
        if int(resp.status)!=200: raise RuntimeError(f'HTTP {resp.status}')
        data=resp.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES: raise RuntimeError('response too large')
        return data

def clean(s, limit=400):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()[:limit]

def parse_time(value):
    if not value: return None
    try:
        d=parsedate_to_datetime(value)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    except (ValueError, TypeError, IndexError):
        try: return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except (ValueError, TypeError): return None

def parsed_feed(raw):
    root=ET.fromstring(raw)
    entries=[]
    for node in root.iter():
        typ=node.tag.rsplit('}',1)[-1]
        if typ not in ('item','entry'): continue
        fields={}
        for child in node:
            key=child.tag.rsplit('}',1)[-1]
            if key=='link': fields['link']=child.attrib.get('href') or (child.text or '')
            elif key in ('title','description','summary','content','pubDate','published','updated','guid','id'):
                fields[key]=''.join(child.itertext()).strip()
        if fields.get('title'):
            entries.append({'title':clean(fields.get('title',''),220),
                'description':clean(fields.get('description') or fields.get('summary') or fields.get('content'),480),
                'url':(fields.get('link') or fields.get('guid') or fields.get('id') or '').strip(),
                'published_at':parse_time(fields.get('pubDate') or fields.get('published') or fields.get('updated'))})
    return entries

def relevant(title, description):
    s=title+' '+description
    return bool(POSITIVE.search(s)) and not bool(EXCLUDE.search(title))

def lead_id(title,url):
    # Prefer the canonical link for stability across repeated runs; no invented event IDs.
    target=url.split('#',1)[0].rstrip('/') or re.sub(r'\W+',' ',title.lower())
    return 'f'+hashlib.sha256(target.encode()).hexdigest()[:16]

def normalize_lead(entry,source,when):
    if not relevant(entry['title'],entry['description']): return None
    url=entry.get('url','')
    if not is_public_https(url): return None
    published=entry.get('published_at')
    # Don't revive years-old results or claim they are fresh.
    if published:
        dt=datetime.fromisoformat(published.replace('Z','+00:00'))
        if datetime.now(timezone.utc)-dt>timedelta(days=45): return None
    return dict(id=lead_id(entry['title'],url),title=entry['title'],
                summary=entry['description'],url=url,source_id=source['id'],
                source_name=source['name'],state=source['state'],
                published_at=published,first_seen=when,last_seen=when,
                verification='Search/news-feed discovery only; not a confirmed book sale, lot, price or inventory quantity.')

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.tokens=[]
    def handle_starttag(self,t,a):
        if t in ('script','style','noscript','svg','template'): self.depth+=1
    def handle_endtag(self,t):
        if t in ('script','style','noscript','svg','template') and self.depth: self.depth-=1
    def handle_data(self,t):
        if not self.depth and t.strip(): self.tokens.append(t.strip())

def page_fingerprint(raw):
    p=VisibleText(); p.feed(raw.decode('utf-8','replace'))
    text=clean(' '.join(p.tokens),100000)
    return hashlib.sha256(text.encode()).hexdigest()

def notify_discord(new_items,changed_pages):
    hook=os.environ.get('DISCORD_WEBHOOK_URL','')
    if not hook or (not new_items and not changed_pages): return 'not_configured_or_no_news'
    # URLs and titles are shown; avoid exposing private sourcing notes.
    lines=[f'📚 BookScout: {len(new_items)} new search leads, {len(changed_pages)} source-page changes']
    for item in new_items[:7]: lines.append(f"• {item['title'][:110]}\n{item['url']}")
    for p in changed_pages[:6]: lines.append(f"• Updated: {p['name']}\n{p['url']}")
    req=Request(hook,data=json.dumps({'content':'\n'.join(lines)[:1900]}).encode(),headers={'Content-Type':'application/json','User-Agent':UA},method='POST')
    try:
        with urlopen(req,timeout=12) as r: return 'sent' if 200<=r.status<300 else f'HTTP {r.status}'
    except Exception as exc: return f'error: {type(exc).__name__}'

def run(fetch=get,feeds=None,pages=None,previous=None,when=None,delay=0):
    when=when or utcnow()
    feeds=feeds if feeds is not None else readjson(ROOT/'config/feeds.json',[])
    pages=pages if pages is not None else readjson(ROOT/'config/watch_pages.json',[])
    previous=previous if previous is not None else readjson(ROOT/'web/data/live.json',{})
    olditems={x['id']:x for x in previous.get('leads',[]) if 'id' in x}
    oldpages={x['id']:x for x in previous.get('pages',[]) if 'id' in x}
    items={};checks=[];new=[];changed=[];page_results=[]
    for src in feeds:
        try:
            rows=parsed_feed(fetch(src['url']))
            accepted=0
            for row in rows:
                lead=normalize_lead(row,src,when)
                if lead is None: continue
                prior=olditems.get(lead['id'])
                if prior:
                    lead['first_seen']=prior.get('first_seen',when)
                else: new.append(lead)
                if lead['id'] not in items: items[lead['id']]=lead;accepted+=1
            checks.append(dict(source=src['name'],type='rss',state=src['state'],url=src['url'],status='ok',found=accepted,checked_at=when))
        except Exception as exc:
            checks.append(dict(source=src['name'],type='rss',state=src['state'],url=src['url'],status='error',detail=str(exc)[:200],checked_at=when))
        if delay: time.sleep(delay)
    for p in pages:
        old=oldpages.get(p['id'],{})
        try:
            digest=page_fingerprint(fetch(p['url']))
            is_changed=bool(old.get('fingerprint') and old['fingerprint']!=digest)
            page=dict(**p,fingerprint=digest,changed=is_changed,checked_at=when,status='ok',last_change=when if is_changed else old.get('last_change'))
            if is_changed: changed.append(page)
        except Exception as exc:
            page=dict(**p,fingerprint=old.get('fingerprint'),changed=False,checked_at=when,status='error',detail=str(exc)[:200],last_change=old.get('last_change'))
        page_results.append(page)
        checks.append(dict(source=p['name'],type='page',state=p['state'],url=p['url'],status=page['status'],detail=page.get('detail',''),checked_at=when))
        if delay: time.sleep(delay)
    # Preserve old findings for 60 days even if RSS stops showing them; mark them stale.
    cutoff=datetime.fromisoformat(when.replace('Z','+00:00'))-timedelta(days=60)
    for id,prior in olditems.items():
        try: last=datetime.fromisoformat(prior.get('last_seen','').replace('Z','+00:00'))
        except ValueError: continue
        if id not in items and last>=cutoff: items[id]=prior
    leads=sorted(items.values(),key=lambda x:x.get('first_seen',''),reverse=True)[:250]
    # A changed source page is NOT proof of a particular lot, date, quantity, or sale.
    had_run=bool(previous.get('last_checked'))
    notification=notify_discord(new if had_run else [],changed if had_run else []) if fetch is get else 'test_mode'
    return dict(schema=1,last_checked=when,monitor_type='Automated RSS discovery + official-page change detection',
                status='partial' if any(x['status']=='error' for x in checks) else 'ok',
                lead_count=len(leads),new_count=len(new),changes_count=len(changed),
                notifications=notification,checks=checks,pages=page_results,leads=leads,
                notice='Discovery leads are NOT verified auctions or book sales. Always verify actual dates, pickup, shipping, screening, bid, condition, resale comps and ISBN demand on original sources.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--delay',type=float,default=.4);args=ap.parse_args()
    payload=run(delay=args.delay)
    savejson(ROOT/'web/data/live.json',payload)
    # JS sidecar allows the app to open under file:// as well as GitHub Pages.
    js='window.BOOKSCOUT_LIVE_DATA='+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n'
    (ROOT/'web/live-data.js').write_text(js,encoding='utf-8')
    print('BookScout updated:',payload['status'],payload['lead_count'],'leads; ',payload['changes_count'],'changed source pages;',sum(c['status']=='error' for c in payload['checks']),'source errors')

if __name__=='__main__':main()
