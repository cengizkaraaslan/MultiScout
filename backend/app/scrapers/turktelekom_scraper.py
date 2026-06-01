"""Türk Telekom kampanya scraper — turktelekom.com.tr/kampanyalar

İki ana liste sayfası:
  1) bireysel.turktelekom.com.tr/mobil/kampanyalar         → mobil kart yapısı
     <div class="mega-menu-img type2 ct__mobilkampanya">
        <a href="/mobil/kampanyalar/SLUG" class="img">
          <img src="..." alt="..." />
        </a>
        <div class="caption">
          <h4>Başlık</h4>
          <p class="small">Kısa açıklama</p>
        </div>
     </div>

  2) bireysel.turktelekom.com.tr/evde-internet/yeni-musteri-kampanyalari → evde-internet
     <div class="card v2 [x3] bg-(evde-internet|prime)">
        <h4>Başlık</h4>
        <div class="card-recipe single">… <strong>50 Mbps</strong> Fiber İnternet …</div>
        <div class="prices">
          <span class="sup-group"><strong>480</strong><sup>TL</sup></span>
        </div>
        <a href="/evde-internet/yeni-musteri-kampanyalari/SLUG">
     </div>

Statik HTML — Playwright yok. urllib redirect'leri otomatik takip eder.
"""
import asyncio
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://bireysel.turktelekom.com.tr"
START_URL = "https://www.turktelekom.com.tr/kampanyalar"  # 301 → /mobil/kampanyalar
EVDE_URL = f"{BASE}/evde-internet/yeni-musteri-kampanyalari"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
}
_SSL_CTX = ssl.create_default_context()

# ---- Mobil kart parser
# Bir mobil kampanya kartı; bir sonraki karta veya footer'a kadar al.
_MOBIL_CARD_RE = re.compile(
    r'<div class="mega-menu-img type2 ct__mobilkampanya"(.*?)(?=<div class="mega-menu-img type2 ct__mobilkampanya"|<footer|</main)',
    re.DOTALL,
)
_MOBIL_LINK_RE = re.compile(
    r'<a\s+href="(/mobil/kampanyalar/[^"]+)"\s+class="img"',
    re.DOTALL,
)
_MOBIL_IMG_RE = re.compile(r'<img\s+src="([^"]+)"', re.DOTALL)
_MOBIL_H4_RE = re.compile(r"<h4>(.*?)</h4>", re.DOTALL)
_MOBIL_DESC_RE = re.compile(r'<p\s+class="small">(.*?)</p>', re.DOTALL)

# ---- Evde-internet kart parser
_EVDE_CARD_RE = re.compile(
    r'<div class="card v2(?: x3)? bg-(?:evde-internet|prime)"(.*?)(?=<div class="card v2(?: x3)? bg-(?:evde-internet|prime)"|<footer|</main)',
    re.DOTALL,
)
_EVDE_H4_RE = re.compile(r"<h4>(.*?)</h4>", re.DOTALL)
_EVDE_SPEED_RE = re.compile(r"<strong>\s*(\d+)\s*Mbps\s*</strong>", re.IGNORECASE)
_EVDE_PRICE_RE = re.compile(
    r'<span class="sup-group">\s*<strong>\s*([\d.,]+)\s*</strong>\s*<sup>\s*TL\s*</sup>',
    re.DOTALL,
)
_EVDE_LINK_RE = re.compile(
    r'<a\s+href="(/evde-internet/[^"]+)"\s+aria-label="Ilerle"',
    re.DOTALL,
)


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[TurkTelekom] fetch error {url}: {e}", flush=True)
        return None


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BASE + href
    return f"{BASE}/{href}"


def _detect_mobil_category(title: str, desc: str) -> str:
    """Title + desc'den kampanya tipi tahmin et."""
    t = (title + " " + desc).lower()
    # Türkçe locale tuzağı: lower yerine küçük harfli regex'e basit dönüşüm yeterli
    if "ücretsiz" in t or "ucretsiz" in t or "bedava" in t:
        return "ucretsiz-internet"
    if "gb" in t and ("hediye" in t or "kazan" in t or "bonus" in t):
        return "gb-hediye"
    if "faturasız" in t or "faturasiz" in t:
        return "faturasiz"
    if "prime" in t:
        return "prime"
    if "youtube" in t or "muud" in t or "tivibu" in t or "dergi" in t:
        return "ek-servis"
    return "kampanya"


def _extract_mobil_price(title: str, desc: str) -> str:
    """Mobil kart için fiyat/teklif satırı."""
    blob = f"{title} {desc}"
    # "20 GB", "10GB", "5 GB" → "X GB hediye"
    m = re.search(r"(\d+)\s*GB", blob, re.IGNORECASE)
    if m:
        return f"{m.group(1)} GB hediye"
    # "X TL"
    m = re.search(r"(\d{1,4}(?:[.,]\d{3})*)\s*TL", blob)
    if m:
        return f"{m.group(1)} TL"
    low = blob.lower()
    if "ücretsiz" in low or "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"
    return "Kampanya"


def _parse_mobil(html: str, deals: list[dict]) -> int:
    """Mobil kampanya kartlarını parse et, deals'e ekle. Eklenen sayısını döner."""
    added = 0
    seen: set[str] = {d["link"] for d in deals}
    for card in _MOBIL_CARD_RE.findall(html):
        link_m = _MOBIL_LINK_RE.search(card)
        if not link_m:
            continue
        link = _abs_url(link_m.group(1).strip())
        if link in seen:
            continue
        seen.add(link)

        h4_m = _MOBIL_H4_RE.search(card)
        if not h4_m:
            continue
        title = _clean_text(h4_m.group(1))
        if len(title) < 3:
            continue
        title = title[:180]

        desc_m = _MOBIL_DESC_RE.search(card)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""

        img_m = _MOBIL_IMG_RE.search(card)
        image = _abs_url(img_m.group(1).strip()) if img_m else ""

        price = _extract_mobil_price(title, desc)
        cat = _detect_mobil_category(title, desc)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "turktelekom",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })
        added += 1
    return added


def _parse_evde(html: str, deals: list[dict]) -> int:
    """Evde-internet kartları (fiber)."""
    added = 0
    seen: set[str] = {d["link"] for d in deals}
    for card in _EVDE_CARD_RE.findall(html):
        h4_m = _EVDE_H4_RE.search(card)
        if not h4_m:
            continue
        title = _clean_text(h4_m.group(1))
        if len(title) < 3:
            continue

        # Hız etiketini başlığa ekle (aynı isimle farklı Mbps kartları var)
        speed_m = _EVDE_SPEED_RE.search(card)
        speed = speed_m.group(1) if speed_m else ""
        if speed and speed not in title:
            title = f"{title} - {speed} Mbps"
        title = title[:200]

        link_m = _EVDE_LINK_RE.search(card)
        if not link_m:
            continue
        link = _abs_url(link_m.group(1).strip())
        if link in seen:
            continue
        seen.add(link)

        price_m = _EVDE_PRICE_RE.search(card)
        if price_m:
            price = f"{price_m.group(1)} TL/ay"
        else:
            price = "Kampanya"

        cat = "fiber" if "fiber" in card.lower() else "ev-interneti"

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": "",
            "source": "turktelekom",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })
        added += 1
    return added


async def scrape_turktelekom_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Türk Telekom mobil + evde-internet kampanyalarını çeker.

    max_pages >= 2 ise evde-internet sayfası da çekilir; aksi halde sadece mobil.
    """
    deals: list[dict] = []
    loop = asyncio.get_running_loop()

    # 1) Mobil kampanyalar (start URL 301 ile mobil sayfaya yönlenir)
    url = category_url or START_URL
    print(f"[TurkTelekom] Mobil sayfa: {url}", flush=True)
    html = await loop.run_in_executor(None, _fetch, url)
    if html:
        n = _parse_mobil(html, deals)
        print(f"[TurkTelekom] mobil: +{n}", flush=True)
    else:
        print("[TurkTelekom] mobil HTML alınamadı", flush=True)

    # 2) Evde-internet kampanyaları (opsiyonel ikinci sayfa)
    if max_pages >= 2 and not category_url:
        print(f"[TurkTelekom] Evde-internet sayfa: {EVDE_URL}", flush=True)
        html2 = await loop.run_in_executor(None, _fetch, EVDE_URL)
        if html2:
            n2 = _parse_evde(html2, deals)
            print(f"[TurkTelekom] evde: +{n2}", flush=True)
        else:
            print("[TurkTelekom] evde HTML alınamadı", flush=True)

    print(f"[TurkTelekom] Toplam {len(deals)} kampanya kaydedilecek", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[TurkTelekom] Birleştirme sonrası {len(merged)} kampanya (yeni: {len(deals)})",
            flush=True,
        )
        save_deals(output_file, merged)
