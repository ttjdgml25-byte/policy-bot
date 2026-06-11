import requests
from bs4 import BeautifulSoup
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_IDS = [os.environ["CHAT_ID"]]
API_KEY = os.environ["DATA_API_KEY"]

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True
        })


def main():
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "2",
        "srchKeyCode": "003",
    }
    res = requests.get(URL, params=params, timeout=15)
    # 첫 번째 item의 전체 XML 구조를 그대로 전송
    soup = BeautifulSoup(res.content, "xml")
    first_item = soup.find("servList")  # 또는 item
    if not first_item:
        first_item = soup.find("item")
    
    msg = f"🔍 응답 구조 확인\n\n{str(first_item)[:1500] if first_item else '항목 없음. 전체:'+res.text[:1000]}"
    send_telegram(msg)
    print(res.text[:2000])


if __name__ == "__main__":
    main()
