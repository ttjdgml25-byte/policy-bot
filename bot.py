import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

# ✅ 전체 키워드 목록
KEYWORDS = [
    "지원사업", "지원금", "복지서비스", "혜택", "바우처", "수당", "장려금", "급여", "연금",
    "환급", "감면", "면제", "할인", "쿠폰", "포인트", "금융지원", "이자지원",
    "생활지원", "생계지원", "주거지원", "의료지원", "돌봄지원", "긴급지원",
    "민생지원", "민생안정", "생활안정", "추가지원", "특별지원",
    "대상자", "신청", "접수", "모집", "신청기간", "신청방법", "지급", "지급일정",
    "시행", "추진", "확대", "신설", "개편", "운영", "발표", "안내",
    "보도자료", "공고", "고시", "행정예고", "지침", "시범사업",
    "종합계획", "기본계획",
    "전국민", "전 국민", "누구나", "전국 대상", "대상 확대",
    "신청 시작", "기간 연장", "추가 모집", "신규사업",
    "청년", "청년월세", "청년도약계좌", "청년주거", "청년지원", "구직", "취업지원", "자립준비청년",
    "출산", "육아", "보육", "부모급여", "아동수당", "양육수당", "아이돌봄", "다자녀", "임산부",
    "노인", "기초연금", "노인일자리", "독거노인", "치매", "장기요양",
    "장애인", "장애수당", "장애연금", "활동지원", "발달장애", "이동지원",
    "한부모", "다문화", "위기가정", "저소득층", "취약계층", "위기가구", "소득지원",
    "소상공인", "자영업자", "근로장려금", "실업급여", "고용지원", "특고", "프리랜서",
    "에너지", "에너지바우처", "전기요금", "도시가스", "난방비", "수도요금",
    "통신비", "교통비", "지역화폐", "문화누리",
    "무료", "무상", "선착순",
]

# ✅ RSS 피드 목록 (검증된 주소)
RSS_SITES = [
    {
        "name": "정책브리핑 - 정책뉴스",
        "url": "https://www.korea.kr/rss/policy.xml",
    },
    {
        "name": "정책브리핑 - 보도자료",
        "url": "https://www.korea.kr/rss/pressRelease.xml",
    },
    {
        "name": "보건복지부",
        "url": "https://www.mohw.go.kr/rssMohw.do",
    },
    {
        "name": "고용노동부",
        "url": "https://www.moel.go.kr/rss/rssMain.do",
    },
    {
        "name": "여성가족부",
        "url": "https://www.mogef.go.kr/rss/rssNews.do",
    },
    {
        "name": "국토교통부",
        "url": "https://www.molit.go.kr/rss/rssMain.do",
    },
    {
        "name": "중소벤처기업부",
        "url": "https://www.mss.go.kr/rss/rssMss.do",
    },
]

# ✅ HTML 직접 크롤링 사이트
CRAWL_SITES = [
    {
        "name": "고용24(Work24)",
        "url": "https://www.work24.go.kr/cm/main.do",
        "item_selector": ".board-list li, .news-list li, .list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.work24.go.kr",
    },
    {
        "name": "가족센터",
        "url": "https://www.familynet.or.kr/web/board/BD_board.list.do?bbsCd=1001",
        "item_selector": "table tbody tr",
        "title_selector": "td.subject a, td a",
        "link_prefix": "https://www.familynet.or.kr",
    },
    {
        "name": "서울복지포털",
        "url": "https://wis.seoul.go.kr/news/newsList.do",
        "item_selector": ".board_list tbody tr, .list tbody tr",
        "title_selector": "td.title a, td.subject a",
        "link_prefix": "https://wis.seoul.go.kr",
    },
    {
        "name": "청년센터",
        "url": "https://www.youthcenter.go.kr/youngPlcyUnif/youngPlcyUnifList.do",
        "item_selector": ".list_area li, .policy_list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.youthcenter.go.kr",
    },
    {
        "name": "복지멤버십(plus.gov.kr)",
        "url": "https://plus.gov.kr/",
        "item_selector": ".board-list li, .news-list li, .list-item",
        "title_selector": ".tit, .title, h3, h4",
        "link_prefix": "https://plus.gov.kr",
    },
    {
        "name": "창업진흥원(K-Startup)",
        "url": "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do",
        "item_selector": ".list-type02 li, .board-list li",
        "title_selector": ".tit, .title, a",
        "link_prefix": "https://www.k-startup.go.kr",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def crawl_rss(site):
    try:
        res = requests.get(site["url"], headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")[:20]
        results = []
        seen = set()
        for item in items:
            title_tag = item.find("title")
            link_tag = item.find("link")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = link_tag.get_text(strip=True) if link_tag else ""
            if title in seen:
                continue
            seen.add(title)
            if any(kw in title for kw in KEYWORDS):
                results.append(f"• {title}\n  🔗 {link}")
        return results
    except Exception:
        return []


def crawl_html(site):
    try:
        res = requests.get(site["url"], headers=HEADERS, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        items = []
        for sel in site["item_selector"].split(", "):
            items = soup.select(sel)
            if items:
                break
        results = []
        seen = set()
        for item in items[:20]:
            title_tag = None
            for t_sel in site["title_selector"].split(", "):
                title_tag = item.select_one(t_sel)
                if title_tag:
                    break
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title or title in seen:
                continue
            seen.add(title)
            a_tag = title_tag if title_tag.name == "a" else item.select_one("a")
            href = a_tag.get("href", "") if a_tag else ""
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = site["link_prefix"] + href
            else:
                link = site["link_prefix"] + "/" + href
            if any(kw in title for kw in KEYWORDS):
                results.append(f"• {title}\n  🔗 {link}")
        return results
    except Exception:
        return []


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_len = 4000
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
    day_map = {
        "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
        "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"
    }
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    msg = f"🌅 *{today} 정부 정책 모닝 브리핑*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    total_count = 0

    for site in RSS_SITES:
        results = crawl_rss(site)
        if results:
            msg += f"📋 *[{site['name']}]*\n"
            msg += "\n".join(results) + "\n\n"
            total_count += len(results)

    for site in CRAWL_SITES:
        results = crawl_html(site)
        if results:
            msg += f"📋 *[{site['name']}]*\n"
            msg += "\n".join(results) + "\n\n"
            total_count += len(results)

    if total_count == 0:
        msg += "오늘은 새로운 키워드 매칭 정책이 없습니다.\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔍 총 {total_count}건 | 키워드 필터 적용"

    send_telegram(msg)
    print(f"✅ 전송 완료 - {total_count}건")


if __name__ == "__main__":
    main()
