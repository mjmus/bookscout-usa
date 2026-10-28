import json
import re
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GaylordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        txt=(ROOT/'web/data/gaylord-sources.js').read_text(encoding='utf8').strip()
        assert txt.startswith('window.BOOKSCOUT_GAYLORD_SOURCES=')
        cls.rows=json.loads(txt.split('=',1)[1].removesuffix(';'))
    def test_distinct_first_party_or_explicit_aggregator_sources(self):
        self.assertGreaterEqual(len(self.rows),12)
        ids=[r['id'] for r in self.rows]
        self.assertEqual(len(ids),len(set(ids)))
        for row in self.rows:
            self.assertTrue(row['url'].startswith('https://'))
            self.assertNotIn('booksalefinder.com',row['url'])
            self.assertTrue(row['evidence'])
            self.assertTrue(row['screening_note'])
            self.assertTrue(row['reviewed_at'])
    def test_unscanned_just_seller_claim(self):
        claims=[r for r in self.rows if r['screening']=='seller_claim_unscanned']
        self.assertGreaterEqual(len(claims),2)
        for r in claims:
            self.assertRegex(r['screening_note'],r'(?i)(seller|vendor|market|says|claims)')
    def test_historical_auctions_cannot_be_mistaken_for_active(self):
        old=[r for r in self.rows if r['type']=='historical']
        self.assertTrue(old)
        for row in old:
            self.assertEqual(row['repeat'],'past')
            self.assertTrue(row['end']<'2026-10-28')
    def test_wholesale_gaylord_link_is_discoverable(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        import national_update as n
        page={'id':'bulk-shop','name':'Book supplier','url':'https://example.org/pallets','state':'US'}
        raw=b'<a href="/products/unsorted-books">Unsorted Wholesale Used Book Pallet</a>'
        leads=n.parse_official_links(raw,page,'2026-10-28T20:00:00Z')
        self.assertEqual(len(leads),1)
        self.assertEqual(leads[0]['url'],'https://example.org/products/unsorted-books')

    def test_no_automatic_rank_or_guaranteed_profit(self):
        for row in self.rows:
            self.assertFalse(row['isbn_manifest'])
            self.assertIsNone(row['start'])
            if row['price'] is not None:
                self.assertGreaterEqual(row['price'],0)
if __name__ == '__main__':
    unittest.main()
