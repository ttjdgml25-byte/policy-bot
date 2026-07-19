# -*- coding: utf-8 -*-
"""
복지알림봇 v3
- 한국시간(KST) 기준 날짜 표기
- data.json 스냅샷 비교로 신규 복지서비스 감지
- 인포그래픽 카드뉴스 (지원대상/지원내용/신청방법, 내용에 따라 1~2장 자동 구성)
- 교회/단체방 공유용 안내문 캡션
- 인라인 키보드 메뉴 + 주제별 웹페이지 생성
"""
import requests
import os
import re
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

BASE = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
URL_LIST = BASE + "/NationalWelfarelistV001"
URL_DETAIL = BASE + "/NationalWelfaredetailedV001"
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

# ─────────────────────────── 텔레그램 ───────────────────────────
def tg_api(method, **kwargs):
    if DRY_RUN:
        print(f"[DRY_RUN] {method}: {str(kwargs)[:150]}")
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
            data = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
                    "disable_web_page_preview": True}
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


def send_album(paths, caption):
    """카드 2장 이상은 앨범으로 묶어 발송 (첫 장에 캡션)"""
    if len(paths) == 1:
        send_photo(paths[0], caption)
        return
    for chat_id in CHAT_IDS:
        if DRY_RUN:
            print(f"[DRY_RUN] sendMediaGroup {paths} → {chat_id}")
            continue
        media = []
        files = {}
        for i, p in enumerate(paths):
            key = f"photo{i}"
            item = {"type": "photo", "media": f"attach://{key}"}
            if i == 0:
                item["caption"] = caption[:1024]
                item["parse_mode"] = "HTML"
            media.append(item)
            files[key] = open(p, "rb")
        tg_api("sendMediaGroup",
               data={"chat_id": chat_id, "media": json.dumps(media)}, files=files)
        for f in files.values():
            f.close()


def esc(s):
    return html_mod.escape(s or "")

# ─────────────────────────── 데이터 수집 ───────────────────────────
def get_welfare_list():
    items = []
    try:
        params = {"serviceKey": API_KEY, "pageNo": "1", "numOfRows": "500", "srchKeyCode": "003"}
        res = requests.get(URL_LIST, params=params, timeout=30)
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
        "id": g("servId"), "title": g("servNm"), "desc": g("servDgst"),
        "thema": g("intrsThemaArray"), "dept": g("jurMnofNm"), "link": g("servDtlLink"),
        "provide": g("srvPvsnNm"), "cycle": g("sprtCycNm"), "online": g("onapPsbltYn"),
        "regdate": g("svcfrstRegTs"),
    }


def clean_text(s, maxlen=200):
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"^[○◦•▶\-\d\.\)\s]+", "", s)
    return s[:maxlen].strip()


def fetch_detail(serv_id):
    """복지로 상세 API에서 지원대상/지원내용/신청방법을 가져온다."""
    out = {"target": "", "benefit": "", "how": ""}
    if not serv_id:
        return out
    try:
        params = {"serviceKey": API_KEY, "callTp": "D", "servId": serv_id}
        res = requests.get(URL_DETAIL, params=params, timeout=30)
        soup = BeautifulSoup(res.content, "xml")

        def g(tag):
            t = soup.find(tag)
            return t.get_text(strip=True) if t else ""
        out["target"] = clean_text(g("tgtrDtlCn"), 160)
        out["benefit"] = clean_text(g("alwServCn"), 160)
        out["how"] = clean_text(g("aplyMtdCn"), 300)
        # 일부 응답은 항목(servSeDetailNm 등) 구조 — 비어있으면 보조 필드 탐색
        if not out["how"]:
            out["how"] = clean_text(g("aplyMtdDc"), 300)
    except Exception as e:
        print(f"상세 API 오류({serv_id}): {e}")
    return out


def split_steps(how_text):
    """신청방법 텍스트를 단계로 분해 (최대 4단계)"""
    parts = re.split(r"[○◦•▶□■]|(?<=[다음됨함])\.\s+|\n", how_text or "")
    steps = []
    for p in parts:
        p = clean_text(p, 70)
        if len(p) >= 6:
            steps.append(p)
    return steps[:4]


ONLINE_STEPS = ["복지로(bokjiro.go.kr) 접속 후 로그인",
                "복지서비스 신청 메뉴에서 해당 서비스 선택",
                "신청 정보 입력 및 서류 제출",
                "처리 결과 확인 (문자·복지로 알림)"]


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
    snap = load_snapshot()
    known = snap.get("items", {}) if snap else {}
    first_run = snap is None
    week_ago = (NOW - timedelta(days=7)).strftime("%Y%m%d")
    new_items, items_out = [], {}
    for d in all_data:
        key = d["id"] or d["title"]
        if key in known:
            first_seen = known[key].get("first_seen", "")
        else:
            first_seen = "" if first_run else TODAY_STR
        d["first_seen"] = first_seen
        items_out[key] = {"title": d["title"], "first_seen": first_seen}
        is_new = (first_seen and first_seen >= week_ago) or \
                 (d["regdate"] and d["regdate"][:8] >= week_ago)
        d["is_new"] = bool(is_new)
        if is_new:
            new_items.append(d)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": NOW.strftime("%Y-%m-%d %H:%M"), "items": items_out},
                  f, ensure_ascii=False, indent=1)
    return new_items

# ─────────────────────────── 카드뉴스 (인포그래픽) ───────────────────────────
CW, CH = 1080, 1350
CREAM = (255, 250, 242)
NAVY = (43, 62, 90)
GRAY = (110, 118, 128)

THEMES = {
    "orange": {"accent": (230, 126, 34), "soft": (253, 236, 215), "banner": (230, 126, 34)},
    "blue":   {"accent": (41, 128, 185), "soft": (223, 238, 248), "banner": (43, 62, 90)},
    "teal":   {"accent": (26, 156, 130), "soft": (222, 243, 238), "banner": (26, 156, 130)},
    "pink":   {"accent": (217, 48, 110), "soft": (252, 228, 236), "banner": (194, 24, 91)},
    "purple": {"accent": (123, 97, 255), "soft": (237, 233, 254), "banner": (94, 71, 214)},
    "green":  {"accent": (46, 139, 111), "soft": (226, 242, 234), "banner": (46, 139, 111)},
}
CAT_THEME = {
    "👶 임신·출산·육아": "orange", "🎓 청년·교육": "blue", "👴 노인·어르신": "purple",
    "♿ 장애인": "green", "💰 금융·생활지원": "teal", "🏥 의료·건강": "pink",
    "👨‍👩‍👧 가족·여성": "pink", "💼 고용·일자리": "blue", "📌 기타": "green",
}

FONT_BOLD = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/malgunbd.ttf"]
FONT_REG = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/malgun.ttf"]

def get_font(size, bold=False):
    for p in (FONT_BOLD if bold else FONT_REG):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
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


def icon_person(dr, cx, cy, r, color):
    dr.ellipse([cx - r*0.32, cy - r*0.62, cx + r*0.32, cy + 0.02*r], fill=color)
    dr.pieslice([cx - r*0.62, cy - r*0.05, cx + r*0.62, cy + r*1.2], 180, 360, fill=color)

def icon_coin(dr, cx, cy, r, color):
    dr.ellipse([cx - r*0.6, cy - r*0.6, cx + r*0.6, cy + r*0.6], outline=color, width=7)
    f = get_font(int(r*0.62), True)
    dr.text((cx - f.getlength("₩")/2, cy - r*0.42), "₩", font=f, fill=color)

def icon_doc(dr, cx, cy, r, color):
    x0, y0, x1, y1 = cx - r*0.45, cy - r*0.6, cx + r*0.45, cy + r*0.6
    dr.rounded_rectangle([x0, y0, x1, y1], radius=6, outline=color, width=7)
    for yy in [0.3, 0.55, 0.8]:
        dr.line([x0 + r*0.2, y0 + (y1-y0)*yy, x1 - r*0.2, y0 + (y1-y0)*yy], fill=color, width=6)

def icon_calendar(dr, cx, cy, r, color):
    x0, y0, x1, y1 = cx - r*0.55, cy - r*0.45, cx + r*0.55, cy + r*0.55
    dr.rounded_rectangle([x0, y0, x1, y1], radius=8, outline=color, width=7)
    dr.line([x0, y0 + r*0.3, x1, y0 + r*0.3], fill=color, width=6)
    dr.line([cx - r*0.25, y0 - r*0.15, cx - r*0.25, y0 + r*0.1], fill=color, width=7)
    dr.line([cx + r*0.25, y0 - r*0.15, cx + r*0.25, y0 + r*0.1], fill=color, width=7)

ICONS = {"person": icon_person, "coin": icon_coin, "doc": icon_doc, "cal": icon_calendar}


def draw_header(dr, theme, page_label, badge="복지정보"):
    bf = get_font(30, True)
    bw = bf.getlength(badge) + 56
    dr.rounded_rectangle([60, 55, 60 + bw, 115], radius=30, fill=theme["accent"])
    dr.text((88, 66), badge, font=bf, fill=(255, 255, 255))
    pf = get_font(34)
    dr.text((CW - 60 - pf.getlength(page_label), 70), page_label, font=pf, fill=GRAY)
    df = get_font(26)
    dr.text((CW - 60 - df.getlength(NOW.strftime("%Y.%m.%d")), 120),
            NOW.strftime("%Y.%m.%d"), font=df, fill=(190, 195, 200))


def draw_banner(dr, theme, text, arrow=True):
    y0 = CH - 130
    dr.rounded_rectangle([50, y0, CW - 50, CH - 45], radius=22, fill=theme["banner"])
    nf = get_font(36, True)
    tw = nf.getlength(text)
    dr.text(((CW - tw) / 2 - (24 if arrow else 0), y0 + 22), text, font=nf, fill=(255, 255, 255))
    if arrow:
        ax, ay = (CW + tw) / 2 + 14, y0 + 43
        dr.line([ax, ay, ax + 34, ay], fill=(255, 255, 255), width=6)
        dr.line([ax + 20, ay - 12, ax + 34, ay], fill=(255, 255, 255), width=6)
        dr.line([ax + 20, ay + 12, ax + 34, ay], fill=(255, 255, 255), width=6)


def card_main(d, detail, page, filename, badge="복지정보"):
    """1장형 인포그래픽 카드: 제목 + 지원대상/내용/신청방법"""
    theme = THEMES[CAT_THEME.get(find_category(d), "green")]
    img = Image.new("RGB", (CW, CH), CREAM)
    dr = ImageDraw.Draw(img)
    draw_header(dr, theme, page, badge)

    y = 170
    tf = get_font(72, True)
    for i, line in enumerate(wrap_text(d["title"], tf, CW - 120)[:2]):
        dr.text((60, y), line, font=tf, fill=theme["accent"] if i == 0 else NAVY)
        y += 92
    y += 8
    sf = get_font(37)
    for line in wrap_text(d["desc"], sf, CW - 120)[:2]:
        dr.text((60, y), line, font=sf, fill=GRAY)
        y += 52
    y += 25

    rows = []
    if detail.get("target"):
        rows.append(("person", "지원대상", detail["target"]))
    if detail.get("benefit"):
        rows.append(("coin", "지원내용", detail["benefit"]))
    how = detail.get("how") or ("복지로(bokjiro.go.kr) 온라인 신청" if d["online"] == "Y"
                                else "읍면동 주민센터 또는 소관기관 문의")
    rows.append(("doc", "신청방법", how))
    if d["cycle"]:
        rows.append(("cal", "지원주기", d["cycle"]))
    if not rows:
        rows = [("doc", "안내", d["desc"][:100])]

    panel_top = max(y, 470)
    panel_bottom = CH - 170
    dr.rounded_rectangle([50, panel_top, CW - 50, panel_bottom], radius=28,
                         fill=(255, 255, 255), outline=(238, 233, 224), width=2)
    inner_y = panel_top + 45
    row_h = (panel_bottom - panel_top - 90) // max(1, len(rows))
    lf = get_font(36, True)
    vf = get_font(33)
    for icon, label, text in rows:
        cx, cy = 130, inner_y + 40
        dr.ellipse([cx - 44, cy - 44, cx + 44, cy + 44], fill=theme["soft"])
        ICONS[icon](dr, cx, cy, 44, theme["accent"])
        dr.text((205, inner_y - 2), label, font=lf, fill=theme["accent"])
        ty = inner_y + 50
        max_lines = max(1, (row_h - 60) // 46)
        tlines = wrap_text(text, vf, CW - 50 - 205 - 40)
        for i, line in enumerate(tlines[:max_lines]):
            if i == max_lines - 1 and len(tlines) > max_lines:
                line = line[:-1] + "…"
            dr.text((205, ty), line, font=vf, fill=(70, 78, 88))
            ty += 46
        inner_y += row_h

    banner = "복지로에서 온라인 신청 가능" if d["online"] == "Y" else "주민센터·소관기관에서 신청하세요"
    draw_banner(dr, theme, banner)
    img.save(filename)
    return filename


def card_steps(d, steps, benefit, page, filename):
    """2장째: 신청방법 단계별 안내 카드"""
    theme = THEMES[CAT_THEME.get(find_category(d), "green")]
    img = Image.new("RGB", (CW, CH), CREAM)
    dr = ImageDraw.Draw(img)
    draw_header(dr, theme, page)

    tf = get_font(54, True)
    title = d["title"] if tf.getlength(d["title"]) <= CW - 120 else \
        wrap_text(d["title"], tf, CW - 120)[0] + "…"
    dr.text((60, 160), title, font=tf, fill=NAVY)
    dr.text((60, 240), "신청방법 한눈에 보기!", font=get_font(44, True), fill=theme["accent"])

    y = 350
    bottom = CH - 320 if benefit else CH - 170
    step_h = (bottom - y) // max(1, len(steps))
    nf = get_font(38, True)
    svf = get_font(33)
    for i, stext in enumerate(steps, 1):
        cy = y + 40
        dr.ellipse([70, cy - 36, 142, cy + 36], fill=theme["accent"])
        num = f"{i:02d}"
        dr.text((106 - nf.getlength(num)/2, cy - 27), num, font=nf, fill=(255, 255, 255))
        if i < len(steps):
            dr.line([106, cy + 42, 106, y + step_h + 4], fill=theme["soft"], width=6)
        ty = y + 10
        for line in wrap_text(stext, svf, CW - 180 - 80)[:3]:
            dr.text((180, ty), line, font=svf, fill=(60, 68, 80))
            ty += 46
        y += step_h

    if benefit:
        dr.rounded_rectangle([50, CH - 300, CW - 50, CH - 160], radius=22, fill=theme["soft"])
        bf = get_font(32, True)
        dr.rounded_rectangle([70, CH - 322, 250, CH - 272], radius=10, fill=theme["accent"])
        dr.text((92, CH - 315), "지원내용", font=bf, fill=(255, 255, 255))
        vf = get_font(34, True)
        for i, line in enumerate(wrap_text(benefit, vf, CW - 160)[:2]):
            dr.text((80, CH - 250 + i * 48), line, font=vf, fill=NAVY)

    banner = "복지로에서 온라인 신청 가능" if d["online"] == "Y" else "주민센터·소관기관에서 신청하세요"
    draw_banner(dr, theme, banner)
    img.save(filename)
    return filename


def make_cards(d, prefix, badge="복지정보"):
    """내용에 따라 1~2장 자동 구성:
    신청방법이 길거나(90자 초과) 실제 단계가 3개 이상일 때만 상세 카드 추가"""
    detail = fetch_detail(d["id"])
    how_text = detail.get("how", "")
    real_steps = split_steps(how_text)
    two_pages = len(real_steps) >= 3 or len(how_text) > 90
    steps = real_steps if len(real_steps) >= 2 else \
        (ONLINE_STEPS if d["online"] == "Y" else real_steps)
    total = 2 if two_pages else 1
    paths = [card_main(d, detail, f"1/{total}", f"{prefix}_1.png", badge)]
    if two_pages:
        paths.append(card_steps(d, steps, detail.get("benefit", ""), f"2/{total}", f"{prefix}_2.png"))
    return paths, detail


def announce_caption(d, detail, prefix="📢"):
    """교회·단체방에 그대로 전달할 수 있는 안내문"""
    cap = f"{prefix} <b>[복지 안내] {esc(d['title'])}</b>\n\n"
    if detail.get("target"):
        cap += f"👤 대상: {esc(detail['target'][:80])}\n"
    if detail.get("benefit"):
        cap += f"💰 내용: {esc(detail['benefit'][:80])}\n"
    cap += ("✅ 복지로에서 온라인 신청 가능\n" if d["online"] == "Y"
            else "🏢 읍면동 주민센터 신청·문의\n")
    if d["link"]:
        cap += f"🔗 <a href=\"{esc(d['link'])}\">자세히 보기·신청 바로가기</a>\n"
    cap += "\n주변에 필요한 분께 공유해 주세요 🙏"
    return cap


def draw_summary_card(all_data, filename):
    online = [d for d in all_data if d["online"] == "Y"]
    img = Image.new("RGB", (CW, CH), (37, 47, 63))
    dr = ImageDraw.Draw(img)
    dr.text((60, 70), NOW.strftime("%Y.%m.%d") + " 복지알림봇", font=get_font(32), fill=(160, 172, 186))
    tf = get_font(62, True)
    dr.text((60, 130), "지금 온라인으로", font=tf, fill=(255, 255, 255))
    dr.text((60, 215), "신청할 수 있는 복지", font=tf, fill=(255, 255, 255))
    dr.rounded_rectangle([60, 330, CW - 60, 470], radius=24, fill=(46, 204, 113))
    cf = get_font(72, True)
    ct = f"총 {len(online)}건"
    dr.text(((CW - cf.getlength(ct)) / 2, 358), ct, font=cf, fill=(255, 255, 255))
    cats = categorize(online)
    y = 530
    lf = get_font(36)
    nf = get_font(36, True)
    palette = list(THEMES.values())
    for i, (cat_name, items) in enumerate(cats.items()):
        if not items:
            continue
        name = cat_name.split(" ", 1)[-1]
        color = palette[i % len(palette)]["accent"]
        dr.ellipse([70, y + 10, 94, y + 34], fill=color)
        dr.text((115, y), name, font=lf, fill=(220, 226, 233))
        cnt = f"{len(items)}건"
        dr.text((CW - 60 - nf.getlength(cnt), y), cnt, font=nf, fill=(255, 255, 255))
        y += 56
        if y > CH - 200:
            break
    dr.rectangle([0, CH - 80, CW, CH], fill=(46, 204, 113))
    note = "전체 목록 · 신청 링크는 아래 버튼에서 확인하세요"
    nfo = get_font(28, True)
    dr.text(((CW - nfo.getlength(note)) / 2, CH - 60), note, font=nfo, fill=(255, 255, 255))
    img.save(filename)
    return filename


def pick_daily_recommendations(all_data, n=3):
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
        msg += f"🆕 <b>새로 올라온 복지서비스 {len(new_items)}건</b> — 카드뉴스로 안내드려요!\n\n"
        for d in new_items[:10]:
            msg += f"• <b>{esc(d['title'])}</b>"
            if d["dept"]:
                msg += f" ({esc(d['dept'])})"
            msg += "\n"
        msg += "\n"
    else:
        msg += "🆕 새로 올라온 복지서비스: 오늘은 없어요\n\n"
    if recs:
        msg += f"🎯 오늘의 추천 복지 {len(recs)}건을 카드뉴스로 보내드립니다 👇\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 전체 {len(all_data)}건 | 🆕 신규 {len(new_items)}건 | ✅ 온라인신청 {len(online_items)}건"
    return msg


def build_keyboard():
    return {"inline_keyboard": [
        [{"text": "📋 전체 목록", "url": WEB_URL},
         {"text": "✅ 온라인신청만", "url": WEB_URL + "?online=1"}],
        [{"text": "🏛 복지로 홈", "url": BOKJIRO_URL},
         {"text": "🔍 복지서비스 검색", "url": WEB_URL + "?focus=search"}],
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

    for i, (cat_name, items) in enumerate(categorize(all_data).items()):
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
        print("⚠️ API 응답 없음")
        send_message("⚠️ 복지알림봇: 오늘 복지로 API 응답이 없어 브리핑을 만들지 못했어요. 내일 다시 시도합니다.")
        return

    new_items = detect_new(all_data)
    recs = pick_daily_recommendations(all_data, 3)

    # 1) 브리핑 메시지 + 메뉴
    send_message(build_message(all_data, new_items, recs), keyboard=build_keyboard())

    # 2) 신규 복지 카드뉴스 (최대 5건, 내용에 따라 1~2장)
    for i, d in enumerate(new_items[:5]):
        paths, detail = make_cards(d, f"card_new_{i}", badge="NEW 신규복지")
        send_album(paths, announce_caption(d, detail, "🆕"))

    # 3) 오늘의 추천 카드뉴스 (로테이션 3건, 내용에 따라 1~2장)
    for i, d in enumerate(recs):
        paths, detail = make_cards(d, f"card_rec_{i}")
        send_album(paths, announce_caption(d, detail, "🎯"))

    # 4) 온라인신청 요약 카드
    f = draw_summary_card(all_data, "card_summary.png")
    online_count = len([d for d in all_data if d["online"] == "Y"])
    send_photo(f, f"✅ <b>지금 온라인으로 신청 가능한 복지 {online_count}건</b>\n"
                  f"🔗 <a href=\"{WEB_URL}?online=1\">전체 목록 · 신청 링크 보기</a>")

    generate_html(all_data, new_items)
    print(f"✅ 완료 - 전체 {len(all_data)}, 신규 {len(new_items)}, 추천 {len(recs)}")


if __name__ == "__main__":
    main()
