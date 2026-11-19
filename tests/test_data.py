import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'update_data.py'
spec = importlib.util.spec_from_file_location('collector', PATH)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class MarketTests(TestCase):
    def test_empty_month_and_area_band(self):
        region = {'name': '서울 종로구', 'metro': '서울', 'code': '11110'}
        rows = [{'region': region['name'], 'date': '2026-11-01', 'price': 55000, 'sqm': 84.0},
                {'region': region['name'], 'date': '2026-11-02', 'price': 65000, 'sqm': 84.0}]
        result = collector.market_snapshot(rows, [region], ['202611', '202610', '202609'], set())
        self.assertEqual(result[0]['count'], 2)
        self.assertEqual(result[0]['months'][0]['bands'][1]['median'], 60000)
        self.assertEqual(result[0]['months'][1]['count'], 0)
        self.assertTrue(result[0]['complete'])

    def test_incomplete_region_flag(self):
        region = {'name': '서울 종로구', 'metro': '서울', 'code': '11110'}
        result = collector.market_snapshot([], [region], ['202611'], {('11110', '202611')})
        self.assertFalse(result[0]['complete'])
        self.assertFalse(result[0]['months'][0]['complete'])

    def test_pagination_keeps_identical_transactions(self):
        row = '''<item><aptNm>테스트</aptNm><dealAmount>70,000</dealAmount><excluUseAr>84.00</excluUseAr><dealYear>2026</dealYear><dealMonth>11</dealMonth><dealDay>2</dealDay><floor>3</floor></item>'''
        pages = [f'<response><body><totalCount>2</totalCount><items>{row}{row}</items></body></response>'.encode()]
        with patch.object(collector, 'fetch', side_effect=pages):
            result = collector.request_month({'name': '서울 종로구', 'code': '11110'}, '202611', 'TEST')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['price'], 70000)