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

BASE_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_len = 4000
    chunks = [message[i:i+max_len] for i in range(0, len(message), max_len)]
    for chat_id in CHAT_IDS:
        for chunk in chunks:
            r = requests.post(url, data={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True
            })
            print(f"텔레그램 전송: {r.status_code}")


def main():
    print("=== 봇 시작 ===")
    print(f"API_KEY 앞 10자: {API_KEY[:10]}...")
    print(f"CHAT_IDS: {CHAT_IDS}")

    # API 호출
    url = f"{BASE_URL}/NationalWelfarelistV001"
    params = {
        "serviceKey": API_KEY,
        "callTp": "L",
        "pageNo": "1",
        "numOfRows": "5",
    }

    print(f"\n요청 URL: {url}")
    print(f"파라미터: callTp=L, pageNo=1, numOfRows=5")

    try:
        res = requests.get(url, params=params, timeout=15)
        print(f"응답 상태코드: {res.status_code}")
        print(f"응답 내용 (앞 500자):\n{res.text[:500]}")

        # 텔레그램으로도 전송
        msg = f"🔍 API 디버그\n상태: {res.status_code}\n응답:\n{res.text[:600]}"
        send_telegram(msg)

    except Exception as e:
        print(f"오류 발생: {e}")
        send_telegram(f"❌ 오류: {str(e)}")

    print("=== 봇 종료 ===")


if __name__ == "__main__":
    main()
