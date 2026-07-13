# -*- coding: utf-8 -*-
"""
복지알림봇 v2
- 한국시간(KST) 기준 날짜 표기 (GitHub Actions UTC 문제 해결)
- data.json 스냅샷 비교로 신규 복지서비스 정확히 감지
- 카드뉴스 이미지 자동 생성 후 텔레그램 발송 (신규 / 오늘의 추천 / 온라인신청 요약)
- 인라인 키보드 메뉴 + 주제별 웹페이지 생성
"""
import requests
import os
import json
import html as html_mod
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────── 기본 설정 ───────────────────────────
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY_STR = NOW.strftime("%Y%m%d")
DRY_RUN = os.environ.get("DRY_RUN") == "1"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_IDS = [c for c in [os.environ.get("CHAT_ID", ""), os.environ.get("CHAT_ID_2", "")] if c]
API_KEY = os.environ.get("DATA_API_KEY", "")

URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
WEB_URL = "https://ttjdgml25-byte.github.io/policy-bot/"
BOKJIRO_URL = "https://www.bokjiro.go.kr"
SNAPSHOT_FILE = "data.json"

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
CAT_COLORS = {
    "👶 임신·출산·육아": (255, 138, 128),
    "🎓 청년·교육": (79, 134, 247),
    "👴 노인·어르신": (149, 117, 205),
    "♿ 장애인": (38, 166, 154),
    "💰 금융·생활지원": (255, 167, 38),
    "🏥 의료·건강": (236, 64, 122),
    "👨‍👩‍👧 가족·여성": (141, 110, 99),
    "💼 고용·일자리": (66, 165, 245),
    "📌 기타": (120, 144, 156),
}

# ─────────────────────────── 텔레그램 ───────────────────────────
def tg_api(method, **kwargs):
    if DRY_RUN:
        print(f"[DRY_RUN] {method}: {str(kwargs)[:200]}")
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, timeout=30, **kwargs)
        if not r.json().get("ok"):
            print(f"⚠️ 텔레그램 오류({method}): {r.text[:300]}")
        return r
    except Exception as e:
        print(f"⚠️ 텔레그램 예외({method}): {e}")
        return None


def send_message(text, keyboard=None):
    max_len = 4000
    chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    for chat_id in CHAT_IDS:
        for i, chunk in enumerate(chunks):
            data = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            # 키보드는 마지막 조각에만 부착
            if keyboard and i == len(chunks) - 1:
                data["reply_markup"] = json.dumps(keyboard)
            tg_api("sendMessage", data=data)


def send_photo(path, caption):
    for chat_id in CHAT_IDS:
        if DRY_RUN:
            print(f"[DRY_RUN] sendPhoto {path} → {chat_id}")
            continue
        with open(path, "rb") as f:
            tg_api("sendPhoto",
                   data={"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML"},
                   files={"photo": f})


def esc(s):
    return html_mod.escape(s or "")

# ─────────────────────────── 데이터 수집 ───────────────────────────
def get_welfare_list():
    items = []
    try:
        params = {
            "serviceKey": API_KEY,
            "pageNo": "1",
            "numOfRows": "500",
            "srchKeyCode": "003",
        }
        res = requests.get(URL, params=params, timeout=30)
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
        "id": g("servId"),
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


def find_category(d):
    text = f"{d['title']} {d['thema']} {d['desc']}"
    for cat_name, keywords in CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return cat_name
    return "📌 기타"


def categorize(data_list):
    cats = {name: [] for name in CATEGORIES}
    cats["📌 기타"] = []
    for d in data_list:
        cats[find_category(d)].append(d)
    return cats

# ─────────────────── 신규 감지 (스냅샷 비교) ───────────────────
def load_snapshot():
    try:
        with open(SNAPSHOT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def detect_new(all_data):
    """이전 실행 때 저장한 목록(data.json)과 비교해 새로 추가된 서비스를 찾는다.
    첫 실행이면 전체를 기존 항목으로 저장만 하고 신규 0건 처리."""
    snap = load_snapshot()
    known = snap.get("items", {}) if snap else {}
    first_run = snap is None

    week_ago = (NOW - timedelta(days=7)).strftime("%Y%m%d")
    new_items = []
    items_out = {}
    for d in all_data:
        key = d["id"] or d["title"]
        if key in known:
            first_seen = known[key].get("first_seen", "")
        else:
            # 첫 실행이면 신규로 치지 않음(과거 데이터 구분 불가)
            first_seen = "" if first_run else TODAY_STR
        d["first_seen"] = first_seen
        items_out[key] = {"title": d["title"], "first_seen": first_seen}
        # 최근 7일 내 목록에 새로 등장했거나, API 등록일이 7일 이내면 신규
        is_new = (first_seen and first_seen >= week_ago) or \
                 (d["regdate"] and d["regdate"][:8] >= week_ago)
        if is_new:
            d["is_new"] = True
            new_items.append(d)
        else:
            d["is_new"] = False

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": NOW.strftime("%Y-%m-%d %H:%M"), "items": items_out},
                  f, ensure_ascii=False, indent=1)
    return new_items

# ─────────────────────────── 카드뉴스 ───────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]

def get_font(size, bold=False):
    paths = FONT_PATHS if bold else FONT_PATHS[1:] + FONT_PATHS[:1]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text, font, max_width):
    lines, line = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(line); line = ""
            continue
        if font.getlength(line + ch) <= max_width:
            line += ch
        else:
            lines.append(line); line = ch
    if line:
        lines.append(line)
    return lines


def strip_emoji_prefix(cat_name):
    # 카테고리명에서 이모지 제거(이미지 폰트가 이모지 미지원)
    return cat_name.split(" ", 1)[-1] if " " in cat_name else cat_name


def draw_card(d, badge_text, badge_color, filename):
    """복지서비스 1건 카드뉴스 (1080x1080)"""
    W, H = 1080, 1080
    cat = find_category(d)
    color = CAT_COLORS.get(cat, (120, 144, 156))
    img = Image.new("RGB", (W, H), (250, 250, 252))
    dr = ImageDraw.Draw(img)

    # 상단 컬러 밴드
    dr.rectangle([0, 0, W, 190], fill=color)
    dr.text((60, 45), strip_emoji_prefix(cat), font=get_font(40, True), fill=(255, 255, 255, 220))
    dr.text((60, 105), NOW.strftime("%Y.%m.%d") + " 복지알림봇", font=get_font(30), fill=(255, 255, 255))

    # 배지 (NEW / 오늘의 추천 등)
    bf = get_font(34, True)
    bw = bf.getlength(badge_text) + 60
    dr.rounded_rectangle([W - bw - 60, 60, W - 60, 130], radius=35, fill=badge_color)
    dr.text((W - bw - 30, 74), badge_text, font=bf, fill=(255, 255, 255))

    # 정보 행 개수를 먼저 계산해 하단 기준으로 배치
    rows = []
    if d["dept"]:
        rows.append(("소관부처", d["dept"]))
    if d["cycle"]:
        rows.append(("지원주기", d["cycle"]))
    if d["provide"]:
        rows.append(("제공형태", d["provide"]))
    rows = rows[:3]
    rows_start = (H - 90) - len(rows) * 72 - 24  # 하단 밴드 위에 정확히 맞춤

    y = 250
    # 제목
    tf = get_font(58, True)
    for line in wrap_text(d["title"], tf, W - 120)[:3]:
        dr.text((60, y), line, font=tf, fill=(33, 41, 52))
        y += 78
    y += 20
    dr.line([60, y, W - 60, y], fill=(225, 228, 233), width=3)
    y += 35

    # 설명 (정보 행을 침범하지 않는 만큼만 표시)
    df = get_font(38)
    desc_lines = wrap_text(d["desc"], df, W - 120)
    max_lines = max(1, int((rows_start - 30 - y) / 56))
    for line in desc_lines[:max_lines]:
        dr.text((60, y), line, font=df, fill=(90, 99, 110))
        y += 56
    if len(desc_lines) > max_lines:
        dr.rectangle([60, y - 56, W - 60, y], fill=(250, 250, 252))
        dr.text((60, y - 56), desc_lines[max_lines - 1][:-1] + "…", font=df, fill=(90, 99, 110))

    # 정보 행
    y = rows_start
    lf = get_font(32, True)
    vf = get_font(32)
    for label, value in rows:
        dr.rounded_rectangle([60, y, 250, y + 52], radius=26, fill=(238, 241, 246))
        lw = lf.getlength(label)
        dr.text((60 + (190 - lw) / 2, y + 8), label, font=lf, fill=(70, 80, 95))
        dr.text((275, y + 8), value[:28], font=vf, fill=(50, 58, 70))
        y += 72

    # 하단 신청 안내 밴드
    if d["online"] == "Y":
        dr.rectangle([0, H - 90, W, H], fill=(46, 204, 113))
        note = "온라인 신청 가능 · 복지로(bokjiro.go.kr)에서 바로 신청"
    else:
        dr.rectangle([0, H - 90, W, H], fill=(96, 108, 122))
        note = "읍면동 주민센터 또는 소관기관 문의 · 자세한 방법은 링크 참고"
    nf = get_font(30, True)
    nw = nf.getlength(note)
    dr.text(((W - nw) / 2, H - 68), note, font=nf, fill=(255, 255, 255))

    img.save(filename)
    return filename


def draw_summary_card(all_data, filename):
    """온라인신청 가능 복지 요약 카드"""
    W, H = 1080, 1080
    online = [d for d in all_data if d["online"] == "Y"]
    img = Image.new("RGB", (W, H), (37, 47, 63))
    dr = ImageDraw.Draw(img)

    dr.text((60, 70), NOW.strftime("%Y.%m.%d") + " 복지알림봇", font=get_font(32), fill=(160, 172, 186))
    tf = get_font(62, True)
    dr.text((60, 130), "지금 온라인으로", font=tf, fill=(255, 255, 255))
    dr.text((60, 215), "신청할 수 있는 복지", font=tf, fill=(255, 255, 255))

    dr.rounded_rectangle([60, 330, W - 60, 470], radius=24, fill=(46, 204, 113))
    cf = get_font(72, True)
    ct = f"총 {len(online)}건"
    dr.text(((W - cf.getlength(ct)) / 2, 358), ct, font=cf, fill=(255, 255, 255))

    # 카테고리별 건수
    cats = categorize(online)
    y = 530
    lf = get_font(36)
    nf = get_font(36, True)
    for cat_name, items in cats.items():
        if not items:
            continue
        name = strip_emoji_prefix(cat_name)
        color = CAT_COLORS.get(cat_name, (120, 144, 156))
        dr.ellipse([70, y + 10, 94, y + 34], fill=color)
        dr.text((115, y), name, font=lf, fill=(220, 226, 233))
        cnt = f"{len(items)}건"
        dr.text((W - 60 - nf.getlength(cnt), y), cnt, font=nf, fill=(255, 255, 255))
        y += 56
        if y > H - 160:
            break

    dr.rectangle([0, H - 80, W, H], fill=(46, 204, 113))
    note = "전체 목록 · 신청 링크는 아래 버튼에서 확인하세요"
    nfo = get_font(28, True)
    dr.text(((W - nfo.getlength(note)) / 2, H - 60), note, font=nfo, fill=(255, 255, 255))
    img.save(filename)
    return filename


def item_caption(d, prefix=""):
    cap = f"{prefix}<b>{esc(d['title'])}</b>\n"
    if d["dept"]:
        cap += f"🏛 {esc(d['dept'])}"
    if d["cycle"]:
        cap += f" · 🔄 {esc(d['cycle'])}"
    cap += "\n"
    cap += "✅ 온라인 신청 가능\n" if d["online"] == "Y" else "🏢 주민센터/기관 신청\n"
    if d["link"]:
        cap += f"🔗 <a href=\"{esc(d['link'])}\">신청·상세 안내 바로가기</a>"
    return cap


def pick_daily_recommendations(all_data, n=3):
    """온라인 신청 가능 목록을 날짜 기준으로 로테이션하여 매일 다른 n건 추천"""
    online = [d for d in all_data if d["online"] == "Y"]
    if not online:
        return []
    online.sort(key=lambda d: d["id"] or d["title"])
    start = (NOW.timetuple().tm_yday * n) % len(online)
    return [online[(start + i) % len(online)] for i in range(min(n, len(online)))]

# ─────────────────────────── 메시지 ───────────────────────────
def build_message(all_data, new_items, recs):
    day_map = {"Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
               "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"}
    today = NOW.strftime("%Y년 %m월 %d일 (%A)")
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    online_items = [d for d in all_data if d["online"] == "Y"]

    msg = f"🌅 <b>{today} 복지정책 브리핑</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if new_items:
        msg += f"🆕 <b>새로 올라온 복지서비스 {len(new_items)}건</b>\n\n"
        for d in new_items[:10]:
            msg += f"• <b>{esc(d['title'])}</b>\n"
            if d["dept"]:
                msg += f"   🏛 {esc(d['dept'])}\n"
            if d["online"] == "Y":
                msg += "   ✅ 온라인 신청 가능\n"
            if d["link"]:
                msg += f"   🔗 {esc(d['link'])}\n"
            msg += "\n"
        if len(new_items) > 10:
            msg += f"…외 {len(new_items) - 10}건 (웹페이지 참고)\n\n"
    else:
        msg += "🆕 새로 올라온 복지서비스: 오늘은 없어요\n\n"

    if recs:
        msg += f"🎯 <b>오늘의 추천 복지 {len(recs)}건</b> (온라인 신청 가능)\n\n"
        for i, d in enumerate(recs, 1):
            msg += f"{i}. <b>{esc(d['title'])}</b>"
            if d["dept"]:
                msg += f" — {esc(d['dept'])}"
            msg += "\n"
            if d["link"]:
                msg += f"   🔗 {esc(d['link'])}\n"
        msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 전체 {len(all_data)}건 | 🆕 신규 {len(new_items)}건 | ✅ 온라인신청 {len(online_items)}건"
    return msg


def build_keyboard():
    return {"inline_keyboard": [
        [
            {"text": "📋 전체 목록", "url": WEB_URL},
            {"text": "✅ 온라인신청만", "url": WEB_URL + "?online=1"},
        ],
        [
            {"text": "🏛 복지로 홈", "url": BOKJIRO_URL},
            {"text": "🔍 복지서비스 검색", "url": WEB_URL + "?focus=search"},
        ],
    ]}

# ─────────────────────────── 웹페이지 ───────────────────────────
def generate_html(all_data, new_items):
    cats = categorize(all_data)
    update_time = NOW.strftime("%Y-%m-%d %H:%M") + " (한국시간)"
    online_count = len([d for d in all_data if d["online"] == "Y"])

    chips = ""
    for i, (cat_name, items) in enumerate(cats.items()):
        if not items:
            continue
        chips += f'<a class="chip" href="#cat{i}">{cat_name} <b>{len(items)}</b></a>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>복지서비스 모아보기</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,'Malgun Gothic',sans-serif; background:#f5f6fa; margin:0; padding:0 0 40px; color:#2c3e50; }}
  header {{ position:sticky; top:0; z-index:10; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,0.08); padding:12px 16px 8px; }}
  h1 {{ margin:0 0 2px; font-size:20px; text-align:center; }}
  .update {{ text-align:center; color:#888; font-size:12px; margin-bottom:8px; }}
  .controls {{ display:flex; gap:8px; max-width:640px; margin:0 auto 8px; }}
  #search {{ flex:1; padding:10px 14px; border:1.5px solid #dfe4ea; border-radius:24px; font-size:14px; outline:none; }}
  #search:focus {{ border-color:#3498db; }}
  .toggle {{ padding:10px 14px; background:#2ecc71; color:#fff; border:none; border-radius:24px; font-size:13px; font-weight:bold; cursor:pointer; white-space:nowrap; }}
  .toggle.off {{ background:#b2bec3; }}
  .chips {{ display:flex; gap:6px; overflow-x:auto; padding:2px 0 6px; -webkit-overflow-scrolling:touch; }}
  .chip {{ flex:none; background:#eef1f6; color:#444; border-radius:16px; padding:6px 12px; font-size:12.5px; text-decoration:none; }}
  .chip b {{ color:#3498db; }}
  main {{ max-width:640px; margin:12px auto 0; padding:0 14px; }}
  .summary {{ text-align:center; margin-bottom:14px; }}
  .summary span {{ display:inline-block; background:#fff; padding:6px 14px; border-radius:20px; margin:3px; font-size:13px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
  .newbox {{ background:#fff8e6; border:1.5px solid #ffd25e; border-radius:12px; padding:14px 16px; margin-bottom:16px; }}
  .newbox h2 {{ margin:0 0 8px; font-size:15px; color:#b7791f; }}
  .category {{ background:#fff; border-radius:12px; margin-bottom:16px; padding:18px; box-shadow:0 2px 8px rgba(0,0,0,0.05); scroll-margin-top:170px; }}
  .cat-title {{ font-size:17px; font-weight:bold; margin-bottom:10px; padding-bottom:8px; border-bottom:2px solid #3498db; }}
  .count {{ color:#888; font-size:13px; font-weight:normal; }}
  .item {{ padding:12px 0; border-bottom:1px solid #eee; }}
  .item:last-child {{ border-bottom:none; }}
  .item-title {{ font-weight:bold; font-size:15px; line-height:1.5; }}
  .badge {{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:10px; margin-left:5px; vertical-align:middle; }}
  .badge-online {{ background:#2ecc71; color:#fff; }}
  .badge-new {{ background:#e74c3c; color:#fff; }}
  .badge-dept {{ background:#ecf0f1; color:#555; }}
  .badge-cycle {{ background:#e8f2fd; color:#2471a3; }}
  .desc {{ color:#666; font-size:13px; margin:6px 0; line-height:1.55; }}
  .link {{ color:#3498db; font-size:13px; text-decoration:none; font-weight:bold; }}
  .hidden {{ display:none !important; }}
  .noresult {{ text-align:center; color:#999; padding:30px 0; display:none; }}
</style>
</head>
<body>
<header>
  <h1>🏛 복지서비스 모아보기</h1>
  <div class="update">마지막 업데이트: {update_time}</div>
  <div class="controls">
    <input id="search" type="search" placeholder="🔍 복지서비스 검색 (예: 청년, 출산, 의료비)">
    <button id="onlineBtn" class="toggle off" onclick="toggleOnline()">✅ 온라인신청만</button>
  </div>
  <nav class="chips">{chips}</nav>
</header>
<main>
<div class="summary">
  <span>📊 전체 {len(all_data)}건</span>
  <span>🆕 신규 {len(new_items)}건</span>
  <span>✅ 온라인신청 {online_count}건</span>
</div>
"""

    if new_items:
        html += '<div class="newbox"><h2>🆕 최근 7일 새로 올라온 복지서비스</h2>\n'
        for d in new_items:
            link = f' <a class="link" href="{d["link"]}" target="_blank">자세히 →</a>' if d["link"] else ""
            html += f'<div class="item"><span class="item-title">{d["title"]}</span>{link}</div>\n'
        html += "</div>\n"

    for i, (cat_name, items) in enumerate(cats.items()):
        if not items:
            continue
        html += f'<div class="category" id="cat{i}">\n'
        html += f'<div class="cat-title">{cat_name} <span class="count">({len(items)}건)</span></div>\n'
        for d in items:
            online_attr = "Y" if d["online"] == "Y" else "N"
            badges = ""
            if d.get("is_new"):
                badges += '<span class="badge badge-new">NEW</span>'
            if d["online"] == "Y":
                badges += '<span class="badge badge-online">온라인신청</span>'
            if d["dept"]:
                badges += f'<span class="badge badge-dept">{d["dept"]}</span>'
            if d["cycle"]:
                badges += f'<span class="badge badge-cycle">{d["cycle"]}</span>'
            html += f'<div class="item" data-online="{online_attr}">\n'
            html += f'<div class="item-title">{d["title"]}{badges}</div>\n'
            if d["desc"]:
                html += f'<div class="desc">{d["desc"]}</div>\n'
            if d["link"]:
                html += f'<a class="link" href="{d["link"]}" target="_blank">자세히 보기 →</a>\n'
            html += "</div>\n"
        html += "</div>\n"

    html += """
<div class="noresult" id="noresult">검색 결과가 없습니다</div>
</main>
<script>
let showOnlyOnline = false;
function applyFilters() {
  const q = document.getElementById('search').value.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll('.category .item').forEach(item => {
    const okOnline = !showOnlyOnline || item.getAttribute('data-online') === 'Y';
    const okSearch = !q || item.textContent.toLowerCase().includes(q);
    const show = okOnline && okSearch;
    item.classList.toggle('hidden', !show);
    if (show) visible++;
  });
  document.querySelectorAll('.category').forEach(cat => {
    const any = cat.querySelectorAll('.item:not(.hidden)').length > 0;
    cat.classList.toggle('hidden', !any);
  });
  document.getElementById('noresult').style.display = visible ? 'none' : 'block';
}
function toggleOnline() {
  showOnlyOnline = !showOnlyOnline;
  const btn = document.getElementById('onlineBtn');
  btn.classList.toggle('off', !showOnlyOnline);
  btn.textContent = showOnlyOnline ? '📋 전체 보기' : '✅ 온라인신청만';
  applyFilters();
}
document.getElementById('search').addEventListener('input', applyFilters);
const params = new URLSearchParams(location.search);
if (params.get('online') === '1') toggleOnline();
if (params.get('focus') === 'search') document.getElementById('search').focus();
</script>
</body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료")

# ─────────────────────────── 메인 ───────────────────────────
def main():
    items = get_welfare_list()
    all_data = [parse_item(it) for it in items if it.find("servNm")]
    if not all_data:
        print("⚠️ API에서 데이터를 받지 못했습니다. 종료합니다.")
        send_message("⚠️ 복지알림봇: 오늘 복지로 API 응답이 없어 브리핑을 만들지 못했어요. 내일 다시 시도합니다.")
        return

    new_items = detect_new(all_data)
    recs = pick_daily_recommendations(all_data, 3)

    # 1) 브리핑 메시지 + 메뉴 버튼
    send_message(build_message(all_data, new_items, recs), keyboard=build_keyboard())

    # 2) 카드뉴스: 신규 (최대 5건)
    for i, d in enumerate(new_items[:5]):
        f = draw_card(d, "NEW 신규", (231, 76, 60), f"card_new_{i}.png")
        send_photo(f, item_caption(d, "🆕 "))

    # 3) 카드뉴스: 오늘의 추천 (매일 로테이션 3건)
    for i, d in enumerate(recs):
        f = draw_card(d, f"오늘의 추천 {i+1}/{len(recs)}", (52, 152, 219), f"card_rec_{i}.png")
        send_photo(f, item_caption(d, "🎯 "))

    # 4) 카드뉴스: 온라인신청 가능 요약
    f = draw_summary_card(all_data, "card_summary.png")
    online_count = len([d for d in all_data if d["online"] == "Y"])
    send_photo(f, f"✅ <b>지금 온라인으로 신청 가능한 복지 {online_count}건</b>\n"
                  f"🔗 <a href=\"{WEB_URL}?online=1\">전체 목록 · 신청 링크 보기</a>")

    generate_html(all_data, new_items)
    print(f"✅ 완료 - 전체 {len(all_data)}, 신규 {len(new_items)}, 추천 {len(recs)}")


if __name__ == "__main__":
    main()
