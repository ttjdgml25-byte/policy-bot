# -*- coding: utf-8 -*-
"""복지로 상세 API 전체 필드 확인 — 신청기한 필드를 찾는다."""
import os
import requests
from bs4 import BeautifulSoup

KEY = os.environ.get("DATA_API_KEY", "")
BASE = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
LIST = BASE + "/NationalWelfarelistV001"
DETAIL = BASE + "/NationalWelfaredetailedV001"


def get(url, params, timeout=40):
    p = dict(params)
    p["serviceKey"] = KEY
    r = requests.get(url, params=p, timeout=timeout)
    return BeautifulSoup(r.content, "xml"), r


if __name__ == "__main__":
    print("=== 1) 목록 API 상태 ===")
    soup, r = get(LIST, {"pageNo": "1", "numOfRows": "30", "srchKeyCode": "003"})
    print(f"HTTP {r.status_code} / {len(r.content)} bytes")
    for t in ["resultCode", "resultMsg", "totalCount"]:
        el = soup.find(t)
        if el:
            print(f"  {t} = {el.get_text(strip=True)}")
    rows = soup.find_all("servList")
    print(f"  servList {len(rows)}건")

    ids = []
    for it in rows:
        sid = it.find("servId")
        nm = it.find("servNm")
        if sid is not None:
            ids.append((sid.get_text(strip=True), nm.get_text(strip=True) if nm else ""))

    print("\n=== 2) 상세 API 전체 필드 (앞 3건) ===")
    for sid, nm in ids[:3]:
        soup, r = get(DETAIL, {"callTp": "D", "servId": sid})
        print(f"\n--- {sid} {nm[:28]} / HTTP {r.status_code} ---")
        root = soup.find("wantedDtl") or soup.find("response") or soup
        seen = 0
        for el in root.find_all():
            if el.find_all():
                continue
            val = el.get_text(strip=True)
            if not val:
                continue
            print(f"    {el.name:<22} = {val[:110]}")
            seen += 1
            if seen > 45:
                print("    ...")
                break

    print("\n=== 3) 날짜/기한처럼 보이는 필드만 재확인 ===")
    import re
    for sid, nm in ids[:8]:
        soup, r = get(DETAIL, {"callTp": "D", "servId": sid})
        hits = []
        for el in soup.find_all():
            if el.find_all():
                continue
            v = el.get_text(strip=True)
            if not v:
                continue
            if re.search(r"\d{4}[-.]\d{1,2}|\d{1,2}\s*월\s*\d{1,2}|기한|기간|접수일|마감", v) or \
               re.search(r"Ymd|Dt$|Date|term|Term|기한", el.name):
                hits.append(f"{el.name}={v[:60]}")
        print(f"  {nm[:22]:<24} {' | '.join(hits[:4]) if hits else '(없음)'}")
