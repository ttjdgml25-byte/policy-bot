# -*- coding: utf-8 -*-
"""
무료·저렴한 문화행사 수집 (한국문화정보원 한눈에보는문화정보 API)
- 대상 지역: 서울, 경기 (우선: 과천시·의왕시·안양시)
- 목록(area2)으로 후보를 받고, 상세(detail2)에서 price를 확인해
  무료 또는 저렴한 행사만 골라낸다.
"""
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr/B553457/cultureinfo"

# 확인 결과 짧은 시도명만 동작한다 (서울 575건 / 경기 125건)
TARGET_AREAS = ["서울", "경기"]
PRIORITY_SIGUNGU = ["과천시", "의왕시", "안양시", "군포시", "성남시", "수원시"]
CHEAP_LIMIT = 10000       # 이 금액 이하면 '저렴'으로 본다


def _get(path, key, params, timeout=30):
    p = dict(params)
    p["serviceKey"] = key
    try:
        r = requests.get(BASE + path, params=p, timeout=timeout)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.content, "xml")
    except Exception as e:
        print(f"문화 API 오류({path}): {e}")
        return None


def _text(node, tag):
    t = node.find(tag)
    return t.get_text(strip=True) if t else ""


def parse_price(txt):
    """관람료 문자열에서 가장 싼 금액을 뽑는다. 무료면 0, 알 수 없으면 None."""
    t = (txt or "").strip()
    if not t:
        return None
    if re.search(r"무료|free", t, re.I) and not re.search(r"유료", t):
        return 0
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", t)
            if len(n.replace(",", "")) >= 3]
    return min(nums) if nums else None


def price_label(d):
    p = d.get("price_num")
    if p == 0:
        return "무료"
    if p is None:
        return d.get("price_txt") or "관람료 문의"
    return f"{p:,}원부터"


def _fmt(s):
    return f"{s[4:6]}.{s[6:8]}" if len(s) == 8 else s


def period_label(d):
    st, en = _fmt(d.get("start", "")), _fmt(d.get("end", ""))
    if st and en:
        return f"{st} ~ {en}"
    return st or en or "상시"


def fetch_candidates(api_key, per_area=100):
    """서울·경기 진행 중 행사 목록"""
    out, seen = [], set()
    today = datetime.now(KST).strftime("%Y%m%d")
    for sido in TARGET_AREAS:
        for page in (1, 2, 3, 4, 5):
            soup = _get("/area2", api_key,
                        {"sido": sido, "PageNo": page, "numOfRows": per_area, "sortStdr": 1})
            if not soup:
                break
            items = soup.find_all("item")
            if not items:
                break
            for it in items:
                seq = _text(it, "seq")
                end = _text(it, "endDate")
                if not seq or seq in seen:
                    continue
                if end and end < today:
                    continue
                seen.add(seq)
                out.append({
                    "seq": seq,
                    "title": _text(it, "title"),
                    "realm": _text(it, "realmName") or _text(it, "serviceName"),
                    "place": _text(it, "place"),
                    "area": _text(it, "area"),
                    "sigungu": _text(it, "sigungu"),
                    "start": _text(it, "startDate"),
                    "end": end,
                    "thumbnail": _text(it, "thumbnail"),
                })
            time.sleep(0.1)
    return out


def enrich(api_key, items, limit=70):
    """상세 조회로 관람료·링크를 채운다 (호출 수 제한)."""
    done = []
    for d in items[:limit]:
        soup = _get("/detail2", api_key, {"seq": d["seq"]}, timeout=20)
        if soup:
            it = soup.find("item")
            if it:
                d["price_txt"] = _text(it, "price")
                d["price_num"] = parse_price(d["price_txt"])
                d["url"] = _text(it, "url")
                d["phone"] = _text(it, "phone")
                d["addr"] = _text(it, "placeAddr")
                if not d.get("thumbnail"):
                    d["thumbnail"] = _text(it, "imgUrl")
        done.append(d)
        time.sleep(0.05)
    return done


# 무료 가능성이 높은 장소·분야 (국공립 시설은 상시 무료가 많다)
FREE_VENUE_HINTS = ["국립", "시립", "도립", "구립", "군립", "미술관", "박물관",
                    "도서관", "문화원", "문화재단", "아트센터", "역사관", "기념관",
                    "센터", "갤러리", "전시관"]
FREE_REALM_HINTS = ["전시", "축제", "미술", "박물", "교육", "체험", "강연", "기타"]


def free_score(d):
    """무료일 가능성 점수 — 높을수록 먼저 상세 조회한다."""
    s = 0
    place = d.get("place", "") or ""
    realm = d.get("realm", "") or ""
    if any(h in place for h in FREE_VENUE_HINTS):
        s += 3
    if any(h in realm for h in FREE_REALM_HINTS):
        s += 2
    if d.get("sigungu") in PRIORITY_SIGUNGU:
        s += 2
    if d.get("area") == "경기":
        s += 1
    return s


def fetch_cheap(api_key, limit=70):
    """무료 또는 저렴한 서울·경기 행사. (cheap_list, 조회건수, 후보수) 반환"""
    if not api_key:
        return [], 0, 0
    cands = fetch_candidates(api_key)
    if not cands:
        return [], 0, 0

    # 무료 가능성이 높은 순으로 정렬해 상세 조회 적중률을 높인다
    cands.sort(key=lambda d: -free_score(d))
    checked = enrich(api_key, cands, limit=limit)

    known = [d for d in checked if d.get("price_num") is not None]
    cheap = [d for d in known if d["price_num"] <= CHEAP_LIMIT]

    def rank(d):
        if d.get("sigungu") in PRIORITY_SIGUNGU:
            return (0, PRIORITY_SIGUNGU.index(d["sigungu"]))
        return (1, 0) if d.get("area") == "경기" else (2, 0)

    cheap.sort(key=lambda d: (d["price_num"], rank(d)))
    print(f"문화행사 후보 {len(cands)}건 / 상세확인 {len(checked)}건 / "
          f"가격확인됨 {len(known)}건 / 무료·저렴 {len(cheap)}건")
    return cheap, len(checked), len(cands)


def summary_lines(items, limit=6):
    lines = []
    for d in items[:limit]:
        loc = d.get("sigungu") or d.get("area")
        tag = "🆓" if d.get("price_num") == 0 else "💸"
        lines.append(f"{tag} <b>{d['title']}</b> — {price_label(d)}\n"
                     f"   📍 {loc} {d.get('place','')} · 🗓 {period_label(d)}")
    return lines


def pick_daily(items, n=2):
    if not items:
        return []
    free = [d for d in items if d.get("price_num") == 0]
    pool = free or items
    day = datetime.now(KST).timetuple().tm_yday
    start = (day * n) % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(min(n, len(pool)))]


if __name__ == "__main__":
    key = os.environ.get("DATA_API_KEY", "")
    got, checked, total = fetch_cheap(key)
    print(f"\n무료·저렴 {len(got)}건")
    for d in got[:20]:
        print(f"  [{d['area']} {d['sigungu']}] {price_label(d):<12} {d['title'][:34]} | "
              f"{d.get('place','')[:20]} | {period_label(d)}")
