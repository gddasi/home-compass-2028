import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from development_radar import build_monitor, category, event_from_news, headline_stage

REGIONS = [
    {"name": "서울 종로구", "metro": "서울", "code": "11110"},
    {"name": "경기 성남시 분당구", "metro": "경기", "code": "41135"},
    {"name": "인천 연수구", "metro": "인천", "code": "28185"},
]

def notice(ident, title, date="2026-11-19"):
    return {"id": ident, "title": title, "date": date, "url": "https://www.molit.go.kr/a",
            "source": "공식 도메인 검색", "topic": "development"}

class DevelopmentRadarTest(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(category("GTX-B 착공 설명"), "rail")
        self.assertEqual(category("분당구 정비구역 지정 고시"), "renewal")
        self.assertEqual(category("수도권 신도시 지구계획 변경"), "urban")
        self.assertIsNone(category("수능 수험생 교통지원 안내"))

    def test_precise_and_broad_location(self):
        exact = event_from_news(notice("1", "분당구 재개발 정비구역 지정"), REGIONS, "2026-11-19")
        self.assertEqual(exact["region"], "경기 성남시 분당구")
        self.assertTrue(exact["region_exact"])
        broad = event_from_news(notice("2", "성남시 재개발 설명회"), REGIONS, "2026-11-19")
        self.assertEqual(broad["region"], "")
        self.assertFalse(broad["region_exact"])

    def test_uncertain_stage_and_change_hint(self):
        self.assertIn("변경", headline_stage("GTX-B 일정 변경 검토"))
        item = event_from_news(notice("1", "인천 연수구 지하철 연장 일정 변경 검토"), REGIONS, "2026-11-19")
        self.assertTrue(item["change_hint"])
        self.assertFalse(item.get("status_verified", False))

    def test_history_dedupe_and_new_detection(self):
        news = [notice("a", "종로구 재개발 사업시행인가")]
        first, hist = build_monitor(news, REGIONS, {}, "2026-11-19")
        self.assertEqual(first["new_count"], 0)
        same, hist2 = build_monitor(news, REGIONS, hist, "2026-11-19")
        self.assertEqual(same["new_count"], 0)
        newer, _ = build_monitor(news+[notice("b", "GTX-A 연장 계획 변경")],
                                 REGIONS, hist2, "2026-11-20")
        self.assertEqual(newer["new_count"], 1)
        self.assertEqual(newer["total_events"], 2)

if __name__ == "__main__":
    unittest.main()
