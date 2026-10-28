import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import national_update as n

class NationalTests(unittest.TestCase):
    def test_blocked_news_feeds_removed(self):
        feeds=json.loads((ROOT/'config/feeds.json').read_text())
        self.assertFalse(any('news.google.com' in f['url'] for f in feeds))
        self.assertGreaterEqual(len(json.loads((ROOT/'config/watch_pages.json').read_text())),60)

    def test_official_source_links_are_discovery_not_sales(self):
        page={'id':'test','url':'https://library.example.org/events','state':'VA','name':'Official Library'}
        raw=b'''<html><a href="/friends-book-sale">Friends Book Sale</a>
        <a href="https://outside.example.org/auction">Book sale elsewhere</a>
        <a href="/files/2025-book-sale">Book Sale 2025</a>
        <a href="/about">About Us</a></html>'''
        leads=n.parse_official_links(raw,page,'2026-10-28T20:00:00Z')
        self.assertEqual(len(leads),1)
        self.assertEqual(leads[0]['url'],'https://library.example.org/friends-book-sale')
        self.assertIn('not a confirmed',leads[0]['verification'].lower())
        self.assertNotIn('start',leads[0])

    def test_official_page_leads_baselined_without_spurious_alerts(self):
        src={'id':'official','state':'VA','name':'Official Library','url':'https://library.example.org/events'}
        raw=b'<html><a href="/book-sale">Upcoming Book Sale</a></html>'
        result=n.checked_page(src,'2026-10-28T20:00:00Z',lambda _:raw)
        prior={'last_checked':'2026-10-28T19:00:00Z','run_count':2,'pages':[dict(**src,fingerprint='old_hash',last_success='2026-10-28T19:00:00Z')],'checks':[],'leads':[],'events':[]}
        report=n.finish_report(prior,[],[result],'2026-10-28T20:00:00Z',seed=[])
        self.assertEqual(len(report['leads']),1)
        self.assertFalse(any(a['type']=='new' for a in report['alerts']))
        self.assertEqual(report['checks'][0]['status'],'ok')

    def test_jsonld_events_only(self):
        page={'id':'test','url':'https://example.org/book-sale','state':'NC','name':'Library'}
        raw=b'''<html><script type="application/ld+json">{"@type":"Event","name":"Book sale 2026","startDate":"2026-11-02","endDate":"2026-11-03","location":{"address":{"addressLocality":"Raleigh","addressRegion":"NC"}}}</script><script type="application/ld+json">{"@type":"Event","name":"Book club meeting","startDate":"2026-11-04"}</script></html>'''
        ev=n.parse_events_from_jsonld(raw,page,'2026-10-28T20:00:00Z')
        self.assertEqual(len(ev),1)
        self.assertEqual(ev[0]['start'],'2026-11-02')
        self.assertEqual(ev[0]['price'],'Not reported')

    def test_invalid_sources_do_not_become_success(self):
        page={'id':'closed','state':'VA','name':'Closed','url':'https://example.org'}
        def blocked(_):
            raise PermissionError('robots denied')
        x=n.checked_page(page,'2026-10-28T20:00:00Z',blocked)
        self.assertFalse(x['ok'])
        self.assertIn('robots',x['error'])

if __name__=='__main__': unittest.main()
