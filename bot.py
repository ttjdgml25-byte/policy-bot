import requests
import os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_IDS = [
    os.environ["CHAT_ID"],
    os.environ.get("CHAT_ID_2", ""),
]
CHAT_IDS = [c for c in CHAT_IDS if c]

# ✅ 공공데이터포털 API 키
CENTRAL_KEY = os.environ["BOKJIRO_CENTRAL_KEY"]   # 중앙부처 복지서비스
LOCAL_KEY   = os.environ["BOKJIRO_LOCAL_KEY"]      # 지자체 복지서비스

# ✅ 전체 키워드 목록
KEYWORDS = [
    "지원사업", "지원금", "복지서비스", "혜택", "바우처", "수당", "장려금", "급여", "연금",
    "환급", "감면", "면제", "할인", "쿠폰", "포인트", "금융지원", "이자지원",
    "생활지원", "생계지원", "주거지원", "의료지원", "돌봄지원", "긴급지원",
    "민생지원", "민생안정", "생활안정", "추가지원", "특별지원",
    "대상자", "신청", "접수", "모집", "신청기간", "신청방법", "지급", "지급일정",
    "시행", "추진", "확대", "신설", "개편", "운영", "발표", "안내",
    "보도자료", "공고", "고시", "행정예고", "지침", "시범사업",
    "전국민", "전 국민", "누구나", "전국 대상", "대상 확대",
    "신청 시작", "기간 연장", "추가 모집", "신규사업",
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

# ✅ 관심 지역 (지자체 서비스 필터용)
TARGET_REGIONS = ["서울", "경기", "과천"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}


def get_central_welfare(api_key):
    """중앙부처 복지서비스 목록 조회"""
    results = []
    try:
        url = "https://apis.data.go.kr/B554287/NationalWelfareInformations/NationalWelfarelistInformation"
        params = {
            "serviceKey": api_key,
            "callTp": "L",
            "pageNo": "1",
            "numOfRows": "100",
            "returnType": "json",
        }
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = res.json()

        items = data.get("body", {}).get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        for item in items:
            title = item.get("servNm", "")
            desc = item.get("servDgst", "")[:100]
            target = item.get("tgtrDsc", "")
            dept = item.get("jurMnofNm", "")
            link = item.get("servDtlLink", "")

            if not title:
                continue
            if any(kw in title or kw in desc for kw in KEYWORDS):
                entry = f"• *{title}*"
                if dept:
                    entry += f"\n  🏛 {dept}"
                if target:
                    entry += f"\n  👥 대상: {target[:60]}"
                if desc:
                    entry += f"\n  📝 {desc}"
                if link:
                    entry += f"\n  🔗 {link}"
                results.append(entry)

    except Exception as e:
        print(f"중앙부처 API 오류: {e}")

    return results


def get_local_welfare(api_key):
    """지자체 복지서비스 목록 조회 (서울/경기/과천)"""
    results = []
    try:
        url = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfareInfo"
        params = {
            "serviceKey": api_key,
            "callTp": "L",
            "pageNo": "1",
            "numOfRows": "100",
            "returnType": "json",
        }
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = res.json()

        items = data.get("body", {}).get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        for item in items:
            title = item.get("servNm", "")
            desc = item.get("servDgst", "")[:100]
            region = item.get("sigunguNm", "") or item.get("ctpvNm", "")
            target = item.get("tgtrDsc", "")
            dept = item.get("jurMnofNm", "")
            link = item.get("servDtlLink", "")

            if not title:
                continue

            # 관심 지역 필터
            region_match = any(r in region for r in TARGET_REGIONS)
            keyword_match = any(kw in title or kw in desc for kw in KEYWORDS)

            if region_match and keyword_match:
                entry = f"• *{title}*"
                if region:
                    entry += f"\n  📍 {region}"
                if dept:
                    entry += f"\n  🏛 {dept}"
                if target:
                    entry += f"\n  👥 대상: {target[:60]}"
                if desc:
                    entry += f"\n  📝 {desc}"
                if link:
                    entry += f"\n  🔗 {link}"
                results.append(entry)

    except Exception as e:
        print(f"지자체 API 오류: {e}")

    return results


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
    total_count = 0

    # 중앙부처 복지서비스
    central = get_central_welfare(CENTRAL_KEY)
    if central:
        msg += f"📋 *[중앙부처 복지서비스]*\n"
        msg += "\n\n".join(central[:10]) + "\n\n"  # 최대 10건
        total_count += len(central)

    # 지자체 복지서비스 (서울/경기/과천)
    local = get_local_welfare(LOCAL_KEY)
    if local:
        msg += f"📋 *[서울·경기·과천 복지서비스]*\n"
        msg += "\n\n".join(local[:10]) + "\n\n"  # 최대 10건
        total_count += len(local)

    if total_count == 0:
        msg += "오늘은 새로운 키워드 매칭 정책이 없습니다.\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔍 총 {total_count}건 | 공공데이터포털 API"

    send_telegram(msg)
    print(f"✅ 전송 완료 - {total_count}건")


if __name__ == "__main__":
    main()
