import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import monitor_core

class InstitutionalDiscoveryTests(unittest.TestCase):
    def test_institutional_keyword_matches(self):
        examples = [
            'University deaccession books auction',
            'Withdrawn library materials for sale',
            'Weeded collection book sale',
            'Obsolete curriculum surplus',
            'Library contents liquidation',
            'Institutional cleanout of books',
            'Boxed media surplus auction',
            'School surplus auction'
        ]
        for example in examples:
            with self.subTest(text=example):
                self.assertTrue(monitor_core.relevant(example,''))

    def test_reject_book_club(self):
        self.assertFalse(monitor_core.relevant('Book club signing event',''))

if __name__ == '__main__':
    unittest.main()
