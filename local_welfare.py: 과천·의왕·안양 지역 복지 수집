# -*- coding: utf-8 -*-
"""
우리 지역 복지 (과천·의왕·안양) — 한국사회보장정보원 지자체복지서비스 API
중앙부처(461건, 연 1회 갱신)와 달리 전국 4,826건이 실시간으로 갱신된다.
lastModYmd(최종수정일)로 신규·변경을 감지한다.
"""
import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
LIST = BASE + "/LcgvWelfarelist"
DETAIL = BASE + "/LcgvWelfaredetailed"

# 확인 결과 sggNm 단독으로 필터가 동작한다 (안양시 22건)
MY_CITIES = ["과천시", "의왕시", "안양시"]
SNAP_FILE = "local_welfare.json"


def _t(node, tag):
    el = node.find(tag)
    return el.get_text(strip=True) if el else ""


def _get(url, key, params, attempts=3, wait=10):
    for i in range(1, attempts + 1):
        try:
            p = dict(params)
            p["serviceKey"] = key
            r = requests.get(url, params=p, timeout=40)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return BeautifulSoup(r.content, "xml")
        except Exception as e:
            print(f"  · 지자체 API {i}차 실패: {type(e).__name__}: {e}")
            if i < attempts:
                time.sleep(wait)
    return None


def fetch_city(key, sgg, max_pages=3):
    """한 시군구의 복지서비스 목록"""
    out = []
    for page in range(1, max_pages + 1):
        soup = _get(LIST, key, {"sggNm": sgg, "pageNo": str(page), "numOfRows": "100"})
        if not soup:
            break
        rows = soup.find_all("servList")
        if not rows:
            break
        for it in rows:
            sid = _t(it, "servId")
            if not sid:
                continue
            out.append({
                "id": sid,
                "title": _t(it, "servNm"),
                "desc": _t(it, "servDgst"),
                "city": _t(it, "sggNm"),
                "sido": _t(it, "ctpvNm"),
                "dept": _t(it, "bizChrDeptNm"),
                "how": _t(it, "aplyMtdNm"),
                "cycle": _t(it, "sprtCycNm"),
                "provide": _t(it, "srvPvsnNm"),
                "target": _t(it, "trgterIndvdlNmArray"),
                "thema": _t(it, "intrsThemaNmArray"),
                "modified": _t(it, "lastModYmd"),
                "link": _t(it, "servDtlLink"),
            })
        if len(rows) < 100:
            break
        time.sleep(0.3)
    return out


def fetch_all(key):
    """과천·의왕·안양 전체. 실패 시 None"""
    if not key:
        return None
    all_items, ok = [], False
    for city in MY_CITIES:
        got = fetch_city(key, city)
        if got:
            ok = True
            all_items.extend(got)
        print(f"  {city}: {len(got)}건")
        time.sleep(0.3)
    return all_items if ok else None


def enrich(key, items, limit=6):
    """상세조회로 지원대상·지원내용·신청방법·연락처를 채운다"""
    for d in items[:limit]:
        soup = _get(DETAIL, key, {"servId": d["id"]}, attempts=2, wait=5)
        if not soup:
            continue
        d["target_detail"] = _t(soup, "sprtTrgtCn")
        d["criteria"] = _t(soup, "slctCritCn")
        d["benefit"] = _t(soup, "alwServCn")
        d["how_detail"] = _t(soup, "aplyMtdCn")
        # 연락처(코드 010)를 찾는다
        for blk in soup.find_all("wlfareInfoDtlCd"):
            if blk.get_text(strip=True) == "010":
                sib = blk.find_next("wlfareInfoReldCn")
                if sib:
                    d["tel"] = sib.get_text(strip=True)
                break
        time.sleep(0.2)
    return items


# ───────────── 신규·변경 감지 ─────────────
def load_snap():
    try:
        import json
        with open(SNAP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def detect(items):
    """(신규목록, 변경목록, 최초실행여부) 반환하고 스냅샷을 갱신한다"""
    import json
    snap = load_snap()
    known = (snap or {}).get("items", {})
    first = snap is None
    new_list, upd_list, out = [], [], {}
    for d in items:
        prev = known.get(d["id"])
        if prev is None and not first:
            d["flag"] = "new"
            new_list.append(d)
        elif prev and prev.get("modified") and d["modified"] and \
                d["modified"] > prev["modified"]:
            d["flag"] = "updated"
            upd_list.append(d)
        else:
            d["flag"] = ""
        out[d["id"]] = {"title": d["title"], "modified": d["modified"], "city": d["city"]}
    with open(SNAP_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                   "items": out}, f, ensure_ascii=False, indent=1)
    return new_list, upd_list, first


def pick_daily(items, n=3):
    """날짜 기준 로테이션"""
    if not items:
        return []
    pool = sorted(items, key=lambda d: (d["city"], d["id"]))
    day = datetime.now(KST).timetuple().tm_yday
    start = (day * n) % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(min(n, len(pool)))]


if __name__ == "__main__":
    k = os.environ.get("DATA_API_KEY", "")
    items = fetch_all(k)
    print(f"\n총 {len(items or [])}건")
    for d in (items or [])[:25]:
        print(f"  [{d['city']}] {d['title'][:30]:<32} | {d['thema'][:14]:<16} | "
              f"{d['how']:<8} | 수정 {d['modified']}")
