# -*- coding: utf-8 -*-
"""
생활 혜택 캘린더 — 소득 기준 없이 일반 시민 누구나 받을 수 있는 혜택
- 문화가 있는 날 (매월 둘째·마지막 수요일 영화 할인)
- 경기지역화폐 충전 인센티브 (과천·의왕·안양) — 경기지역화폐 공식 표를 실시간 조회
- K-패스 대중교통비 환급
- 청년 문화예술패스
"""
import calendar
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
GMONEY_URL = "https://www.gmoney.or.kr/base/gmoney/insentive/index?menuLevel=2&menuNo=72"
MY_CITIES = ["과천시", "의왕시", "안양시"]

# 조회 실패 시 사용할 최근 확인값 (2026-08 기준)
GMONEY_FALLBACK = {
    "과천시": {"type": "추가형", "charge": "200,000", "rate": "8", "cap": "16,000", "tel": "02-3677-2449"},
    "의왕시": {"type": "할인형", "charge": "300,000", "rate": "8", "cap": "24,000", "tel": "031-345-2354"},
    "안양시": {"type": "추가형", "charge": "200,000", "rate": "8", "cap": "16,000", "tel": "031-8045-2955"},
}


# ───────────── 문화가 있는 날 ─────────────
def culture_days(year, month):
    """해당 월의 둘째 수요일과 마지막 수요일"""
    weds = [d for d in range(1, calendar.monthrange(year, month)[1] + 1)
            if datetime(year, month, d).weekday() == 2]
    out = []
    if len(weds) >= 2:
        out.append(weds[1])
    if weds and weds[-1] not in out:
        out.append(weds[-1])
    return out


def culture_day_status(now=None):
    """오늘이 문화가 있는 날인지, 아니면 다음 날짜가 언제인지"""
    now = now or datetime.now(KST)
    days = culture_days(now.year, now.month)
    if now.day in days:
        return {"today": True, "date": now.date(), "days_left": 0}
    upcoming = [d for d in days if d > now.day]
    if upcoming:
        d = upcoming[0]
        return {"today": False, "date": datetime(now.year, now.month, d).date(),
                "days_left": d - now.day}
    # 다음 달 첫 해당일
    ny, nm = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    nd = culture_days(ny, nm)
    if not nd:
        return None
    target = datetime(ny, nm, nd[0]).date()
    return {"today": False, "date": target, "days_left": (target - now.date()).days}


# ───────────── 경기지역화폐 인센티브 ─────────────
def fetch_gmoney(timeout=20):
    """경기지역화폐 인센티브 표에서 과천·의왕·안양 정보를 가져온다."""
    result = {}
    try:
        r = requests.get(GMONEY_URL, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        for tr in soup.select("table tr"):
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue
            city = tds[0].get_text(strip=True)
            if city not in MY_CITIES:
                continue
            result[city] = {
                "type": tds[1].get_text(strip=True),
                "charge": tds[2].get_text(strip=True),
                "rate": tds[3].get_text(strip=True).replace("%", "").strip(),
                "cap": tds[4].get_text(strip=True),
                "period": tds[5].get_text(strip=True),
                "tel": tds[6].get_text(strip=True),
            }
    except Exception as e:
        print(f"지역화폐 조회 실패: {e}")
    for city in MY_CITIES:
        if city not in result:
            fb = dict(GMONEY_FALLBACK.get(city, {}))
            if fb:
                fb["period"] = "(최근 확인값)"
                result[city] = fb
    return result


# ───────────── 상시 혜택 ─────────────
STANDING = [
    {"name": "K-패스 대중교통비 환급",
     "desc": "월 15회 이상 대중교통 이용 시 요금의 20~53%를 다음 달에 환급. 소득 기준 없이 누구나, 청년(19~34세)은 30% 환급.",
     "how": "K-패스 앱 또는 korea-pass.kr에서 카드 발급·등록",
     "url": "https://korea-pass.kr"},
    {"name": "청년 문화예술패스",
     "desc": "19세 청년에게 공연·전시 관람비 최대 15만원 지원. 소득 무관.",
     "how": "문화예술패스 누리집에서 신청 후 인터파크·예스24 등에서 사용",
     "url": "https://www.문화예술패스.kr"},
    {"name": "국가건강검진 (무료)",
     "desc": "20세 이상이면 2년에 한 번 무료 건강검진. 소득·직장 여부와 무관하게 모든 국민 대상이며, "
             "20·30대도 해당됩니다. 홀수년생은 홀수해, 짝수년생은 짝수해에 받습니다.",
     "how": "건강보험공단 홈페이지·앱에서 대상 조회 후 가까운 검진기관 예약",
     "url": "https://www.nhis.or.kr"},
    {"name": "청년 국가건강검진 (20~34세)",
     "desc": "직장가입자가 아닌 20~34세 청년도 2년마다 무료 검진 대상. "
             "우울증 검사와 혈액·혈압 검사가 포함됩니다.",
     "how": "건강보험공단 앱에서 대상 확인 후 검진기관 예약",
     "url": "https://www.nhis.or.kr"},
    {"name": "근로자 휴가지원사업",
     "desc": "근로자가 20만원을 적립하면 기업과 정부가 20만원을 더해 40만원의 국내 여행 적립금을 지원.",
     "how": "회사가 참여 신청해야 이용 가능 · 매년 상반기 모집",
     "url": "https://www.worker-holiday.kr"},
]


# ───────────── 메시지 조립 ─────────────
def build_message(now=None):
    now = now or datetime.now(KST)
    lines = []

    # 1) 문화가 있는 날
    cd = culture_day_status(now)
    if cd:
        if cd["today"]:
            lines.append("🎬 <b>오늘은 «문화가 있는 날»입니다!</b>\n"
                         "   오후 5~9시 영화 관람료 <b>성인 1만원 / 청소년 8천원</b>\n"
                         "   CGV·롯데시네마·메가박스 등 전국 주요 영화관\n"
                         "   💡 소득 기준 없이 누구나 · 예매 시 자동 적용")
        elif cd["days_left"] <= 3:
            lines.append(f"🎬 <b>{cd['date'].month}월 {cd['date'].day}일(수)은 «문화가 있는 날»</b> — {cd['days_left']}일 남았어요\n"
                         "   오후 5~9시 영화 성인 1만원 / 청소년 8천원")

    # 2) 지역화폐 (월초에 강조 — 예산 소진되면 종료)
    if now.day <= 7:
        gm = fetch_gmoney()
        if gm:
            body = [f"💳 <b>이번 달 지역화폐 충전 혜택</b> (예산 소진 시 조기 종료)"]
            for city in MY_CITIES:
                d = gm.get(city)
                if not d:
                    continue
                body.append(f"   • <b>{city}</b> {d['charge']}원 충전 시 "
                            f"<b>{d['rate']}%</b> 적립 (최대 {d['cap']}원) · {d['type']}")
            body.append("   💡 충전은 각 시 지역화폐 앱에서 · 소득 기준 없음")
            lines.append("\n".join(body))

    # 3) 상시 혜택 — 날짜 기준 로테이션으로 하루 1건
    idx = now.timetuple().tm_yday % len(STANDING)
    s = STANDING[idx]
    lines.append(f"🎁 <b>{s['name']}</b>\n   {s['desc']}\n   📝 {s['how']}\n   🔗 {s['url']}")

    if not lines:
        return ""
    msg = "✨ <b>누구나 받을 수 있는 생활 혜택</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "\n\n".join(lines)
    return msg


if __name__ == "__main__":
    print(build_message())
    print("\n--- 문화가 있는 날 (이번 달) ---")
    n = datetime.now(KST)
    print(culture_days(n.year, n.month), culture_day_status(n))
    print("\n--- 지역화폐 ---")
    for k, v in fetch_gmoney().items():
        print(" ", k, v)
