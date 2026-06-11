import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_IDS = [
    os.environ["CHAT_ID"],
    os.environ.get("CHAT_ID_2", ""),
]
CHAT_IDS = [c for c in CHAT_IDS if c]
API_KEY = os.environ["DATA_API_KEY"]

# ✅ 관심 키워드 (테마/서비스명/설명에서 매칭)
KEYWORDS = [
    "지원사업", "지원금", "복지서비스", "혜택", "바우처", "수당", "장려금", "급여", "연금",
    "환급", "감면", "면제", "할인", "쿠폰", "포인트", "금융지원", "이자지원",
    "생활지원", "생계지원", "주거지원", "의료지원", "돌봄지원", "긴급지원",
    "민생지원", "민생안정", "생활안정", "추가지원", "특별지원",
    "대상자", "신청", "접수", "모집", "지급", "현금지급", "현금",
    "전국민", "전 국민", "누구나",
    "청년", "청년월세", "청년도약계좌", "청년주거", "청년지원", "구직", "취업지원",
    "출산", "육아", "보육", "부모급여", "아동수당", "양육수당", "아이돌봄", "다자녀", "임산부",
    "노인", "기초연금", "노인일자리", "독거노인", "치매", "장기요양",
    "장애인", "장애수당", "장애연금", "활동지원", "발달장애", "이동지원",
    "한부모", "다문화", "위기가정", "저소득층", "취약계층", "위기가구", "소득지원",
    "소상공인", "자영업자", "근로장려금", "실업급여", "고용지원", "특고", "프리랜서",
    "에너지", "에너지바우처", "전기요금", "도시가스", "난방비", "수도요금",
    "통신비", "교통비", "지역화폐", "문화누리",
    "무료", "무상", "선착순",
]

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_len = 4000
    chunks = [message[i:i+max_len] for i in range(0, len(message), max_len)]
    for chat_id in CHAT_IDS:
        for chunk in chunks:
            requests.post(url, data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            })


def get_welfare_list():
    """중앙부처 복지서비스 전체 목록 조회"""
    all_items = []
    try:
        # 전체 데이터 조회 (최대 500건)
        params = {
            "serviceKey": API_KEY,
            "pageNo": "1",
            "numOfRows": "500",
            "srchKeyCode": "003",   # 핵심 파라미터!
        }
        res = requests.get(URL, params=params, timeout=20)
        soup = BeautifulSoup(res.content, "xml")
        all_items = soup.find_all("servList")
    except Exception as e:
        print(f"API 오류: {e}")
    return all_items


def parse_recent(items, days=7):
    """최근 등록된 서비스 + 키워드 매칭"""
    results = []
    today = datetime.now()

    for item in items:
        servNm = item.find("servNm")
        servDgst = item.find("servDgst")
        thema = item.find("intrsThemaArray")
        dept = item.find("jurMnofNm")
        link = item.find("servDtlLink")
        provide = item.find("srvPvsnNm")
        cycle = item.find("sprtCycNm")
        regDate = item.find("svcfrstRegTs")

        title = servNm.get_text(strip=True) if servNm else ""
        desc = servDgst.get_text(strip=True) if servDgst else ""
        thema_txt = thema.get_text(strip=True) if thema else ""
        dept_txt = dept.get_text(strip=True) if dept else ""
        link_txt = link.get_text(strip=True) if link else ""
        provide_txt = provide.get_text(strip=True) if provide else ""
        reg_txt = regDate.get_text(strip=True) if regDate else ""

        if not title:
            continue

        # 키워드 매칭
        search_text = f"{title} {desc} {thema_txt}"
        if not any(kw in search_text for kw in KEYWORDS):
            continue

        entry = f"• *{title}*"
        if dept_txt:
            entry += f"\n  🏛 {dept_txt}"
        if thema_txt:
            entry += f"\n  🏷 {thema_txt}"
        if provide_txt:
            entry += f"\n  💰 {provide_txt}"
        if desc:
            entry += f"\n  📝 {desc[:120]}"
        if link_txt:
            entry += f"\n  🔗 {link_txt}"
        results.append(entry)

    return results


def main():
    today = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    day_map = {
        "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
        "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"
    }
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    msg = f"🌅 *{today} 정부 복지정책 모닝 브리핑*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    items = get_welfare_list()
    results = parse_recent(items)

    if results:
        msg += f"📋 *[중앙부처 복지서비스]* 키워드 매칭 {len(results)}건\n\n"
        # 너무 많으면 상위 15건만
        msg += "\n\n".join(results[:15]) + "\n\n"
        if len(results) > 15:
            msg += f"...외 {len(results)-15}건 더 있음\n\n"
    else:
        msg += "오늘은 키워드 매칭 복지서비스가 없습니다.\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔍 전체 {len(items)}건 중 {len(results)}건 매칭 | 복지로 API"

    send_telegram(msg)
    print(f"✅ 전송 완료 - 전체 {len(items)}건, 매칭 {len(results)}건")


if __name__ == "__main__":
    main()
