# -*- coding: utf-8 -*-
"""
문화·공연·전시·체육 정보 수집 (한국문화정보원 한눈에보는문화정보 API)
- 대상 지역: 서울, 경기 (우선 지역: 과천시, 의왕시, 안양시)
- 실제 응답 필드: serviceName, seq, title, startDate, endDate, place,
                  realmName, area, sigungu, thumbnail, gpsX, gpsY
"""
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr/B553457/cultureinfo"

TARGET_AREAS = ["서울", "경기"]
PRIORITY_SIGUNGU = ["과천시", "의왕시", "안양시"]
CULTURE_PORTAL = "https://www.culture.go.kr"


def _get(path, key, params):
    p = dict(params)
    p["serviceKey"] = key
    try:
        r = requests.get(BASE + path, params=p, timeout=30)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.content, "xml")
    except Exception as e:
        print(f"문화 API 오류({path}): {e}")
        return None


def _parse_items(soup):
    out = []
    if not soup:
        return out
    for it in soup.find_all("item"):
        def g(tag):
            t = it.find(tag)
            return t.get_text(strip=True) if t else ""
        title = g("title")
        if not title:
            continue
        out.append({
            "seq": g("seq"),
            "title": title,
            "realm": g("realmName") or g("serviceName"),
            "place": g("place"),
            "area": g("area"),
            "sigungu": g("sigungu"),
            "start": g("startDate"),
            "end": g("endDate"),
            "thumbnail": g("thumbnail"),
        })
    return out


def _fmt_date(s):
    if len(s) == 8:
        return f"{s[4:6]}.{s[6:8]}"
    return s


def period_label(d):
    st, en = _fmt_date(d["start"]), _fmt_date(d["end"])
    if st and en:
        return f"{st} ~ {en}"
    return st or en or "상시"


def fetch_culture(api_key, days=30, max_pages=8):
    """오늘부터 days일 이내 진행되는 서울·경기 문화행사 수집"""
    if not api_key:
        return []
    now = datetime.now(KST)
    frm = now.strftime("%Y%m%d")
    to = (now + timedelta(days=days)).strftime("%Y%m%d")

    collected, seen = [], set()

    # 1차 시도: 지역별 조회 (시도명 짧은 형태가 정답)
    for sido in TARGET_AREAS:
        soup = _get("/area2", api_key,
                    {"sido": sido, "PageNo": 1, "numOfRows": 100, "sortStdr": 1})
        for d in _parse_items(soup):
            if d["seq"] not in seen:
                seen.add(d["seq"])
                collected.append(d)

    # 2차(보완): 기간별 조회 후 지역 필터 — area2가 비어 있을 때 대비
    if len(collected) < 20:
        for page in range(1, max_pages + 1):
            soup = _get("/period2", api_key,
                        {"from": frm, "to": to, "PageNo": page,
                         "numOfRows": 100, "sortStdr": 1})
            items = _parse_items(soup)
            if not items:
                break
            for d in items:
                if d["area"] in TARGET_AREAS and d["seq"] not in seen:
                    seen.add(d["seq"])
                    collected.append(d)

    # 종료된 행사 제외
    today = frm
    live = [d for d in collected if not d["end"] or d["end"] >= today]

    # 우선 지역 → 그 외 경기 → 서울 순으로 정렬
    def rank(d):
        if d["sigungu"] in PRIORITY_SIGUNGU:
            return (0, PRIORITY_SIGUNGU.index(d["sigungu"]))
        if d["area"] == "경기":
            return (1, 0)
        return (2, 0)

    live.sort(key=rank)
    return live


def pick_daily(items, n=3):
    """날짜 기준 로테이션으로 매일 다른 항목 선정 (우선 지역 우대)"""
    if not items:
        return []
    prio = [d for d in items if d["sigungu"] in PRIORITY_SIGUNGU]
    rest = [d for d in items if d["sigungu"] not in PRIORITY_SIGUNGU]
    pool = prio + rest
    day = datetime.now(KST).timetuple().tm_yday
    start = (day * n) % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(min(n, len(pool)))]


def summary_lines(items, limit=6):
    """브리핑 메시지에 넣을 요약 줄 생성"""
    lines = []
    for d in items[:limit]:
        loc = d["sigungu"] or d["area"]
        lines.append(f"• <b>{d['title']}</b>\n   📍 {loc} {d['place']} · 🗓 {period_label(d)}")
    return lines


if __name__ == "__main__":
    key = os.environ.get("DATA_API_KEY", "")
    got = fetch_culture(key)
    print(f"수집 {len(got)}건")
    for d in got[:15]:
        print(f"  [{d['area']} {d['sigungu']}] {d['realm']} | {d['title']} | "
              f"{period_label(d)} | {d['place']} | thumb={'Y' if d['thumbnail'] else 'N'}")
