import requests
from bs4 import BeautifulSoup
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_IDS = [
    os.environ["CHAT_ID"],
    os.environ.get("CHAT_ID_2", ""),
]
CHAT_IDS = [c for c in CHAT_IDS if c]
API_KEY = os.environ["DATA_API_KEY"]

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS[:1]:  # 테스트는 1명에게만
        requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True
        })


def try_params(name, params):
    """파라미터 조합 시도"""
    try:
        res = requests.get(URL, params=params, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        total = soup.find("totalCount")
        result_msg = soup.find("resultMessage")
        total_txt = total.get_text() if total else "?"
        msg_txt = result_msg.get_text() if result_msg else "?"
        return f"[{name}] totalCount={total_txt}, msg={msg_txt}"
    except Exception as e:
        return f"[{name}] 오류: {str(e)[:50]}"


def main():
    results = []

    # 조합 1: 페이지 관련 다양한 이름
    results.append(try_params("기본", {
        "serviceKey": API_KEY, "pageNo": "1", "numOfRows": "5"
    }))

    # 조합 2: srchKeyCode 추가
    results.append(try_params("srchKeyCode", {
        "serviceKey": API_KEY, "pageNo": "1", "numOfRows": "5",
        "srchKeyCode": "001"
    }))

    # 조합 3: 생애주기/대상 코드
    results.append(try_params("lifeArray", {
        "serviceKey": API_KEY, "pageNo": "1", "numOfRows": "5",
        "lifeArray": "", "trgterIndvdlArray": "", "intrsThemaArray": ""
    }))

    # 조합 4: 모든 가능한 파라미터
    results.append(try_params("전체파라미터", {
        "serviceKey": API_KEY, "callTp": "L", "pageNo": "1", "numOfRows": "5",
        "srchKeyCode": "003", "searchWrd": ""
    }))

    # 조합 5: orderBy 추가
    results.append(try_params("orderBy", {
        "serviceKey": API_KEY, "pageNo": "1", "numOfRows": "5",
        "orderBy": "date"
    }))

    msg = "🔍 파라미터 테스트 결과\n\n" + "\n\n".join(results)
    send_telegram(msg)
    print(msg)


if __name__ == "__main__":
    main()
