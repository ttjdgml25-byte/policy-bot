import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

# ✅ 크롤링 사이트 목록
SITES = [
    {
        "name": "정책브리핑",
        "url": "https://www.korea.kr/news/policyNewsView.do",
        "list_selector": ".news-list li",
        "title_selector": ".tit",
        "link_prefix": "https://www.korea.kr"
    },
    {
        "name": "복지로",
        "url": "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do",
        "list_selector": ".welfare-list li",
        "title_selector": ".tit",
        "link_prefix": "https://www.bokjiro.go.kr"
    },
    {
        "name": "복지멤버십(정부24 복지서비스)",
        "url": "https://plus.gov.kr/",
        "list_selector": ".board-list li, .news-list li, .list-item, article",
        "title_selector": ".tit, .title, h3, h4",
        "link_prefix": "https://plus.gov.kr"
    },
    {
        "name": "가족센터(familynet)",
        "url": "https://www.familynet.or.kr/web/index.do",
        "list_selector": ".board-list li, .news-wrap li, .list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.familynet.or.kr"
    },
    {
        "name": "서울 복지포털(wis.seoul)",
        "url": "https://wis.seoul.go.kr/",
        "list_selector": ".board-list li, .welfare-list li, .list-wrap li",
        "title_selector": ".tit, .subject, a",
        "link_prefix": "https://wis.seoul.go.kr"
    },
    {
        "name": "Work24(고용24)",
        "url": "https://www.work24.go.kr/cm/main.do",
        "list_selector": ".board-list li, .news-list li, .list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.work24.go.kr"
    },
    {
        "name": "창업진흥원(K-Startup)",
        "url": "https://www.k-startup.go.kr/",
        "list_selector": ".board-list li, .notice-list li, .list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.k-startup.go.kr"
    },
    {
        "name": "청년센터",
        "url": "https://www.youthcenter.go.kr/",
        "list_selector": ".board-list li, .news-list li, .notice li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.youthcenter.go.kr"
    },
]

# ✅ 전체 키워드 목록
KEYWORDS = [
    # 지원 유형
    "지원사업", "지원금", "복지서비스", "혜택", "바우처", "수당", "장려금", "급여", "연금",
    "환급", "감면", "면제", "할인", "쿠폰", "포인트", "금융지원", "이자지원",
    "생활지원", "생계지원", "주거지원", "의료지원", "돌봄지원", "긴급지원",
    "민생지원", "민생안정", "생활안정", "추가지원", "특별지원",
    # 신청/공고
    "대상자", "신청", "접수", "모집", "신청기간", "신청방법", "지급", "지급일정",
    "시행", "추진", "확대", "신설", "개편", "운영", "발표", "안내",
    "보도자료", "공고", "고시", "행정예고", "지침", "시범사업",
    "종합계획", "기본계획",
    # 대상
    "전국민", "전 국민", "누구나", "전국 대상", "대상 확대",
    "신청 시작", "기간 연장", "추가 모집", "신규사업",
    # 청년
    "청년", "청년월세", "청년도약계좌", "청년주거", "청년지원", "구직", "취업지원", "자립준비청년",
    # 출산·육아
    "출산", "육아", "보육", "부모급여", "아동수당", "양육수당", "아이돌봄", "다자녀", "임산부",
    # 노인
    "노인", "기초연금", "노인일자리", "독거노인", "치매", "장기요양",
    # 장애인
    "장애인", "장애수당", "장애연금", "활동지원", "발달장애", "이동지원",
    # 취약계층
    "한부모", "다문화", "위기가정", "저소득층", "취약계층", "위기가구", "소득지원",
    # 소상공인·고용
    "소상공인", "자영업자", "근로장려금", "실업급여", "고용지원", "특고", "프리랜서",
    # 에너지·생활비
    "에너지", "에너지바우처", "전기요금", "도시가스", "난방비", "수도요금",
    "통신비", "교통비", "지역화폐", "문화누리",
    # 기타
    "무료", "무상", "선착순",
]

def crawl(site):
    """사이트 크롤링 후 키워드 매칭된 정책 반환"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(site["url"], headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        # 여러 선택자 시도
        items = []
        for sel in site["list_selector"].split(", "):
            items = soup.select(sel)
            if items:
                break

        results = []
        seen = set()

        for item in items[:20]:  # 최신 20개 중 키워드 필터
            # 제목 추출 시도
            title_tag = None
            for t_sel in site["title_selector"].split(", "):
                title_tag = item.select_one(t_sel)
                if title_tag:
                    break

            a_tag = item.select_one("a")
            if not title_tag or not a_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = a_tag.get("href", "")

            if not title or title in seen:
                continue
            seen.add(title)

            # 링크 처리
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = site["link_prefix"] + href
            else:
                link = site["link_prefix"] + "/" + href

            # 키워드 필터
            if any(kw in title for kw in KEYWORDS):
                results.append(f"• {title}\n  🔗 {link}")

        return results

    except Exception as e:
        return [f"⚠️ 크롤링 실패: {str(e)}"]


def send_telegram(message):
    """텔레그램 메시지 전송 (4096자 초과시 분할)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_len = 4000

    if len(message) <= max_len:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })
    else:
        # 메시지가 길 경우 분할 전송
        chunks = [message[i:i+max_len] for i in range(0, len(message), max_len)]
        for chunk in chunks:
            requests.post(url, data={
                "chat_id": CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            })


def main():
    today = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    # 요일 한글 변환
    day_map = {"Monday":"월요일","Tuesday":"화요일","Wednesday":"수요일",
               "Thursday":"목요일","Friday":"금요일","Saturday":"토요일","Sunday":"일요일"}
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    msg = f"🌅 *{today} 정부 정책 모닝 브리핑*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    total_count = 0

    for site in SITES:
        results = crawl(site)
        if results:
            msg += f"📋 *[{site['name']}]*\n"
            msg += "\n".join(results) + "\n\n"
            total_count += len(results)
        # 결과 없으면 해당 사이트 생략 (메시지 간결하게)

    if total_count == 0:
        msg += "오늘은 새로운 키워드 매칭 정책이 없습니다.\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔍 총 {total_count}건 | 키워드 필터 적용"

    send_telegram(msg)
    print(f"✅ 전송 완료 - {total_count}건")


if __name__ == "__main__":
    main()
