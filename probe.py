# -*- coding: utf-8 -*-
"""문화정보 API 응답 구조 탐색용 (1회성). 인증키는 절대 출력하지 않음."""
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("DATA_API_KEY", "")
BASE = "https://apis.data.go.kr/B553457/cultureinfo"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)


def show(label, path, params):
    print("\n" + "=" * 70)
    print(f"[{label}]  GET {path}   params={ {k: v for k, v in params.items()} }")
    print("=" * 70)
    try:
        p = dict(params)
        p["serviceKey"] = KEY
        r = requests.get(BASE + path, params=p, timeout=30)
        print(f"HTTP {r.status_code} / {len(r.content)} bytes")
        body = r.content.decode("utf-8", "ignore")
        # 인증키가 응답에 반사되는 경우 대비해 마스킹
        if KEY and KEY[:10] in body:
            body = body.replace(KEY, "***KEY***")
        print("--- 원문 앞부분 ---")
        print(body[:1200])

        soup = BeautifulSoup(r.content, "xml")
        # 결과코드 확인
        for t in ["resultCode", "resultMsg", "returnAuthMsg", "errMsg", "totalCount"]:
            el = soup.find(t)
            if el:
                print(f"{t} = {el.get_text(strip=True)}")
        # 반복 아이템 후보 찾기
        for cand in ["item", "perforList", "sportList", "cultureList"]:
            items = soup.find_all(cand)
            if items:
                print(f"\n>>> <{cand}> {len(items)}건 발견. 첫 항목 필드:")
                for ch in items[0].find_all(recursive=False):
                    val = ch.get_text(strip=True)
                    print(f"    {ch.name:<24} = {val[:70]}")
                break
        else:
            print("\n>>> 반복 아이템 태그를 못 찾음. 전체 태그 목록:")
            names = []
            for el in soup.find_all():
                if el.name not in names:
                    names.append(el.name)
            print("   ", ", ".join(names[:60]))
    except Exception as e:
        print(f"예외: {e}")


if __name__ == "__main__":
    if not KEY:
        print("DATA_API_KEY 없음")
        raise SystemExit(1)
    frm = NOW.strftime("%Y%m%d")
    to = (NOW + timedelta(days=30)).strftime("%Y%m%d")

    show("기간별", "/period2", {"numOfRows": 5, "PageNo": 1, "from": frm, "to": to, "sortStdr": 1})
    show("지역별-경기", "/area2", {"numOfRows": 5, "PageNo": 1, "sido": "경기도", "sortStdr": 1})
    show("지역별-서울", "/area2", {"numOfRows": 5, "PageNo": 1, "sido": "서울특별시", "sortStdr": 1})
    show("분야별", "/realm2", {"numOfRows": 5, "PageNo": 1, "sortStdr": 1})
