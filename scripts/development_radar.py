"""Development project headline monitor for the Seoul capital region.

This is a PUBLIC ANNOUNCEMENT MONITOR, not an official approval/status registry.
Only label facts as 'mentioned in headline'; source documents must be checked.
No private household financial data is stored or processed here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any

RAIL = (
    "gtx", "철도", "지하철", "도시철도", "광역급행", "광역전철",
    "전철", "경전철", "트램", "신분당선", "신안산선", "인덕원동탄",
    "인동선", "월곶판교", "월판선", "서부선", "위례신사선",
    "동북선", "서해선", "수인분당선", "교외선", "경강선",
    "대장홍대", "대장-홍대", "신림선", "경의중앙선", "면목선",
)
RENEWAL = (
    "재개발", "재건축", "정비구역", "정비사업", "도시정비",
    "신속통합기획", "모아타운", "모아주택", "관리처분",
    "조합설립", "노후계획도시", "공공재개발", "공공재건축",
    "가로주택정비", "소규모주택정비", "역세권활성화",
)
URBAN = (
    "도시개발", "지구계획", "택지개발", "택지지구", "신도시",
    "공공주택지구", "공공택지", "주택지구", "도시계획시설",
    "개발제한구역", "복합개발",
)
CHANGES = ("연기", "지연", "취소", "중단", "변경", "재검토", "보류", "철회", "무산", "기간연장", "일정조정")
PHASES = (
    ("지연·변경", ("연기", "지연", "취소", "중단", "변경", "보류", "철회", "무산", "재검토")),
    ("개통·준공", ("개통", "준공", "완공", "개장")),
    ("착공·공사", ("착공", "공사 시작", "공사착수", "공사 착수")),
    ("관리처분", ("관리처분",)),
    ("사업시행인가", ("사업시행인가", "사업시행계획인가")),
    ("조합설립", ("조합설립", "조합 설립")),
    ("구역지정·확정", ("정비구역 지정", "구역지정", "지구 지정", "지구지정", "사업 확정")),
    ("계획·심의", ("기본계획", "구축계획", "기본구상", "도시계획", "예비타당성", "예타", "공청회", "설명회", "추진계획")),
)
PARENTS = ("고양시", "부천시", "성남시", "수원시", "안산시", "안양시", "용인시", "화성시")

def category(title: str) -> str | None:
    name = title.lower()
    if any(k in name for k in RAIL):
        return "rail"
    if any(k in name for k in RENEWAL):
        return "renewal"
    if any(k in name for k in URBAN):
        return "urban"
    return None

def headline_stage(title: str) -> str:
    for label, keys in PHASES:
        if any(k in title for k in keys):
            return "제목에 '" + label + "' 관련 표현"
    return "단계 미확인 (원문 확인 필요)"

def match_region(title: str, region_list: list[dict]) -> dict:
    # Never pretend an entire city or line is located within a particular district.
    # Match longest precise administrative name only.
    found = []
    for item in region_list:
        label = item.get("name", "")
        leaf = label.split(" ", 1)[-1]
        # district token is unique in the region list except where multiple parent gu share suffix.
        # Prefer exact full name or 2-part city district names.
        if label and label in title:
            found.append((len(label) + 100, item))
        elif leaf and leaf in title:
            found.append((len(leaf), item))
        elif " " in leaf and leaf.split(" ")[-1] in title:
            found.append((len(leaf.split(" ")[-1]) - 1, item))
    if found:
        best = max(found, key=lambda z: z[0])[1]
        return {"region": best.get("name", ""), "metro": best.get("metro", ""), "region_exact": True}
    for parent in PARENTS:
        if parent in title:
            return {"region": "", "metro": "경기", "region_exact": False, "scope": "경기 " + parent + " (세부 구 미확인)"}
    for token, metro in (("인천", "인천"), ("경기도", "경기"), ("서울", "서울")):
        if token in title:
            return {"region": "", "metro": metro, "region_exact": False,
                    "scope": metro + " 전체·지역 미특정"}
    return {"region": "", "metro": "", "region_exact": False, "scope": "지역 미특정·노선 전체 가능"}

def event_from_news(item: dict, regions: list[dict], seen_at: str) -> dict | None:
    title = str(item.get("title") or "").strip()
    kind = category(title)
    if kind is None or not item.get("url", "").startswith(("https://", "http://")):
        return None
    loc = match_region(title, regions)
    key = str(item.get("id") or hashlib.sha1((title+"|"+item["url"]).encode()).hexdigest()[:18])
    return {
        "id": key, "category": kind, "title": title[:260],
        "date": item.get("date") or seen_at, "source": item.get("source", ""),
        "url": item["url"], "stage_hint": headline_stage(title),
        "change_hint": any(c in title for c in CHANGES),
        "region": loc.get("region", ""), "metro": loc.get("metro", ""),
        "scope": loc.get("scope") or loc.get("region", ""),
        "region_exact": loc["region_exact"],
        "first_seen": seen_at,
    }

def build_monitor(news: list[dict], regions: list[dict], previous: dict | None = None,
                  checked_at: str | None = None) -> tuple[dict, dict]:
    checked_at = checked_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    previous = previous or {}
    old_events = {x["id"]: x for x in previous.get("events", []) if x.get("id")}
    bootstrapping = not bool(previous.get("updated_at"))
    seen_now = set()
    for item in news:
        event = event_from_news(item, regions, checked_at)
        if not event:
            continue
        k = event["id"]
        if k in seen_now:
            continue
        seen_now.add(k)
        if k in old_events:
            event["first_seen"] = old_events[k].get("first_seen", checked_at)
        old_events[k] = event
    keep_after = (dt.date.fromisoformat(checked_at) - dt.timedelta(days=550)).isoformat()
    history_events = sorted((x for x in old_events.values() if x.get("date", "") >= keep_after),
                            key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True)[:750]
    for x in history_events:
        x["is_new"] = not bootstrapping and x["id"] in seen_now and x["first_seen"] == checked_at
        x["status_verified"] = False  # never infer administrative approval from headlines
    visible = history_events[:250]
    dashboard = {
        "generated_at": checked_at,
        "events": visible,
        "total_events": len(history_events),
        "new_count": sum(1 for x in history_events if x["is_new"]),
        "change_count": sum(1 for x in visible if x["change_hint"]),
        "method": "공식기관 도메인 관련 발표 제목 자동탐색. 제목의 단계·일정 표현은 검증 전 신호이며 실제 추진 단계·개통 예정일을 확정하지 않습니다.",
    }
    history = {"updated_at": checked_at, "events": [
        {k: v for k, v in x.items() if k not in ("is_new", "status_verified")}
        for x in history_events
    ]}
    return dashboard, history
