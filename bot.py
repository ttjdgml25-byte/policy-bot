import requests
from bs4 import BeautifulSoup
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 테스트할 RSS 목록
RSS_SITES = [
    {"name": "정책브리핑-정책뉴스", "url": "https://www.korea.kr/rss/policy.xml"},
    {"name": "정책브리핑-보도자료", "url": "https://www.korea.kr/rss/pressRelease.xml"},
    {"name": "보건복지부", "url": "https://www.mohw.go.kr/rssMohw.do"},
    {"name": "고용노동부", "url": "https://www.moel.go.kr/rss/rssMain.do"},
    {"name": "경기도뉴스", "url": "https://gnews.gg.go.kr/rss/gnews_rss_main.do"},
    {"name": "서울시뉴스", "url": "https://www.seoul.go.kr/rss/news.do"},
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    })

msg = "🔍 진단 시작\n\n"

for site in RSS_SITES:
    try:
        res = requests.get(site["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        if items:
            first = items[0].find("title")
            title = first.get_text(strip=True) if first else "제목없음"
            msg += f"✅ {site['name']}: {len(items)}건\n예시: {title[:40]}\n\n"
        else:
            msg += f"❌ {site['name']}: 항목 없음 (상태코드: {res.status_code})\n\n"
    except Exception as e:
        msg += f"⚠️ {site['name']}: 오류 - {str(e)[:50]}\n\n"

send_telegram(msg)
print("진단 완료")
