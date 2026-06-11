import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_IDS = [
    os.environ["CHAT_ID"],
    os.environ.get("CHAT_ID_2", ""),
]
CHAT_IDS = [c for c in CHAT_IDS if c]
API_KEY = os.environ["DATA_API_KEY"]

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"

# ✅ 웹페이지 주소
WEB_URL = "https://ttjdgml25-byte.github.io/policy-bot/"

# ✅ 주제별 카테고리
CATEGORIES = {
    "👶 임신·출산·육아": ["출산", "육아", "보육", "임신", "영유아", "아동", "양육", "임산부"],
    "🎓 청년·교육": ["청년", "교육", "학자금", "장학", "구직", "취업", "일자리"],
    "👴 노인·어르신": ["노인", "어르신", "고령", "기초연금", "치매", "장기요양"],
    "♿ 장애인": ["장애", "발달장애", "활동지원"],
    "💰 금융·생활지원": ["서민금융", "금융", "생활", "생계", "긴급", "저소득", "주거", "에너지"],
    "🏥 의료·건강": ["의료", "건강", "질환", "치료", "재활", "보건"],
    "👨‍👩‍👧 가족·여성": ["한부모", "다문화", "여성", "가족", "가정"],
    "💼 고용·일자리": ["고용", "근로", "실업", "취업", "직업", "소상공인", "자영업"],
}


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
    items = []
    try:
        params = {
            "serviceKey": API_KEY,
            "pageNo": "1",
            "numOfRows": "500",
            "srchKeyCode": "003",
        }
        res = requests.get(URL, params=params, timeout=20)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("servList")
    except Exception as e:
        print(f"API 오류: {e}")
    return items


def parse_item(item):
    def g(tag):
        t = item.find(tag)
        return t.get_text(strip=True) if t else ""
    return {
        "title": g("servNm"),
        "desc": g("servDgst"),
        "thema": g("intrsThemaArray"),
        "dept": g("jurMnofNm"),
        "link": g("servDtlLink"),
        "provide": g("srvPvsnNm"),
        "cycle": g("sprtCycNm"),
        "online": g("onapPsbltYn"),
        "regdate": g("svcfrstRegTs"),
    }


def categorize(data_list):
    cats = {name: [] for name in CATEGORIES}
    cats["📌 기타"] = []
    for d in data_list:
        text = f"{d['title']} {d['thema']} {d['desc']}"
        matched = False
        for cat_name, keywords in CATEGORIES.items():
            if any(kw in text for kw in keywords):
                cats[cat_name].append(d)
                matched = True
                break
        if not matched:
            cats["📌 기타"].append(d)
    return cats


def main():
    today = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    day_map = {
        "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
        "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"
    }
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    items = get_welfare_list()
    all_data = [parse_item(it) for it in items if it.find("servNm")]

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    new_items = [d for d in all_data if d["regdate"] and d["regdate"] >= week_ago]
    online_items = [d for d in all_data if d["online"] == "Y"]

    msg = f"🌅 *{today} 복지정책 브리핑*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if new_items:
        msg += f"🆕 *최근 7일 신규 복지서비스 ({len(new_items)}건)*\n\n"
        for d in new_items[:10]:
            msg += f"• *{d['title']}*\n"
            if d['dept']:
                msg += f"  🏛 {d['dept']}\n"
            if d['online'] == "Y":
                msg += f"  ✅ 온라인 신청 가능\n"
            if d['link']:
                msg += f"  🔗 {d['link']}\n"
            msg += "\n"
        if len(new_items) > 10:
            msg += f"...외 {len(new_items)-10}건 더 (웹페이지 참고)\n\n"
    else:
        msg += "🆕 최근 7일 신규 복지서비스: 없음\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 전체 {len(all_data)}건 | 🆕 신규 {len(new_items)}건 | ✅ 온라인신청 {len(online_items)}건\n\n"
    msg += f"📋 *전체 주제별 목록 보기*\n{WEB_URL}"

    send_telegram(msg)
    generate_html(all_data)
    print(f"✅ 완료 - 전체 {len(all_data)}, 신규 {len(new_items)}, 온라인 {len(online_items)}")


def generate_html(all_data):
    cats = categorize(all_data)
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    online_count = len([d for d in all_data if d['online'] == "Y"])

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>복지서비스 모아보기</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,'Malgun Gothic',sans-serif; background:#f5f6fa; margin:0; padding:16px; color:#2c3e50; }}
  h1 {{ text-align:center; color:#2c3e50; font-size:24px; }}
  .update {{ text-align:center; color:#888; font-size:13px; margin-bottom:8px; }}
  .summary {{ text-align:center; margin-bottom:20px; }}
  .summary span {{ display:inline-block; background:#fff; padding:6px 14px; border-radius:20px; margin:4px; font-size:13px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
  .filter-btn {{ display:block; width:100%; max-width:400px; margin:0 auto 20px; padding:12px; background:#2ecc71; color:#fff; border:none; border-radius:8px; font-size:15px; font-weight:bold; cursor:pointer; }}
  .category {{ background:#fff; border-radius:12px; margin-bottom:16px; padding:18px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }}
  .cat-title {{ font-size:18px; font-weight:bold; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid #3498db; }}
  .count {{ color:#888; font-size:13px; font-weight:normal; }}
  .item {{ padding:12px 0; border-bottom:1px solid #eee; }}
  .item:last-child {{ border-bottom:none; }}
  .item-title {{ font-weight:bold; font-size:15px; }}
  .badge {{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:10px; margin-left:6px; }}
  .badge-online {{ background:#2ecc71; color:#fff; }}
  .badge-dept {{ background:#ecf0f1; color:#555; }}
  .desc {{ color:#666; font-size:13px; margin:6px 0; line-height:1.5; }}
  .link {{ color:#3498db; font-size:13px; text-decoration:none; font-weight:bold; }}
</style>
</head>
<body>
<h1>🏛 복지서비스 모아보기</h1>
<div class="update">마지막 업데이트: {update_time}</div>
<div class="summary">
  <span>📊 전체 {len(all_data)}건</span>
  <span>✅ 온라인신청 {online_count}건</span>
</div>
<button class="filter-btn" onclick="toggleOnline()">✅ 온라인 신청 가능만 보기</button>
"""

    for cat_name, items in cats.items():
        if not items:
            continue
        html += f'<div class="category">\n'
        html += f'<div class="cat-title">{cat_name} <span class="count">({len(items)}건)</span></div>\n'
        for d in items:
            online_attr = 'data-online="Y"' if d['online'] == "Y" else 'data-online="N"'
            online_badge = '<span class="badge badge-online">온라인신청</span>' if d['online'] == "Y" else ''
            html += f'<div class="item" {online_attr}>\n'
            html += f'<div class="item-title">{d["title"]}{online_badge}'
            if d['dept']:
                html += f'<span class="badge badge-dept">{d["dept"]}</span>'
            html += '</div>\n'
            if d['desc']:
                html += f'<div class="desc">{d["desc"]}</div>\n'
            if d['link']:
                html += f'<a class="link" href="{d["link"]}" target="_blank">자세히 보기 →</a>\n'
            html += '</div>\n'
        html += '</div>\n'

    html += """
<script>
let showOnlyOnline = false;
function toggleOnline() {
  showOnlyOnline = !showOnlyOnline;
  const items = document.querySelectorAll('.item');
  items.forEach(item => {
    if (showOnlyOnline && item.getAttribute('data-online') !== 'Y') {
      item.style.display = 'none';
    } else {
      item.style.display = 'block';
    }
  });
  document.querySelector('.filter-btn').textContent = showOnlyOnline ? '📋 전체 보기' : '✅ 온라인 신청 가능만 보기';
}
</script>
</body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료")


if __name__ == "__main__":
    main()
