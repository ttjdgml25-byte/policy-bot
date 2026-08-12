# -*- coding: utf-8 -*-
"""문화 API 상세(detail2) 필드 확인 — 가격 정보를 찾는다."""
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("DATA_API_KEY", "")
BASE = "https://apis.data.go.kr/B553457/cultureinfo"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)


def get(path, params):
    p = dict(params)
    p["serviceKey"] = KEY
    r = requests.get(BASE + path, params=p, timeout=30)
    return BeautifulSoup(r.content, "xml"), r


if __name__ == "__main__":
    frm = NOW.strftime("%Y%m%d")
    to = (NOW + timedelta(days=30)).strftime("%Y%m%d")

    print("=== 1) 지역별 짧은 시도명 테스트 ===")
    for sido in ["서울", "경기", "서울특별시", "경기도"]:
        soup, r = get("/area2", {"sido": sido, "PageNo": 1, "numOfRows": 5})
        tc = soup.find("totalCount")
        print(f"  sido='{sido}' -> totalCount={tc.get_text(strip=True) if tc else '?'}")

    print("\n=== 2) 기간별 목록에서 seq 확보 ===")
    soup, _ = get("/period2", {"from": frm, "to": to, "PageNo": 1, "numOfRows": 30})
    seqs = []
    for it in soup.find_all("item"):
        s = it.find("seq")
        a = it.find("area")
        t = it.find("title")
        if s is not None:
            seqs.append((s.get_text(strip=True),
                         a.get_text(strip=True) if a else "",
                         t.get_text(strip=True) if t else ""))
    print(f"  {len(seqs)}건 확보")
    for s, a, t in seqs[:5]:
        print(f"   seq={s} [{a}] {t[:35]}")

    print("\n=== 3) detail2 전체 필드 (앞 3건) ===")
    for s, a, t in seqs[:3]:
        soup, r = get("/detail2", {"seq": s})
        print(f"\n--- seq={s} [{a}] {t[:30]} / HTTP {r.status_code} ---")
        item = soup.find("item")
        if not item:
            print("    item 없음. 원문:", r.content.decode('utf-8','ignore')[:400])
            continue
        for ch in item.find_all(recursive=False):
            val = ch.get_text(strip=True)
            print(f"    {ch.name:<20} = {val[:90]}")
