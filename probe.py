# -*- coding: utf-8 -*-
"""지자체 복지서비스 API 탐색 — 지역 파라미터와 응답 필드를 찾는다."""
import os
import requests
from bs4 import BeautifulSoup

KEY = os.environ.get("DATA_API_KEY", "")
BASE = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
LIST = BASE + "/LcgvWelfarelist"
DETAIL = BASE + "/LcgvWelfaredetailed"


def call(label, url, params, show_body=False):
    p = dict(params)
    p["serviceKey"] = KEY
    try:
        r = requests.get(url, params=p, timeout=40)
        soup = BeautifulSoup(r.content, "xml")
        code = soup.find("resultCode")
        msg = soup.find("resultMsg") or soup.find("errMsg") or soup.find("returnAuthMsg")
        tc = soup.find("totalCount")
        rows = soup.find_all("servList") or soup.find_all("item")
        print(f"[{label}] HTTP {r.status_code} / code={code.get_text(strip=True) if code else '?'} "
              f"/ msg={msg.get_text(strip=True)[:40] if msg else '-'} "
              f"/ total={tc.get_text(strip=True) if tc else '?'} / rows={len(rows)}")
        if show_body:
            body = r.content.decode("utf-8", "ignore")
            if KEY and KEY[:10] in body:
                body = body.replace(KEY, "***")
            print("   원문:", body[:400].replace("\n", " "))
        return rows
    except Exception as e:
        print(f"[{label}] 예외 {type(e).__name__}: {e}")
        return []


if __name__ == "__main__":
    print("=== 1) 기본 호출 ===")
    rows = call("기본", LIST, {"pageNo": "1", "numOfRows": "10"}, show_body=True)

    print("\n=== 2) 첫 항목 전체 필드 ===")
    if rows:
        for ch in rows[0].find_all(recursive=False):
            print(f"   {ch.name:<22} = {ch.get_text(strip=True)[:70]}")
    else:
        print("   항목 없음")

    print("\n=== 3) 지역 파라미터 후보 테스트 (경기 안양) ===")
    cands = [
        {"ctpvNm": "경기도"}, {"ctpvNm": "경기"},
        {"sidoNm": "경기도"}, {"siDoNm": "경기도"},
        {"ctpvNm": "경기도", "sggNm": "안양시"},
        {"ctpvNm": "경기도", "siGunGuNm": "안양시"},
        {"sggNm": "안양시"},
        {"searchWrd": "안양"},
    ]
    for c in cands:
        call(str(c), LIST, dict({"pageNo": "1", "numOfRows": "5"}, **c))

    print("\n=== 4) 상세조회 ===")
    if rows:
        sid = rows[0].find("servId")
        if sid:
            sid = sid.get_text(strip=True)
            p = {"servId": sid, "serviceKey": KEY}
            r = requests.get(DETAIL, params=p, timeout=40)
            soup = BeautifulSoup(r.content, "xml")
            print(f"   servId={sid} HTTP {r.status_code}")
            n = 0
            for el in soup.find_all():
                if el.find_all():
                    continue
                v = el.get_text(strip=True)
                if not v:
                    continue
                print(f"   {el.name:<22} = {v[:70]}")
                n += 1
                if n > 30:
                    print("   ...")
                    break
