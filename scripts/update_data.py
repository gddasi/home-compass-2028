#!/usr/bin/env python3
"""HOME COMPASS: daily public-data updater. Python standard library only.
Financial/private data is NEVER sent to this updater or committed to the repository.
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from statistics import median
import time
import email.utils
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
DAILY_JSON = ROOT / "data" / "daily.json"
DAILY_JS = ROOT / "data" / "daily.js"
REGIONS_JSON = ROOT / "data" / "regions.json"
NOW = dt.datetime.now(dt.timezone.utc)
HEADERS = {
    "User-Agent": "HomeCompassPersonalDashboard/1.0 (noncommercial; public RSS/APIs)",
    "Accept": "application/rss+xml, application/xml, application/json, text/xml, */*",
}
KEYWORDS = ("주택", "주담대", "대출", "부동산", "가계부채", "DSR", "LTV", "신혼", "디딤돌", "보금자리", "주거", "재건축", "재개발", "도시계획", "교통", "철도", "정비", "공급", "분양", "금리", "모아타운", "GTX", "전세")


def fetch(url: str, timeout=18) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(3_000_000)


def google_rss(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return "https://news.google.com/rss/search?" + params


SOURCES = [
    {
        "name": "금융위원회 보도자료 RSS", "topic": "finance", "source": "금융위원회",
        "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
    },
    {
        "name": "금융위원회 공식자료 탐색", "topic": "finance", "source": "뉴스 검색 · fsc.go.kr",
        "url": google_rss("site:fsc.go.kr (주택담보대출 OR DSR OR LTV OR 가계대출)"),
    },
    {
        "name": "국토교통부 공식자료 탐색", "topic": "housing", "source": "뉴스 검색 · molit.go.kr",
        "url": google_rss("site:molit.go.kr (주택 OR 부동산 OR 주택공급 OR 신혼부부)"),
    },
    {
        "name": "서울시 도시계획 공식자료 탐색", "topic": "development", "source": "뉴스 검색 · seoul.go.kr",
        "url": google_rss("site:seoul.go.kr (도시계획 OR 재개발 OR 정비사업 OR 철도 OR 모아타운)"),
    },
    {
        "name": "은행연합회 공식자료 탐색", "topic": "bank", "source": "뉴스 검색 · kfb.or.kr",
        "url": google_rss("site:kfb.or.kr (주택담보대출 OR 대출금리 OR 금리공시)"),
    },
]


def parse_feed(raw: bytes, config: dict) -> list[dict]:
    root = ET.fromstring(raw)
    elements = root.findall(".//item")
    if not elements:
        elements = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    items = []
    for node in elements:
        def tag(name):
            return (node.findtext(name) or node.findtext("{http://www.w3.org/2005/Atom}" + name) or "").strip()
        title = html.unescape(re.sub(r"\s+", " ", tag("title"))).strip()
        link = tag("link")
        if not link:
            lnk = node.find("{http://www.w3.org/2005/Atom}link")
            link = lnk.get("href", "") if lnk is not None else ""
        published = tag("pubDate") or tag("published") or tag("updated")
        if not title or not link.startswith("http"):
            continue
        if not any(k.lower() in title.lower() for k in KEYWORDS):
            continue
        try:
            timestamp = email.utils.parsedate_to_datetime(published)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        except Exception:
            try:
                timestamp = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
            except Exception:
                timestamp = NOW
        if timestamp < NOW - dt.timedelta(days=120) or timestamp > NOW + dt.timedelta(days=2):
            continue
        identity = hashlib.sha1((title + "|" + link).encode("utf-8")).hexdigest()[:18]
        items.append({
            "id": identity,
            "title": title[:260],
            "url": link,
            "date": timestamp.strftime("%Y-%m-%d"),
            "topic": config["topic"],
            "source": config["source"],
            "new": False,
        })
    return items


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def months_back(n=3):
    year, month = NOW.year, NOW.month
    result = []
    for _ in range(n):
        result.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return result


def size_band(sqm):
    if sqm < 60:
        return "60㎡ 미만"
    if sqm < 85:
        return "60~84㎡"
    if sqm < 115:
        return "85~114㎡"
    return "115㎡ 이상"


def request_month(region, mon, key):
    """Fetch all pages for one region and one contract month. Partial pages are not accepted."""
    code = region['code']
    total_rows, collected = None, []
    page, page_limit, page_size = 1, 50, 1000
    while page <= page_limit:
        args = urllib.parse.urlencode({
            'serviceKey': key, 'LAWD_CD': code, 'DEAL_YMD': mon,
            'numOfRows': page_size, 'pageNo': page})
        url = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade?' + args
        last_exc = None
        for attempt in range(3):
            try:
                root = ET.fromstring(fetch(url, timeout=25))
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep((attempt + 1) * 0.8)
        if last_exc is not None:
            # Do not print URL or API secret on errors.
            raise RuntimeError(f'{type(last_exc).__name__} while fetching {code}/{mon} page={page}')
        code_result = root.findtext('.//resultCode')
        if code_result and code_result.strip() not in ('00', '000'):
            raise RuntimeError(f'API result code {code_result[:18]} {code}/{mon}')
        try:
            total_rows = int(root.findtext('.//totalCount') or '0')
        except ValueError:
            raise RuntimeError('Invalid API totalCount')
        page_items = root.findall('.//item')
        if total_rows > 0 and not page_items:
            raise RuntimeError('Empty page with nonempty totalCount')
        for item in page_items:
            def get(*tags):
                return next((str(item.findtext(tag)).strip() for tag in tags if item.findtext(tag)), '')
            if get('cdealDay'):
                continue
            amount = int(re.sub(r'[^0-9]', '', get('dealAmount')) or 0)
            area = float(get('excluUseAr', 'excluUseArea') or 0)
            apt = get('aptNm', 'apartmentName')
            if amount <= 0 or area <= 0 or not apt:
                continue
            y, m, d = get('dealYear'), get('dealMonth'), get('dealDay')
            try:
                contract_day = f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
            except (ValueError, TypeError):
                continue
            collected.append({'region': region['name'], 'code': code, 'apt': apt,
                              'date': contract_day, 'price': amount,
                              'sqm': round(area, 2), 'floor': get('floor'),
                              'dealId': get('slerGbn', 'rgstDate')})
        if page * page_size >= total_rows:
            break
        page += 1
    if total_rows is not None and page * page_size < total_rows:
        raise RuntimeError(f'Pagination limit reached {code}/{mon}: total={total_rows}')
    # Keep every reported transaction, including apparently identical contracts.
    # A building, day, price, area and floor combination is not a unique contract ID.
    return collected


def market_snapshot(deals, regions, months, failures):
    by_region, grouped = defaultdict(list), defaultdict(list)
    for x in deals:
        by_region[x['region']].append(x)
        grouped[(x['region'], x['date'][:7])].append(x)
    market = []
    for region in regions:
        name = region['name']
        values = by_region[name]
        month_rows = []
        for mon in months:
            chosen = grouped[(name, f'{mon[:4]}-{mon[4:]}')]
            bands = []
            for label in ('60㎡ 미만', '60~84㎡', '85~114㎡', '115㎡ 이상'):
                prices = [x['price'] for x in chosen if size_band(x['sqm']) == label]
                bands.append({'band': label, 'count': len(prices),
                              'median': round(median(prices)) if prices else None})
            month_rows.append({'month': f'{mon[:4]}-{mon[4:]}', 'count': len(chosen),
                               'bands': bands,
                               'complete': (region['code'], mon) not in failures})
        recent = [x for x in values if x['date'][:7] == f'{months[0][:4]}-{months[0][4:]}']
        market.append({'region': name, 'metro': region['metro'], 'code': region['code'],
                       'count': len(values), 'months': month_rows,
                       'currentMonthCount': len(recent),
                       'complete': all((region['code'], m) not in failures for m in months)})
    return market


def get_trades() -> tuple[list[dict], list[dict], dict]:
    key = os.getenv('MOLIT_SERVICE_KEY', '').strip()
    regions = read_json(REGIONS_JSON, [])
    months = months_back(3)
    if not key:
        return [], [], {'name': '국토부 실거래 API (인증키 미설정)', 'ok': False,
                         'requested': 0, 'complete': 0, 'failed': 0}
    if not regions:
        return [], [], {'name': '국토부 실거래 API (지역 미설정)', 'ok': False,
                         'requested': 0, 'complete': 0, 'failed': 0}
    for region in regions:
        if not re.fullmatch(r'\d{5}', str(region.get('code',''))):
            raise ValueError('Invalid 5-digit region code in regions.json')
    tasks = [(region, mon) for region in regions for mon in months]
    deals, failed = [], set()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(request_month, region, mon, key): (region, mon)
                   for region, mon in tasks}
        for future in as_completed(futures):
            region, mon = futures[future]
            try:
                deals.extend(future.result())
            except Exception as ex:
                failed.add((region['code'], mon))
                print(f'Trade API failed: {region["name"]}/{mon} {type(ex).__name__}: {str(ex)[:90]}',
                      file=sys.stderr)
    # Sample for compact page view. Regional stats are computed from ALL successfully fetched pages.
    sample = sorted(deals, key=lambda x: (x['date'], x['region']), reverse=True)[:1800]
    summary = market_snapshot(deals, regions, months, failed)
    ok_count = len(tasks) - len(failed)
    return sample, summary, {
        'name': f'국토부 실거래 API: {len(regions)}개 지역 / {ok_count}/{len(tasks)} 지역·월 조회 성공',
        'ok': not failed and bool(deals), 'requested': len(tasks), 'complete': ok_count,
        'failed': len(failed), 'total_trades': len(deals),
        'note': '최근 3개월 신고된 거래 기준. 거래취소·중복·신고지연 및 면적구성 차이 주의.'
    }


# Detection only: headlines are not evidence of benefits or price appreciation.
REGIONS = (
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
    "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구",
    "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구", "광명시",
    "김포시", "고양시", "파주시", "부천시", "안양시", "군포시", "과천시", "의왕시", "하남시",
    "성남시", "남양주시", "구리시", "시흥시", "안산시", "화성시", "수원시", "용인시",
    "평택시", "안성시", "오산시", "광주시", "의정부시", "양주시", "동두천시", "포천시",
    "인천 서구", "인천 연수구", "인천 부평구", "인천 계양구", "인천 미추홀구",
)


def detect_signals(news: list[dict]) -> list[dict]:
    grouped = {}
    for item in news:
        if item.get("topic") not in ("development", "housing"):
            continue
        title = item.get("title", "")
        for region in REGIONS:
            if region in title:
                grouped.setdefault(region, []).append(item)
    signals = []
    for region, items in grouped.items():
        text = " ".join(x["title"] for x in items)
        if any(k in text for k in ("지연", "취소", "중단", "무산")):
            stage = "지연·취소 표현 포함"
        elif any(k in text for k in ("착공", "준공", "개통")):
            stage = "착공·준공·개통 표현 포함"
        elif any(k in text for k in ("인가", "고시", "확정")):
            stage = "인가·고시·확정 표현 포함"
        else:
            stage = "발표·계획 단계 확인 필요"
        signals.append({"region": region, "count": len(items), "stage": stage, "url": items[0]["url"]})
    return sorted(signals, key=lambda x: (-x["count"], x["region"]))[:15]


def ai_brief(news: list[dict]) -> str:
    """Optional API summary; PUBLIC headlines only; no financial inputs involved."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or not news:
        return ""
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    lines = "\n".join(f"- {n['date']} {n['source']}: {n['title']} ({n['url']})" for n in news[:20])
    payload = {
        "model": model,
        "instructions": (
            "당신은 한국 주택 구매 계획을 위한 공공정보 요약자입니다. "+
            "제목과 링크만 제공되므로 시행 여부, 규정 숫자, 수혜 지역을 지어내지 마세요. "+
            "새로 발표된 사항과 검토·계획을 구별하고, 결론에 '원문 확인 필요'를 명시하세요. "+
            "제목에 없는 사실 단정 금지. 한국어로 6문장 이내. 투자권유 금지."
        ),
        "input": "다음 공개된 공지의 제목들을 주제별로 요약하세요.\n" + lines,
        "max_output_tokens": 550,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        result = json.loads(urllib.request.urlopen(request, timeout=30).read().decode("utf-8"))
        segments = [c.get("text", "") for output in result.get("output", []) for c in output.get("content", []) if c.get("type") == "output_text"]
        return "\n".join(segments).strip()[:2000]
    except Exception as ex:
        print("Optional AI brief failed:", type(ex).__name__, str(ex)[:200], file=sys.stderr)
        return ""


def main():
    old = read_json(DAILY_JSON, {})
    old_news = old.get("news", [])
    had_prior_run = bool(old.get("generated_at"))
    old_ids = {x.get("id") for x in old_news}
    found, health = [], []
    for source in SOURCES:
        try:
            fresh = parse_feed(fetch(source["url"]), source)
            found.extend(fresh)
            health.append({"name": source["name"] + f" ({len(fresh)}건)", "ok": True})
        except Exception as ex:
            print("News source error", source["name"], type(ex).__name__, str(ex)[:300], file=sys.stderr)
            health.append({"name": source["name"] + " (수집 실패)", "ok": False})
    # Preserve last known items during temporary source outages.
    for old_item in old_news:
        if old_item.get("date", "") >= (NOW - dt.timedelta(days=120)).strftime("%Y-%m-%d"):
            found.append(old_item)
    seen, news = set(), []
    for item in sorted(found, key=lambda x: x.get("date", ""), reverse=True):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        item["new"] = had_prior_run and item["id"] not in old_ids
        news.append(item)
    news = news[:120]
    if not any(s["ok"] for s in health):
        health.append({"name": "수집 실패: 원문 링크 확인 필요", "ok": False})
    trades, market, trade_health = get_trades()
    health.append(trade_health)
    # Preserve last known values during total API outage, without claiming a fresh market update.
    if not market and old.get('market'):
        market = old['market']
        trades = old.get('trades', [])
    # Historical monthly snapshot (bounded 24 months); no personal data or daily raw deal dumps.
    history_file = ROOT / 'data' / 'market-history.json'
    history = read_json(history_file, {'months': []})
    current_month = NOW.strftime('%Y-%m')
    if market and trade_health['complete'] > 0:
        snapshots = [x for x in history.get('months', []) if x.get('month') != current_month]
        snapshots.append({'month': current_month, 'as_of': NOW.strftime('%Y-%m-%d'),
                          'regions': [{'region': x['region'], 'count': x['count'],
                                       'months': x['months']} for x in market]})
        history = {'months': sorted(snapshots, key=lambda x: x['month'])[-24:]}
        history_file.write_text(json.dumps(history, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    summary = ai_brief(news) if any(x["new"] for x in news) or not old.get("ai_summary") else old["ai_summary"]
    obj = {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "news": news,
        "trades": trades,
        "market": market,
        "market_as_of": NOW.strftime("%Y-%m-%d") if trade_health["complete"] else old.get("market_as_of"),
        "signals": detect_signals(news),
        "health": health,
        "ai_summary": summary,
        "ai_enabled": bool(os.getenv("OPENAI_API_KEY")),
    }
    DAILY_JSON.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    DAILY_JS.write_text("// Public daily data only. No personal financial records.\nwindow.HOME_PULSE_DATA = " + json.dumps(obj, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Updated at {obj['generated_at']}; news={len(news)}; sample_trades={len(trades)}; regions={len(market)}; sources_success={sum(x['ok'] for x in health)}/{len(health)}")


if __name__ == "__main__":
    main()