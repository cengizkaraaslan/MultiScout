"""Axess (Akbank) kampanya scraper — axess.com.tr/kampanyalar

ASP.NET WebForms tabanlı klasik server-side render. Ana sayfa
`/kampanyalar` SADECE 6 öne çıkan kampanyayı carousel'de gösterir; gerçek
kampanya listesi `/ajax/kampanya-ajax.aspx` endpoint'inden çekilir.

Carousel kartı (sadece link + img):
  <div class="boutique owl-carousel">
    <div><a href="/axess/kampanyalar/<slug>"><img src="..." /></a></div>

Ajax kartı (link + img + desc, BAŞLIK YOK!):
  <div class="grid-3"><div class="campaingBox"><div class="campaing">
      <div class="imgArea"><img src="..." /></div>
      <div class="textArea">
          <p> AÇIKLAMA İLK SATIRI...</p>
          <a href="/axess/kampanyalar/<slug>" class="dLink">...

Title: hem carousel hem ajax kartlarında YOK. Slug'tan türetiyoruz
(kebab-case → Title Case + Türkçe karakter düzeltme). Açıklamanın ilk
cümlesini desc olarak tutup price extraction'da kullanıyoruz.

Filtre/kategori sayfaları (`/axess/kampanyalar/chip-para-kampanyalari`
vb.) aynı template'in yeniden render edilmiş halidir — kart listesi
sunucu tarafında değişmez, yine 6 carousel kartı çıkar. Kategori
filtresi ajax POST + categoryId ile yapılıyor ama VIEWSTATE
gerektirdiği için server-side scrape için pratik değil. Bu yüzden
genel ajax endpoint'i + carousel hep birlikte kullanılıyor.

Statik HTML yeterli; Playwright gerekmez. Site identity response
dönse de gzip/deflate decode yolu Turkcell scraper'ından kopyalanmış.
"""
import asyncio
import gzip
import re
import ssl
import urllib.error
import urllib.request
import zlib
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.axess.com.tr"
# Sırasıyla dene — ilk 200 dönen ana liste URL'i kullanılır.
CANDIDATE_LIST_URLS = [
    f"{BASE}/kampanyalar",
    f"{BASE}/firsatlar",
    f"{BASE}/",
]
AJAX_URL = f"{BASE}/ajax/kampanya-ajax.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}
_SSL_CTX = ssl.create_default_context()

# Carousel kartı: <a href="/axess/kampanyalar/<slug>"><img src="..." alt="..." /></a>
# (boutique owl-carousel içinde, /upload/CmsCampaign/.../detay... görseli)
_CAROUSEL_RE = re.compile(
    r'<a href="(/axess/kampanyalar/[a-z0-9-]+)">\s*'
    r'<img src="([^"]+)"[^>]*alt="([^"]*)"',
    re.DOTALL,
)

# Ajax kartı: campaingBox > campaing > imgArea + textArea > <p>desc</p> + <a href dLink>
_AJAX_CARD_RE = re.compile(
    r'<div class="campaingBox">(.*?)</div>\s*</div>\s*</div>',
    re.DOTALL,
)
_AJAX_IMG_RE = re.compile(
    r'<div class="imgArea">\s*<img src="([^"]+)"',
    re.DOTALL,
)
_AJAX_DESC_RE = re.compile(
    r'<div class="textArea">\s*<p>(.*?)</p>',
    re.DOTALL,
)
_AJAX_LINK_RE = re.compile(
    r'<a href="(/axess/kampanyalar/[a-z0-9-]+)"\s+class="dLink"',
    re.DOTALL,
)


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    s = s.replace("\xa0", " ").replace("​", "")
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def _fetch(url: str, timeout: int = 25, extra_headers: dict | None = None) -> str | None:
    try:
        headers = dict(HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return raw.decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[Axess] fetch error {url}: {e}", flush=True)
        return None


def _ascii_lower(s: str) -> str:
    return (
        s.lower()
        .replace("ı", "i").replace("İ", "i")
        .replace("ş", "s").replace("Ş", "s")
        .replace("ç", "c").replace("Ç", "c")
        .replace("ğ", "g").replace("Ğ", "g")
        .replace("ü", "u").replace("Ü", "u")
        .replace("ö", "o").replace("Ö", "o")
    )


# Slug → Başlık dönüşümü için kelime düzeltmeleri (özel isimler + sık geçen
# kalıplar). Slug ASCII; Türkçe karakter geri yüklemiyoruz (overkill).
_TITLE_FIXES = {
    "axess": "Axess",
    "axesse": "Axess'e",
    "axessten": "Axess'ten",
    "akbank": "Akbank",
    "akbanklilar": "Akbanklılar",
    "juzdan": "Juzdan",
    "juzdana": "Juzdan'a",
    "chip": "Chip",
    "para": "para",
    "chip-para": "Chip-para",
    "tl": "TL",
    "tlye": "TL'ye",
    "tlye-varan": "TL'ye Varan",
    "ye": "'ye",
    "ile": "ile",
    "ozel": "Özel",
    "mayis": "Mayıs",
    "nisan": "Nisan",
    "haziran": "Haziran",
    "temmuz": "Temmuz",
    "ogrenci": "Öğrenci",
    "kartina": "Kartına",
    "varan": "Varan",
    "kazaniyor": "Kazanıyor",
    "kazaniyorlar": "Kazanıyorlar",
    "simdi": "Şimdi",
    "basvuran": "Başvuran",
    "fatura": "Fatura",
    "talimatlarina": "Talimatlarına",
    "egitim": "Eğitim",
    "sektoru": "Sektörü",
    "kapsaminda": "Kapsamında",
    "okul": "Okul",
    "odemelerinde": "Ödemelerinde",
    "taksitli": "Taksitli",
    "islemlerde": "İşlemlerde",
    "taksit": "Taksit",
    "pesin": "Peşin",
    "fiyatina": "Fiyatına",
    "alisverislerinize": "Alışverişlerinize",
    "alisverislerinde": "Alışverişlerinde",
    "kampanyalari": "Kampanyaları",
    "indirim": "İndirim",
    "indirimi": "İndirimi",
    "firsati": "Fırsatı",
    "firsatlar": "Fırsatlar",
    "harcamalariniza": "Harcamalarınıza",
    "harcamalarinda": "Harcamalarında",
    "sigorta": "Sigorta",
    "klima": "Klima",
    "alimlarinda": "Alımlarında",
    "yetkili": "Yetkili",
    "magaza": "Mağaza",
    "magazalari": "Mağazaları",
    "kazandiriyor": "Kazandırıyor",
    "imkani": "İmkanı",
    "kadar": "Kadar",
    "logolu": "Logolu",
    "kartlariniza": "Kartlarınıza",
    "kartlarinla": "Kartlarınla",
    "evideada": "Evidea'da",
    "vestelde": "Vestel'de",
    "isbir": "İşbir",
    "yatakta": "Yatakta",
    "marvyde": "Marvy'de",
    "tatilsepetinde": "Tatilsepeti'nde",
    "finessete": "Finesse'te",
    "hotelste": "Hotels'te",
    "prometeonda": "Prometeon'da",
    "giyim": "Giyim",
    "odeye": "Ödeye",
    "ode": "Öde",
    "troy": "Troy",
}


def _slugify_title(slug: str) -> str:
    """`/axess/kampanyalar/<slug>` formundaki path'ten okunaklı başlık üret."""
    name = slug.rstrip("/").rsplit("/", 1)[-1]
    # "chip-para" bigram'ını tek token olarak koru
    name = name.replace("chip-para", "chippara")
    parts = name.split("-")
    out = []
    for p in parts:
        if not p:
            continue
        if p == "chippara":
            out.append("Chip-para")
            continue
        if p.isdigit() or re.fullmatch(r"\d+", p):
            out.append(p)
            continue
        fixed = _TITLE_FIXES.get(p)
        if fixed:
            out.append(fixed)
            continue
        # Sayı + harf karışımı (örn. "10000", "7500", "1200")
        out.append(p.capitalize())
    title = " ".join(out)
    # "100000 Tl" → "100.000 TL", "7500 Tl" → "7.500 TL"
    title = re.sub(r"\bTl\b", "TL", title)
    title = re.sub(
        r"\b(\d{4,})\b",
        lambda m: f"{int(m.group(1)):,}".replace(",", "."),
        title,
    )
    # "Tl'ye Varan" zaten doğru; iki noktayı normalize et
    title = re.sub(r"\s+", " ", title).strip()
    return title[:180]


def _detect_category(title: str, desc: str, slug: str) -> str:
    blob = _ascii_lower(title + " | " + desc + " | " + slug)
    if "chargeback" in blob:
        return "chargeback"
    if "chip-para" in blob or "chip para" in blob:
        return "chip-para"
    if "sinema" in blob or "film" in blob:
        return "sinema"
    if "restoran" in blob or "yemek" in blob or "lezzet" in blob:
        return "restoran"
    if "market" in blob or "gida" in blob or "migros" in blob or "carrefour" in blob:
        return "market"
    if (
        "seyahat" in blob or "otel" in blob or "tatil" in blob
        or "havayolu" in blob or "rezervasyon" in blob or "hotels" in blob
    ):
        return "seyahat"
    if "taksit" in blob:
        return "taksit"
    return "kampanya"


def _extract_price(title: str, desc: str) -> str:
    """Title + desc'ten anlamlı bir teaser çıkar (banka kampanyaları için)."""
    blob = (title + " | " + desc).strip()
    low = _ascii_lower(blob)

    # "Ücretsiz" / "bedava"
    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    # "X+Y taksit" (örn. "2+8 taksit", "9 taksit", "12 ay taksit")
    m = re.search(r"(\d+)\s*\+\s*(\d+)\s*taksit", low)
    if m:
        return f"{m.group(1)}+{m.group(2)} taksit"
    m = re.search(r"\b(\d{1,2})\s*(?:aya\s+varan\s+)?taksit\b", low)
    if m:
        return f"{m.group(1)} taksit"

    # "X TL chargeback"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl[^a-z]{0,10}chargeback", low)
    if m:
        return f"{m.group(1)} TL chargeback"

    # "X TL chip-para" / "X chip-para" (kelimeler arasında 25 kar. tolerans)
    m = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*tl(?:[^a-z]{0,30}varan)?[^a-z]{0,15}chip[-\s]?para", low)
    if m:
        return f"{m.group(1)} TL chip-para"
    m = re.search(r"chip[-\s]?para[^a-z0-9]{0,15}(\d{1,4}(?:\.\d{3})*)\s*tl", low)
    if m:
        return f"{m.group(1)} TL chip-para"
    m = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*tl'?ye\s+varan", low)
    if m:
        return f"{m.group(1)} TL'ye varan"

    # "%X iade" / "%X indirim"
    m = re.search(r"%\s*(\d{1,3})\s*(iade|indirim)?", low)
    if m:
        kind = m.group(2) or "indirim"
        return f"%{m.group(1)} {kind}"

    # "X TL indirim"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl[^a-z]{0,8}indirim", low)
    if m:
        return f"{m.group(1)} TL indirim"

    # "X TL'ye varan chip-para/indirim"
    m = re.search(
        r"(\d{1,3}(?:\.\d{3})*)\s*tl[^a-z]{0,8}(?:varan|kadar)",
        low,
    )
    if m:
        return f"{m.group(1)} TL'ye varan"

    return "Kampanya"


def _abs_image(src: str) -> str:
    src = src.strip()
    if not src:
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return BASE + src
    return src


def _parse_carousel(html: str) -> list[dict]:
    """Ana sayfanın carousel'inden 6 öne çıkan kampanyayı al."""
    out: list[dict] = []
    seen: set[str] = set()
    for href, img, _alt in _CAROUSEL_RE.findall(html):
        if href in seen:
            continue
        seen.add(href)
        slug = href
        link = BASE + href
        title = _slugify_title(slug)
        if not title or len(title) < 3:
            continue
        out.append({
            "_slug": slug,
            "title": title,
            "desc": "",
            "image": _abs_image(img),
            "link": link,
        })
    return out


def _parse_ajax(html: str) -> list[dict]:
    """Ajax endpoint'inden gelen 9 kartı al."""
    out: list[dict] = []
    seen: set[str] = set()
    for card_html in _AJAX_CARD_RE.findall(html):
        link_m = _AJAX_LINK_RE.search(card_html)
        if not link_m:
            continue
        href = link_m.group(1)
        if href in seen:
            continue
        seen.add(href)
        link = BASE + href

        img_m = _AJAX_IMG_RE.search(card_html)
        image = _abs_image(img_m.group(1)) if img_m else ""

        desc_m = _AJAX_DESC_RE.search(card_html)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""

        title = _slugify_title(href)
        if not title or len(title) < 3:
            continue
        out.append({
            "_slug": href,
            "title": title,
            "desc": desc,
            "image": image,
            "link": link,
        })
    return out


async def scrape_axess_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Axess kampanyalarını çeker.

    max_pages parametresi şu an aktif değil — Axess sayfalandırma sunmuyor
    (ajax'ta filtre ASP.NET VIEWSTATE gerektiriyor). Her zaman tek geçişle
    carousel + ajax kombinasyonu döner (~12-15 unique kampanya).
    """
    list_url = category_url
    if not list_url:
        for cand in CANDIDATE_LIST_URLS:
            list_url = cand
            break

    print(f"[Axess] Başlıyor: list={list_url} ajax={AJAX_URL}", flush=True)

    loop = asyncio.get_running_loop()

    # 1) Ana liste sayfası (carousel için)
    list_html: str | None = None
    chosen_url: str | None = None
    urls_to_try = [category_url] if category_url else CANDIDATE_LIST_URLS
    for url in urls_to_try:
        if not url:
            continue
        h = await loop.run_in_executor(None, _fetch, url)
        if h and ("campaingBox" in h or "/axess/kampanyalar/" in h):
            list_html = h
            chosen_url = url
            print(f"[Axess] liste OK: {url}", flush=True)
            break

    # 2) Ajax endpoint (asıl liste). Bu endpoint SADECE Referer + XHR
    # header'ı ile dolu yanıt veriyor; aksi halde boş WebForms shell döner.
    ajax_headers = {
        "Referer": chosen_url or f"{BASE}/kampanyalar",
        "X-Requested-With": "XMLHttpRequest",
    }
    ajax_html = await loop.run_in_executor(
        None, lambda: _fetch(AJAX_URL, 25, ajax_headers)
    )
    if not ajax_html:
        print("[Axess] ajax HTML alınamadı", flush=True)

    if not list_html and not ajax_html:
        print("[Axess] Hiçbir kaynaktan veri alınamadı", flush=True)
        return

    raw_cards: list[dict] = []
    if list_html:
        c = _parse_carousel(list_html)
        print(f"[Axess] carousel: {len(c)} kart", flush=True)
        raw_cards.extend(c)
    if ajax_html:
        a = _parse_ajax(ajax_html)
        print(f"[Axess] ajax: {len(a)} kart", flush=True)
        raw_cards.extend(a)

    deals: list[dict] = []
    seen: set[str] = set()
    for c in raw_cards:
        link = c["link"]
        if link in seen:
            continue
        seen.add(link)
        title = c["title"]
        desc = c["desc"]
        slug = c["_slug"]
        price = _extract_price(title, desc)
        cat = _detect_category(title, desc, slug)
        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": c["image"],
            "source": "axess",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })

    print(f"[Axess] {len(raw_cards)} ham, {len(deals)} unique kampanya", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[Axess] Kaydediliyor: {len(merged)} kampanya (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)
