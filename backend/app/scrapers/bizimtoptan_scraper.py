import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US','en']});
window.chrome = {runtime: {}};
"""


BIZIMTOPTAN_CATEGORY_URLS: dict[str, str] = {
    "temel-gida": "https://www.bizimtoptan.com.tr/temel-gida",
    "icecek": "https://www.bizimtoptan.com.tr/icecek",
    "sivi-yag-margarin": "https://www.bizimtoptan.com.tr/sivi-yag-margarin",
    "temizlik": "https://www.bizimtoptan.com.tr/temizlik",
    "atistirmalik": "https://www.bizimtoptan.com.tr/atistirmalik",
    "sarkuteri-kahvaltilik": "https://www.bizimtoptan.com.tr/sarkuteri-kahvaltilik",
    "et-urunleri-ve-sarkuteri": "https://www.bizimtoptan.com.tr/et-urunleri-ve-sarkuteri",
    "kisisel-bakim": "https://www.bizimtoptan.com.tr/kisisel-bakim",
    "bebek-urunleri": "https://www.bizimtoptan.com.tr/bebek-urunleri",
}


async def scrape_bizimtoptan_deals(
    output_file: str,
    category: str = "temel-gida",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    seen_links: set[str] = set()
    url = category_url or BIZIMTOPTAN_CATEGORY_URLS.get(
        category, f"https://www.bizimtoptan.com.tr/{category}"
    )
    print(f"[BizimToptan] Başlıyor: {url}", flush=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9"},
            )
            await context.add_init_script(STEALTH)
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(3.5, 4.5))

            # Scroll to force lazy images + load full category grid
            for _ in range(10):
                await page.mouse.wheel(0, random.randint(1500, 2000))
                await page.wait_for_timeout(random.randint(600, 900))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';

              const seen = new Set();
              const out = [];
              const cards = Array.from(document.querySelectorAll('.product-box-container'));
              for (const card of cards) {
                // product link: the FIRST <a> that goes to /<slug> (not javascript:;)
                const anchors = Array.from(card.querySelectorAll('a[href]'));
                let href = '';
                for (const a of anchors) {
                  const raw = a.getAttribute('href') || '';
                  if (!raw || raw.startsWith('javascript')) continue;
                  if (!raw.startsWith('/')) continue;
                  if (raw === '/' || raw.startsWith('/search') || raw.startsWith('/customer')) continue;
                  // skip category-style hrefs (no product slug words)
                  href = a.href;
                  break;
                }
                if (!href) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                // Title: prefer .productbox-name, fallback to img alt
                const titleEl = card.querySelector('.productbox-name');
                const img = card.querySelector('img.product-box-zoom-image, img');
                let title = titleEl ? (titleEl.textContent || '').trim() : '';
                if (!title && img) title = (img.getAttribute('alt') || '').trim();
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 3) continue;

                // Price (main): .product-price (e.g. "489,00 TL")
                const priceEl = card.querySelector('.product-price');
                let current = null;
                if (priceEl) current = turkishToFloat(priceEl.textContent || '');
                if (!current || current < 1) continue;

                // Optional tier/bulk price: ".percent-value-tierpriceofpiece" — e.g. "8 Adet üzeri 485 TL"
                // and / or ".unit-price" inside "Koliyle Alımda 277,00 TL / Adet"
                // CAREFUL: turkishToFloat would grab the leading "8" (quantity), so extract price near "TL".
                const extractPriceNearTL = (text) => {
                  if (!text) return null;
                  // Pattern: number then "TL" (with optional decimals)
                  const m = text.match(/(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?|\\d+(?:,\\d{2})?)\\s*TL/i);
                  return m ? turkishToFloat(m[1]) : null;
                };
                let bulk = null;
                const tierEl = card.querySelector('.percent-value-tierpriceofpiece');
                if (tierEl) {
                  const v = extractPriceNearTL(tierEl.textContent || '');
                  if (v && v > 0 && v < current) bulk = v;
                }
                const unitEl = card.querySelector('.unit-price');
                if (unitEl) {
                  const v = extractPriceNearTL(unitEl.textContent || '');
                  if (v && v > 0 && v < current && (!bulk || v < bulk)) bulk = v;
                }
                // Sanity: discount must be reasonable (<=50% is realistic wholesale bulk savings)
                if (bulk && current > 0) {
                  const pct = ((current - bulk) / current) * 100;
                  if (pct > 50) bulk = null;  // probably parsed wrong
                }

                let discount = 0;
                if (bulk && current > bulk) {
                  discount = Math.round(((current - bulk) / current) * 100);
                }

                // Image: img src or data-src (lazy)
                let image = '';
                if (img) {
                  image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                }
                if (image && image.startsWith('//')) image = 'https:' + image;
                // Filter: ignore tiny badge-like imgs by parent class (defensive — current site has none)
                if (img) {
                  const parentCls = img.parentElement ? (typeof img.parentElement.className === 'string' ? img.parentElement.className : '') : '';
                  if (/badge|coupon|label|promo|sticker|rosette/i.test(parentCls)) {
                    image = '';
                  }
                  const imgCls = (typeof img.className === 'string' ? img.className : '');
                  if (/badge|coupon|label|promo|sticker/i.test(imgCls)) {
                    image = '';
                  }
                }

                // bulk price as "original" for display purposes (the standalone/unit price)
                const originalForDisplay = bulk ? formatTL(current) : null;
                const priceForDisplay = bulk ? formatTL(bulk) : formatTL(current);

                out.push({
                  title: title.substring(0, 150),
                  // when there is a bulk discount: show bulk as "price" and standalone as "original"
                  // when none: just show single price
                  price: priceForDisplay,
                  original: originalForDisplay,
                  discount,
                  link: href,
                  image,
                });
              }
              return out;
            }""")

            raw_count = len(products_data)
            kept = 0
            for prod in products_data:
                link = prod.get("link") or ""
                if not link.startswith("http"):
                    continue
                if link in seen_links:
                    continue
                seen_links.add(link)
                discount = prod.get("discount", 0) or 0
                if discount < min_discount:
                    continue
                deals.append({
                    "title": (prod.get("title") or "")[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "bizimtoptan",
                    "category": category,
                    "last_updated": datetime.now().isoformat(),
                })
                kept += 1

            print(
                f"[BizimToptan] {category}: {raw_count} ham, {kept} kept (min_discount={min_discount})",
                flush=True,
            )
            await browser.close()

    except Exception as e:
        print(f"[BizimToptan] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[BizimToptan] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)
