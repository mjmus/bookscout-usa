import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import national_update as n
class NationalTests(unittest.TestCase):
 def test_coverage(self):
  feeds=json.loads((ROOT/'config/feeds.json').read_text())
  self.assertEqual(len(feeds),110)
  states={x['state'] for x in feeds if x['state']!='US'}
  self.assertEqual(len(states),51)
  self.assertTrue(all(sum(f['state']==st for f in feeds)==2 for st in states))
 def test_schedule_alternates_without_skipping_states(self):
  feeds=json.loads((ROOT/'config/feeds.json').read_text())
  def failure(url):raise RuntimeError('test: unavailable')
  a=n.run(fetch=failure,feeds=feeds,pages=[],previous={'run_count':0},now='2026-10-28T20:00:00Z')
  b=n.run(fetch=failure,feeds=feeds,pages=[],previous={'run_count':1},now='2026-10-28T21:00:00Z')
  self.assertEqual(len(a['checks']),59);self.assertEqual(len(b['checks']),59)
  self.assertIn('VA',{x['state'] for x in a['checks']})
  self.assertNotEqual(set(x['id'] for x in a['checks']),set(x['id'] for x in b['checks']))
  self.assertEqual(a['status'],'partial')
  self.assertEqual(len(a['leads']),0)
 def test_structured_events_only(self):
  page={'id':'test','url':'https://example.org/book-sale','state':'NC','name':'Library'}
  raw=b'''<html><script type="application/ld+json">{"@type":"Event","name":"Book sale 2026","startDate":"2026-11-02","endDate":"2026-11-03","location":{"address":{"addressLocality":"Raleigh","addressRegion":"NC"}}}</script><script type="application/ld+json">{"@type":"Event","name":"Book club meeting","startDate":"2026-11-04"}</script></html>'''
  ev=n.parse_events_from_jsonld(raw,page,'2026-10-28T20:00:00Z')
  self.assertEqual(len(ev),1);self.assertEqual(ev[0]['start'],'2026-11-02');self.assertEqual(ev[0]['lat'],None)
 def test_alert_dedup_and_ending(self):
  prev={'last_checked':'2026-10-28T14:00:00Z','run_count':1,'leads':[],'events':[],'checks':[],'pages':[],'alerts':[],'alerts_sent':[]}
  src={'id':'feed-test','state':'VA','name':'Virginia book sales','url':'https://news.google.com/rss/test'}
  res=[{'kind':'feed','source':src,'ok':True,'leads':[{'id':'f123','title':'Book sale','url':'https://example.org/1','state':'VA','first_seen':'2026-10-28T18:00:00Z','last_seen':'2026-10-28T18:00:00Z'}]}]
  first=n.finish_report(prev,[],res,'2026-10-28T18:00:00Z',seed=[{'id':'a1','start':'2026-10-25','end':'2026-10-29','title':'Library book sale','state':'VA','url':'https://example.org'}])
  self.assertTrue(any(a['type']=='new' for a in first['alerts']))
  self.assertTrue(any(a['type']=='ending' for a in first['alerts']))
  second=n.finish_report(first,[],res,'2026-10-28T19:00:00Z',seed=[])
  self.assertEqual(len([a for a in first['alerts'] if a['type']=='new']),len([a for a in second['alerts'] if a['type']=='new']))
 def test_parsing_no_invented_prices(self):
  page={'id':'demo','url':'https://example.org','state':'PA','name':'Demo'}
  s=b'<script type="application/ld+json">{"@type":"Event","name":"Used book sale","startDate":"2026-11-03","location":{"address":{"addressLocality":"York","addressRegion":"PA"}}}</script>'
  x=n.parse_events_from_jsonld(s,page,'2026-10-28T18:00:00Z')[0]
  self.assertEqual(x['price'],'Not reported');self.assertIsNone(x['qty'])
if __name__=='__main__':unittest.main()
