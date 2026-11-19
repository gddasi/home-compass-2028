#!/usr/bin/env python3
"""Update public housing feeds. Never store user savings, balances or personal data."""
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime.now(dt.timezone.utc)
DATA = ROOT / "data"
KEYWORDS = ("주택", "주담대", "대출", "부동산", "가계부채", "dsr", "ltv",
            "신혼", "디딤돌", "보금자리", "주거", "재건축", "재개발",
            "도시계획", "교통", "철도", "정비", "공급", "분양",
            "금리", "모아타운", "gtx", "전세")
REGION_WORDS = ("종로구 중구 용산구 성동구 광진구 동대문구 중랑구 성북구 강북구 "
                "도봉구 노원구 은평구 서대문구 마포구 양천구 강서구 구로구 금천구 "
                "영등포구 동작구 관악구 서초구 강남구 송파구 강동구 광명시 김포시 "
                "고양시 파주시 부천시 안양시 군포시 과천시 의왕시 하남시 성남시 "
                "남양주시 구리시 시흥시 안산시 화성시 수원시 용인시 평택시 오산시 "
                "광주시 의정부시 양주시 인천").split()

def request(url, timeout=20, data=None, headers=None):
    hdr = {"User-Agent": "HomeCompassPersonalDashboard/1.0", "Accept": "application/xml, application/json, */*"}
    hdr.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read(3_000_000)

def google(query):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})

SOURCES = [
    ("금융위원회 공식 RSS", "finance", "금융위원회", "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"),
    ("금융위원회 보도 탐색", "finance", "뉴스검색 · fsc.go.kr", google("site:fsc.go.kr (주택담보대출 OR DSR OR LTV OR 가계대출)")),
    ("국토교통부 정책 탐색", "housing", "뉴스검색 · molit.go.kr", google("site:molit.go.kr (주택 OR 부동산 OR 주택공급 OR 신혼부부)")),
    ("서울시 개발계획 탐색", "development", "뉴스검색 · seoul.go.kr", google("site:seoul.go.kr (도시계획 OR 재개발 OR 정비사업 OR 철도 OR 모아타운)")),
    ("은행연합회 탐색", "bank", "뉴스검색 · kfb.or.kr", google("site:kfb.or.kr (주택담보대출 OR 대출금리 OR 금리공시)"))
]

def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return fallback

def feed_entries(raw, topic, source):
    tree = ET.fromstring(raw)
    nodes = tree.findall(".//item") or tree.findall(".//{http://www.w3.org/2005/Atom}entry")
    output = []
    for node in nodes:
        def get(name):
            return (node.findtext(name) or node.findtext("{http://www.w3.org/2005/Atom}" + name) or "").strip()
        title = html.unescape(re.sub(r"\s+", " ", get("title")))[:260]
        link = get("link")
        if not link:
            n = node.find("{http://www.w3.org/2005/Atom}link")
            link = n.get("href", "") if n is not None else ""
        if not title or not link.startswith(("https://", "http://")):
            continue
        if not any(k in title.lower() for k in KEYWORDS):
            continue
        stamp = get("pubDate") or get("published") or get("updated")
        try:
            day = email.utils.parsedate_to_datetime(stamp)
            if day.tzinfo is None:
                day = day.replace(tzinfo=dt.timezone.utc)
        except Exception:
            try:
                day = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except Exception:
                day = NOW
        if day < NOW - dt.timedelta(days=120) or day > NOW + dt.timedelta(days=2):
            continue
        identity = hashlib.sha1((title + "|" + link).encode("utf-8")).hexdigest()[:18]
        output.append({"id": identity, "title": title, "url": link,
                       "date": day.strftime("%Y-%m-%d"), "topic": topic,
                       "source": source, "new": False})
    return output

def trades():
    key = os.environ.get("MOLIT_SERVICE_KEY", "").strip()
    regions = load_json(DATA / "regions.json", [])
    if not key:
        return [], {"name": "국토부 실거래 API (인증키 미설정)", "ok": False}
    if not regions:
        return [], {"name": "국토부 실거래 API (지역 미설정)", "ok": False}
    months = []
    year, month = NOW.year, NOW.month
    for _ in range(3):
        months.append(f"{year}{month:02d}")
        month -= 1
        if month < 1:
            year, month = year - 1, 12
    found, errors = [], []
    for region in regions[:12]:
        code = str(region.get("code", ""))
        if not re.fullmatch(r"\d{5}", code):
            continue
        for ym in months:
            params = urllib.parse.urlencode({"serviceKey": key, "LAWD_CD": code,
                                             "DEAL_YMD": ym, "pageNo": 1, "numOfRows": 1000})
            url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade?" + params
            try:
                root = ET.fromstring(request(url))
                result_code = root.findtext(".//resultCode")
                if result_code and result_code not in ("00", "000"):
                    raise ValueError("API status " + result_code)
                for item in root.findall(".//item"):
                    def val(*tags):
                        for tag in tags:
                            content = item.findtext(tag)
                            if content:
                                return content.strip()
                        return ""
                    if val("cdealType", "cdealDay"):
                        continue
                    price = float(re.sub(r"[^0-9.]", "", val("dealAmount")) or 0)
                    if price <= 0:
                        continue
                    area = float(val("excluUseAr", "excluUseArea") or 0)
                    y, m, d = val("dealYear"), val("dealMonth"), val("dealDay")
                    date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}" if y and m and d else ym[:4] + "-" + ym[4:] + "-01"
                    found.append({"region": region.get("name", code),
                                  "apt": val("aptNm", "apartmentName"), "date": date,
                                  "price": price, "sqm": area, "floor": val("floor")})
            except Exception as exc:
                errors.append(f"{code}/{ym} {type(exc).__name__}: {exc}")
    for message in errors[:6]:
        print("Trade query:", message, file=sys.stderr)
    unique = {}
    for item in found:
        token = "|".join(str(item[k]) for k in ("region", "apt", "date", "price", "sqm", "floor"))
        unique[token] = item
    output = sorted(unique.values(), key=lambda x: x["date"], reverse=True)[:1000]
    return output, {"name": f"국토부 실거래 API ({len(output)}건)" if output else "국토부 실거래 API (자료 없음)",
                    "ok": bool(output) and not errors}

def signals(news):
    result = []
    for region in REGION_WORDS:
        matched = [n for n in news if n["topic"] in ("development", "housing") and region in n["title"]]
        if not matched:
            continue
        titles = " ".join(n["title"] for n in matched)
        if any(t in titles for t in ("지연", "취소", "중단", "무산")):
            stage = "지연·취소 관련 표현 포함"
        elif any(t in titles for t in ("착공", "준공", "개통")):
            stage = "착공·준공·개통 관련 표현 포함"
        elif any(t in titles for t in ("인가", "고시", "확정")):
            stage = "인가·고시·확정 관련 표현 포함"
        else:
            stage = "계획·발표 단계 확인 필요"
        result.append({"region": region, "count": len(matched),
                       "stage": stage, "url": matched[0]["url"]})
    return sorted(result, key=lambda x: (-x["count"], x["region"]))[:15]

def brief(news):
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or not news:
        return ""
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    lines = "\n".join(f"- {n['date']}: {n['title']} ({n['url']})" for n in news[:20])
    payload = {"model": model,
               "instructions": "한국 신혼집 준비 정책 보도 제목을 한국어 6문장 이내로 요약하세요. 제공된 것은 제목뿐이므로 제도 시행 여부, 금리, 지역 수혜, 숫자를 추측하지 마세요. 마지막에 원문 확인 필요를 명시하세요.",
               "input": lines, "max_output_tokens": 550}
    try:
        raw = request("https://api.openai.com/v1/responses", timeout=30,
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        data = json.loads(raw)
        return "\n".join(c.get("text", "") for o in data.get("output", [])
                         for c in o.get("content", []) if c.get("type") == "output_text")[:2000]
    except Exception as exc:
        print("Optional AI summary failed:", type(exc).__name__, str(exc)[:160], file=sys.stderr)
        return ""

def main():
    old = load_json(DATA / "daily.json", {})
    previous = old.get("news", [])
    old_ids = {entry.get("id") for entry in previous}
    found, health = [], []
    for name, topic, source, url in SOURCES:
        try:
            items = feed_entries(request(url), topic, source)
            found.extend(items)
            health.append({"name": f"{name} ({len(items)}건)", "ok": True})
        except Exception as exc:
            health.append({"name": name + " (수집 실패)", "ok": False})
            print(name + ":", type(exc).__name__, str(exc)[:160], file=sys.stderr)
    cutoff = (NOW - dt.timedelta(days=120)).strftime("%Y-%m-%d")
    found.extend(item for item in previous if item.get("date", "") >= cutoff)
    unique = {}
    for item in sorted(found, key=lambda x: x.get("date", ""), reverse=True):
        if item.get("id") and item["id"] not in unique:
            unique[item["id"]] = item
    news = list(unique.values())[:120]
    for item in news:
        item["new"] = bool(old.get("generated_at")) and item["id"] not in old_ids
    recent, trade_health = trades()
    health.append(trade_health)
    if not recent and old.get("trades"):
        recent = old["trades"]
    summary = brief(news) if any(x["new"] for x in news) or not old.get("ai_summary") else old["ai_summary"]
    payload = {"generated_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
               "news": news, "trades": recent, "signals": signals(news),
               "health": health, "ai_summary": summary,
               "ai_enabled": bool(os.environ.get("OPENAI_API_KEY"))}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "daily.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA / "daily.js").write_text("// Public housing data only; no private financial records.\nwindow.HOME_PULSE_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("Refreshed", payload["generated_at"], "news", len(news), "trades", len(recent))

if __name__ == "__main__":
    main()
