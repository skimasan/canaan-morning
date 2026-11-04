# Canaan morning Story - runs in a Claude cloud session, no Mac needed.
#   python3 story.py verse "Фил 3:13-14" [--use=yv|db]   text from the database, checked against saved YouVersion data
#   python3 story.py find "забывая заднее"          find an address by words
#   python3 story.py photos "sunrise mountain mist" numbered contact sheet from Pixabay: .tmp/sheet.jpg
#   python3 story.py render "Фил 3:13-14" <number> [--tone=warm|cool] [--date=YYYY-MM-DD] [--use=yv|db]
#   python3 story.py check                          check the Instagram key, nothing is published
#   python3 story.py publish YYYY-MM-DD             publish the pushed story.jpg to Instagram Stories
# Keys are not in this repository: the cloud proxy adds the Instagram key, the Pixabay key is the environment variable PIXABAY_KEY.
# Any problem stops the run. Nothing is guessed.
import base64, datetime as D, hashlib, html, json, os, pathlib, re, shutil, sqlite3, subprocess, sys, time, urllib.error as E, urllib.parse as P, urllib.request as U

try:
    from PIL import Image, ImageDraw
except ImportError:
    # The cloud default python3 cannot load the system Pillow, /usr/bin/python3 can
    if sys.executable != "/usr/bin/python3" and os.path.exists("/usr/bin/python3"):
        os.execv("/usr/bin/python3", ["/usr/bin/python3", *sys.argv])
    raise

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
BIBLE = ROOT / "bible"
STORIES = ROOT / "stories"
USED = ROOT / "used_photos.json"
TMP = ROOT / ".tmp"
RAW = "https://raw.githubusercontent.com/skimasan/canaan-morning/main/stories"
IG = "https://graph.instagram.com/v26.0"
PIXABAY = "https://pixabay.com/api/"
WEATHER = "https://api.open-meteo.com/v1/forecast?latitude=43.2389&longitude=76.8897&current=temperature_2m,weather_code&daily=temperature_2m_max&timezone=Asia/Almaty&forecast_days=3"
ALMATY = D.timezone(D.timedelta(hours=5))
MIN_W, MIN_H = 700, 1100
LARGE = 1280  # Pixabay gives this size on the long side
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
WEEK = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# canonical Russian book name in the database, YouVersion code, other spellings
BOOKS = [
    ("Бытие", "GEN", "Быт"), ("Исход", "EXO", "Исх"), ("Левит", "LEV", "Лев"), ("Числа", "NUM", "Чис|Числ"), ("Второзаконие", "DEU", "Втор"),
    ("Иисуса Навина", "JOS", "Иисус Навин|Нав"), ("Судей", "JDG", "Суд"), ("Руфь", "RUT", "Руф"),
    ("1-я Царств", "1SA", "1-Царств|1 Царств|1Царств|1Цар|1 Цар"), ("2-я Царств", "2SA", "2-Царств|2 Царств|2Царств|2Цар|2 Цар"),
    ("3-я Царств", "1KI", "3-Царств|3 Царств|3Царств|3Цар|3 Цар"), ("4-я Царств", "2KI", "4-Царств|4 Царств|4Царств|4Цар|4 Цар"),
    ("1-я Паралипоменон", "1CH", "1-Паралипоменон|1 Паралипоменон|1Пар|1 Пар"), ("2-я Паралипоменон", "2CH", "2-Паралипоменон|2 Паралипоменон|2Пар|2 Пар"),
    ("Ездры", "EZR", "Ездра|Езд"), ("Неемии", "NEH", "Неемия|Неем"), ("Есфирь", "EST", "Есф"), ("Иов", "JOB", "Иова"), ("Псалтирь", "PSA", "Псалом|Псалмы|Пс"),
    ("Притчи", "PRO", "Притч|Прит"), ("Екклесиаст", "ECC", "Еккл"), ("Песнь Песней", "SNG", "Песн"), ("Исаия", "ISA", "Исаии|Ис"), ("Иеремия", "JER", "Иеремии|Иер"),
    ("Плач Иеремии", "LAM", "Плач"), ("Иезекииль", "EZK", "Иезекииля|Иез"), ("Даниил", "DAN", "Даниила|Дан"), ("Осия", "HOS", "Осии|Ос"), ("Иоиль", "JOL", "Иоиля|Иоил"),
    ("Амос", "AMO", "Амоса|Ам"), ("Авдий", "OBA", "Авдия|Авд"), ("Иона", "JON", "Ионы|Ион"), ("Михей", "MIC", "Михея|Мих"), ("Наум", "NAM", "Наума"),
    ("Аввакум", "HAB", "Аввакума|Авв"), ("Софония", "ZEP", "Софонии|Соф"), ("Аггей", "HAG", "Аггея|Агг"), ("Захария", "ZEC", "Захарии|Зах"), ("Малахия", "MAL", "Малахии|Мал"),
    ("Матфей", "MAT", "Матфея|Мф|Мат"), ("Марк", "MRK", "Марка|Мк|Мар"), ("Лука", "LUK", "Луки|Лк|Лук"), ("Иоанн", "JHN", "Иоанна|Ин|Иоан"), ("Деяния", "ACT", "Деян"),
    ("Иакову", "JAS", "Иакова|Иак"), ("1-е Петру", "1PE", "1-Петра|1 Петра|1-Петру|1 Петру|1Пет|1 Пет"), ("2-е Петру", "2PE", "2-Петра|2 Петра|2-Петру|2 Петру|2Пет|2 Пет"),
    ("1-е Иоанну", "1JN", "1-Иоанна|1 Иоанна|1-Иоанну|1 Иоанну|1Ин|1 Ин"), ("2-е Иоанну", "2JN", "2-Иоанна|2 Иоанна|2-Иоанну|2 Иоанну|2Ин|2 Ин"), ("3-е Иоанну", "3JN", "3-Иоанна|3 Иоанна|3-Иоанну|3 Иоанну|3Ин|3 Ин"),
    ("Иуде", "JUD", "Иуды|Иуд"), ("Римлянам", "ROM", "Рим"), ("1-е Коринфянам", "1CO", "1-Коринфянам|1 Коринфянам|1Кор|1 Кор"), ("2-е Коринфянам", "2CO", "2-Коринфянам|2 Коринфянам|2Кор|2 Кор"),
    ("Галатам", "GAL", "Гал"), ("Ефесянам", "EPH", "Еф|Ефес"), ("Филиппийцам", "PHP", "Флп|Фил"), ("Колоссянам", "COL", "Кол"),
    ("1-е Фессалоникийцам", "1TH", "1-Фессалоникийцам|1 Фессалоникийцам|1Фес|1 Фес"), ("2-е Фессалоникийцам", "2TH", "2-Фессалоникийцам|2 Фессалоникийцам|2Фес|2 Фес"),
    ("1-е Тимофею", "1TI", "1-Тимофею|1 Тимофею|1Тим|1 Тим"), ("2-е Тимофею", "2TI", "2-Тимофею|2 Тимофею|2Тим|2 Тим"), ("Титу", "TIT", "Тит"), ("Филимону", "PHM", "Флм"),
    ("Евреям", "HEB", "Евр"), ("Откровение", "REV", "Откр"),
]
ALIAS = {}
for ru, code, other in BOOKS:
    for name in [ru] + other.split("|"):
        ALIAS[name.lower().replace(".", "").strip()] = (ru, code)
# book label on the Story, where it differs from the database name
LABELS = {"Матфей": "МАТФЕЯ", "Марк": "МАРКА", "Лука": "ЛУКИ", "Иоанн": "ИОАННА", "Иакову": "ИАКОВА", "Иуде": "ИУДЫ", "Псалтирь": "ПСАЛОМ",
          "1-е Петру": "1 ПЕТРА", "2-е Петру": "2 ПЕТРА", "1-е Иоанну": "1 ИОАННА", "2-е Иоанну": "2 ИОАННА", "3-е Иоанну": "3 ИОАННА"}
TONES = {"warm": ("#4A3216", "50, 30, 10"), "cool": ("#0F2238", "10, 22, 45")}
ICONS = {
    "sun": '<circle cx="22" cy="22" r="7"></circle><path d="M22 6v5M22 33v5M6 22h5M33 22h5M10.7 10.7l3.5 3.5M29.8 29.8l3.5 3.5M33.3 10.7l-3.5 3.5M14.2 29.8l-3.5 3.5"></path>',
    "partly": '<circle cx="15" cy="15" r="5"></circle><path d="M15 4v3M4 15h3M7.2 7.2l2.1 2.1M22.8 7.2l-2.1 2.1"></path><path d="M16 36a7 7 0 0 1 0-14 9.5 9.5 0 0 1 18 2.5 5.8 5.8 0 0 1-1 11.5z"></path>',
    "cloud": '<path d="M13 32a8 8 0 0 1 0-16 11 11 0 0 1 21 3 6.5 6.5 0 0 1-1 13z"></path>',
    "fog": '<path d="M13 24a7 7 0 0 1 0-14 10 10 0 0 1 19 3 5.5 5.5 0 0 1-1 11z"></path><path d="M8 31h28M13 37h18"></path>',
    "rain": '<path d="M13 26a7 7 0 0 1 0-14 10 10 0 0 1 19 3 5.5 5.5 0 0 1-1 11z"></path><path d="M15 32l-2 6M23 32l-2 6M31 32l-2 6"></path>',
    "snow": '<path d="M13 26a7 7 0 0 1 0-14 10 10 0 0 1 19 3 5.5 5.5 0 0 1-1 11z"></path><path d="M15 33v5M12.8 35.5h4.4M23 33v5M20.8 35.5h4.4M31 33v5M28.8 35.5h4.4"></path>',
    "storm": '<path d="M13 26a7 7 0 0 1 0-14 10 10 0 0 1 19 3 5.5 5.5 0 0 1-1 11z"></path><path d="M24 29l-5 6h6l-4 6"></path>',
}


class Stop(Exception):
    pass


def today():
    return D.datetime.now(ALMATY).date().isoformat()


def get_json(url, data=None, headers=None, method=None):
    head = {"User-Agent": "canaan-morning", **(headers or {})}
    token = os.environ.get("IG_TOKEN") if url.startswith(IG) else None  # local tests only, in the cloud the proxy adds the key
    if token:
        head["Authorization"] = f"Bearer {token}"
    req = U.Request(url, data=data, headers=head, method=method)
    try:
        with U.urlopen(req, timeout=40) as r:
            return json.load(r)
    except E.HTTPError as e:
        raise Stop(f"{url.split('?')[0]} answered {e.code}: {e.read()[:400].decode(errors='replace')}")


# ---------- Bible ----------

def open_db():
    path = BIBLE / "syno.sqlite"
    want = (BIBLE / "syno.sqlite.sha256").read_text().strip()
    if hashlib.sha256(path.read_bytes()).hexdigest() != want:
        raise Stop("The Bible database changed. Its checksum does not match.")
    return sqlite3.connect(path)


def parse_ref(ref):
    """'Фил 3:13-14', 'Ин 3:16' or 'Ис 40:31 - 41:2' -> (book, code, label, (c1, v1), (c2, v2))"""
    m = re.fullmatch(r"(.+?)\s+(\d+):(\d+)(?:\s*-\s*(?:(\d+):)?(\d+))?", ref.strip().replace("–", "-").replace("—", "-"))
    if not m:
        raise Stop(f"Cannot read reference: {ref}")
    key = m[1].lower().replace(".", "").strip()
    if key not in ALIAS:
        raise Stop(f"Unknown book name: {m[1]}")
    ru, code = ALIAS[key]
    c1, v1 = int(m[2]), int(m[3])
    c2, v2 = int(m[4] or c1), int(m[5] or v1)
    name = LABELS.get(ru, re.sub(r"^(\d)-[яе] ", r"\1 ", ru).upper())
    span = f"{c1}:{v1}" if (c1, v1) == (c2, v2) else f"{c1}:{v1}-{v2}" if c1 == c2 else f"{c1}:{v1}-{c2}:{v2}"
    return ru, code, f"{name} {span}", (c1, v1), (c2, v2)


def check_youversion(code, rows, use):
    """Each verse must match YouVersion SYNO. Accents, ё and reading marks do not count.
    A real difference stops the run, so Kim can choose. use='yv' or 'db' is that choice. Returns the verses to print."""
    saved = json.loads((BIBLE / "yv_all.json").read_text())
    accepted = json.loads((BIBLE / "accepted.json").read_text())
    differs = json.loads((BIBLE / "yv_diff.json").read_text())
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:8]
    out = []
    for ch, v, t in rows:
        key = f"{code}.{ch}"
        got = saved.get(key, {}).get(str(v))
        if not got:
            raise Stop(f"Not checked against YouVersion: {key}:{v}. Text in the database: {t}")
        words = re.sub(r"[^а-я0-9]", "", t.lower().replace("ё", "е"))
        same = h(words) == got[:8] and h(re.sub(r"\s+", "", t)) == got[8:]
        other = differs.get(f"{key}.{v}")
        if same or f"{key}.{v}" in accepted or not other:
            out.append(t)
        elif use == "yv":
            out.append(other)
        elif use == "db":
            out.append(t)
        else:
            raise Stop(f"Text differs from YouVersion SYNO: {key}:{v}.\nYouVersion: {other}\nDatabase: {t}")
    return out


def read_verses(ref, use=None):
    ru, code, label, a, b = parse_ref(ref)
    rows = open_db().execute("select chapter, verse, text from verses where book_ru=? and (chapter>? or (chapter=? and verse>=?)) and (chapter<? or (chapter=? and verse<=?)) order by chapter, verse",
                             (ru, a[0], a[0], a[1], b[0], b[0], b[1])).fetchall()
    if not rows or (rows[0][0], rows[0][1]) != a or (rows[-1][0], rows[-1][1]) != b:
        raise Stop(f"Verses not found: {ref}")
    if any(not t.strip() for _, _, t in rows):
        raise Stop(f"Empty verse in: {ref}")
    return label, " ".join(re.sub(r"\s+", " ", t).strip() for t in check_youversion(code, rows, use))


def find(words):
    norm = lambda s: re.sub(r"[^а-я0-9]", "", s.lower().replace("ё", "е"))
    want = norm(words)
    return [f"{b} {c}:{v}" for b, c, v, t in open_db().execute("select book_ru, chapter, verse, text from verses") if want in norm(t)]


# ---------- weather ----------

def wmo(code):
    if code == 0: return "ясно", "sun"
    if code in (1, 2): return "малооблачно", "partly"
    if code == 3: return "облачно", "cloud"
    if code in (45, 48): return "туман", "fog"
    if 51 <= code <= 57: return "морось", "rain"
    if 61 <= code <= 67 or 80 <= code <= 82: return "дождь", "rain"
    if 71 <= code <= 77 or code in (85, 86): return "снег", "snow"
    if code >= 95: return "гроза", "storm"
    raise Stop(f"Unknown weather code: {code}")


def deg(x):
    n = round(x)
    return f"+{n}°" if n > 0 else f"{n}°"


def weather(day):
    d = get_json(WEATHER)
    days = d["daily"]["time"]
    if day not in days:
        raise Stop(f"No forecast for {day}")
    word, icon = wmo(d["current"]["weather_code"])
    return {"now": deg(d["current"]["temperature_2m"]), "word": word, "icon": icon, "day": deg(d["daily"]["temperature_2m_max"][days.index(day)]), "at": d["current"]["time"]}


# ---------- photos ----------

def photos(query):
    key = os.environ.get("PIXABAY_KEY")
    if not key:
        raise Stop("PIXABAY_KEY is not set in this environment")
    d = get_json(PIXABAY + "?" + P.urlencode({"key": key, "q": query, "image_type": "photo", "orientation": "vertical", "safesearch": "true", "order": "popular", "per_page": 60, "min_width": MIN_W, "min_height": MIN_H}))
    used = json.loads(USED.read_text()) if USED.exists() else {}
    seen = {v["photo_id"] for v in used.values() if v.get("photo_id")}
    wide = lambda p: p["imageWidth"] * LARGE / p["imageHeight"] >= MIN_W
    rows = [p for p in d["hits"] if p["id"] not in seen and wide(p) and not p.get("isAiGenerated") and not p.get("isLowQuality")][:12]
    if not rows:
        raise Stop(f"No new photos for: {query}")
    TMP.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (4 * 300, 3 * 500), "#111111")
    pen = ImageDraw.Draw(sheet)
    for i, p in enumerate(rows):
        f = TMP / f"thumb{i + 1}.jpg"
        req = U.Request(p["webformatURL"], headers={"User-Agent": "canaan-morning"})
        f.write_bytes(U.urlopen(req, timeout=40).read())
        im = Image.open(f).convert("RGB")
        im.thumbnail((296, 496))
        x, y = (i % 4) * 300 + 2, (i // 4) * 500 + 2
        sheet.paste(im, (x, y))
        pen.rectangle((x, y, x + 52, y + 34), fill="#000000")
        pen.text((x + 8, y + 8), str(i + 1), fill="#ffffff", font_size=24)
    sheet.save(TMP / "sheet.jpg", quality=88)
    (TMP / "photos.json").write_text(json.dumps([{"n": i + 1, "id": p["id"], "url": p["pageURL"], "author": p["user"], "tags": p.get("tags", ""), "src": p["largeImageURL"]} for i, p in enumerate(rows)], ensure_ascii=False, indent=1))
    print(json.dumps({"sheet": str(TMP / "sheet.jpg"), "list": str(TMP / "photos.json"), "photos": [{"n": i + 1, "tags": p.get("tags", "")} for i, p in enumerate(rows)]}, ensure_ascii=False))


def fetch_photo(n):
    rows = {r["n"]: r for r in json.loads((TMP / "photos.json").read_text())}
    if n not in rows:
        raise Stop(f"No photo number {n}. Run photos first.")
    r = rows[n]
    f = TMP / "photo.jpg"
    f.write_bytes(U.urlopen(U.Request(r["src"], headers={"User-Agent": "canaan-morning"}), timeout=60).read())
    return f, r


# ---------- Story ----------

def fit(text):
    """Font size for the verse box. A longer verse is never cut: it stops the run."""
    n = len(text)
    for limit, size in ((170, 20), (225, 18), (300, 16.5), (380, 15)):
        if n <= limit:
            return size
    raise Stop(f"Verse is too long for one Story: {n} characters. Ask Kim.")


def nb(text):
    """Short words stay with the next word. Layout only, the letters do not change."""
    return re.sub(r"(?<![а-яА-ЯёЁ])([а-яА-ЯёЁ]{1,2}) ", "\\1\u00a0", html.escape(text, quote=False))


def card(day, wx, label, text, photo, tone):
    """The title is a ready image from the Mac, so the Story looks the same without the Mac fonts."""
    d = D.date.fromisoformat(day)
    base, shade = TONES[tone]
    when = f"{WEEK[d.weekday()]} · {d.day} {MONTHS[d.month - 1]}".upper()
    return f"""<div style="width: 450px; height: 800px; box-sizing: border-box; padding: 44px 40px 48px; background: {base}; color: #FFF4E0; display: flex; flex-direction: column; align-items: center; text-align: center; font-family: 'Manrope', sans-serif; position: relative; overflow: hidden">
<img src="{photo}" alt="" style="position: absolute; top: 0; left: 0; width: 450px; height: 800px; object-fit: cover">
<div style="position: absolute; top: 0; left: 0; width: 450px; height: 800px; background: linear-gradient(to bottom, rgba({shade}, 0.62), rgba({shade}, 0.44) 45%, rgba({shade}, 0.6))"></div>
<img src="{(ASSETS / 'title.png').as_uri()}" alt="" style="position: absolute; top: 0; left: 0; width: 450px; height: 800px">
<img src="{(ASSETS / 'logo.svg').as_uri()}" alt="Canaan" style="position: relative; width: 104px; height: 54px">
<div style="position: relative; margin-top: 18px; align-self: stretch; display: flex; align-items: center; gap: 16px; font-size: 14px; font-weight: 700; letter-spacing: 3px; text-shadow: 0 1px 8px rgba({shade}, 0.6)">
<div style="flex-grow: 1; height: 1px; background: #FFF4E0; opacity: 0.7"></div>
<span>{when}</span>
<div style="flex-grow: 1; height: 1px; background: #FFF4E0; opacity: 0.7"></div>
</div>
<div style="position: relative; margin-top: 18px; display: flex; flex-direction: column; align-items: center; gap: 6px; text-shadow: 0 1px 8px rgba({shade}, 0.6)">
<div style="display: flex; align-items: center; justify-content: center; gap: 12px">
<svg width="34" height="34" viewBox="0 0 44 44" fill="none" stroke="#FFF4E0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[wx['icon']]}</svg>
<div style="font-size: 22px; font-weight: 700">{wx['now']} {wx['word']}</div>
</div>
<div style="font-size: 15px; font-weight: 500">днём {wx['day']}</div>
</div>
<div id="box" style="position: relative; margin-top: auto; align-self: stretch; padding: 16px 20px 20px; border: 2px solid #FFF4E0; border-radius: 20px; background: rgba({shade}, 0.6); backdrop-filter: blur(6px)">
<div style="font-size: 13px; font-weight: 700; letter-spacing: 3px; padding-left: 3px">{label}</div>
<div style="margin-top: 8px; font-weight: 500; font-size: {fit(text)}px; line-height: 1.38">{nb(text)}</div>
</div>
</div>"""


def page(body):
    font = base64.b64encode((ASSETS / "Manrope.woff2").read_bytes()).decode()
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
@font-face{{font-family:Manrope;src:url(data:font/woff2;base64,{font}) format('woff2');font-weight:200 800}}
body{{margin:0}}</style></head><body>{body}</body></html>"""


def chrome_path():
    for p in (os.environ.get("CHROME_PATH"), "/usr/bin/google-chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("chromium")):
        if p and os.path.exists(p):
            return p
    raise Stop("Chrome is not installed")


def chrome(args, doc):
    TMP.mkdir(exist_ok=True)
    f = TMP / "story.html"
    f.write_text(doc)
    return subprocess.run([chrome_path(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2.4", "--window-size=450,800",
                           "--allow-file-access-from-files", "--virtual-time-budget=4000", *args, f.as_uri()], capture_output=True, text=True, timeout=120)


def render(ref, n, day, tone, use=None):
    if D.date.fromisoformat(day).weekday() >= 5:
        raise Stop(f"{day} is not a weekday")
    label, text = read_verses(ref, use)
    photo, info = fetch_photo(n)
    size = Image.open(photo).size
    if size[0] < MIN_W or size[1] < MIN_H or size[1] <= size[0]:
        raise Stop(f"Photo is too small or not vertical: {size}")
    wx = weather(day)
    doc = page(card(day, wx, label, text, photo.as_uri(), tone))
    png = TMP / "story.png"
    png.unlink(missing_ok=True)
    r = chrome([f"--screenshot={png}"], doc)
    if not png.exists():
        raise Stop(f"Chrome did not render: {r.stderr[-300:]}")
    if Image.open(png).size != (1080, 1920):
        raise Stop(f"Wrong Story size: {Image.open(png).size}")
    probe = doc.replace("</body>", "<script>const b=document.getElementById('box').getBoundingClientRect();document.body.dataset.box=Math.round(b.bottom)+','+Math.round(b.top)</script></body>")
    m = re.search(r'data-box="(\d+),(\d+)"', chrome(["--dump-dom"], probe).stdout)
    if not m or int(m[1]) > 760 or int(m[2]) < 470:
        raise Stop(f"Verse box does not fit: {m and m.groups()}")
    folder = STORIES / day
    folder.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert("RGB").save(folder / "story.jpg", quality=93, subsampling=0)
    (folder / "meta.json").write_text(json.dumps({"date": day, "ref": ref, "label": label, "text": text, "weather": wx, "photo": info["url"], "photo_id": info["id"], "author": info["author"], "tone": tone}, ensure_ascii=False, indent=1))
    used = json.loads(USED.read_text()) if USED.exists() else {}
    used[day] = {"photo_id": info["id"]}
    USED.write_text(json.dumps(used, indent=1))
    print(json.dumps({"jpg": str(folder / "story.jpg"), "label": label, "weather": wx, "chars": len(text), "url_after_push": f"{RAW}/{day}/story.jpg"}, ensure_ascii=False))


def publish(day):
    folder = STORIES / day
    meta = json.loads((folder / "meta.json").read_text())
    if meta.get("permalink") or meta.get("media_id"):
        raise Stop(f"Already published: {meta.get('permalink') or meta.get('media_id')}")
    url = f"{RAW}/{day}/story.jpg"
    made = get_json(f"{IG}/me/media", data=P.urlencode({"media_type": "STORIES", "image_url": url}).encode(), method="POST")["id"]
    for _ in range(36):
        code = get_json(f"{IG}/{made}?fields=status_code,status")
        if code.get("status_code") == "FINISHED":
            break
        if code.get("status_code") in ("ERROR", "EXPIRED"):
            raise Stop(f"Instagram did not accept the file: {code}")
        time.sleep(5)
    else:
        raise Stop("Instagram took too long")
    media = get_json(f"{IG}/me/media_publish", data=P.urlencode({"creation_id": made}).encode(), method="POST")["id"]
    link = get_json(f"{IG}/{media}?fields=permalink").get("permalink")
    meta.update(media_id=media, permalink=link)
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps({"media_id": media, "permalink": link}))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    day = opt.get("date", today())
    if a[0] == "verse":
        label, text = read_verses(a[1], opt.get("use"))
        print(json.dumps({"label": label, "text": text, "chars": len(text), "font": fit(text)}, ensure_ascii=False))
    elif a[0] == "find":
        print(json.dumps(find(a[1]), ensure_ascii=False))
    elif a[0] == "check":
        name = get_json(f"{IG}/me?fields=username").get("username")
        if name != "canaan_acc":
            raise Stop(f"Instagram key belongs to another account: {name}")
        print("OK: Instagram key works for canaan_acc")
    elif a[0] == "photos":
        photos(a[1])
    elif a[0] == "render":
        render(a[1], int(a[2]), day, opt.get("tone", "warm"), opt.get("use"))
    elif a[0] == "publish":
        publish(a[1])
    else:
        raise Stop(f"Unknown command: {a[0]}")


if __name__ == "__main__":
    try:
        main()
    except Stop as e:
        sys.exit(f"STOP: {e}")
