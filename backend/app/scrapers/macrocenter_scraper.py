import asyncio
import random
from datetime import datetime
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US','en']});
window.chrome = {runtime: {}};
"""


async def scrape_macrocenter_deals(
    output_file: str,
    category: str = "atistirmalik",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    # Macrocenter uses /{slug}-c-{code} pattern; fallback to search if no category_url
    url = category_url or f"https://www.macrocenter.com.tr/arama?q={quote_plus(category)}"
    print(f"[Macrocenter] Başlıyor: {url}", flush=True)

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
            await asyncio.sleep(random.uniform(3.0, 4.5))

            # Lazy-load: scroll generously to load all cards
            for _ in range(10):
                await page.mouse.wheel(0, random.randint(1500, 2000))
                await page.wait_for_timeout(random.randint(700, 1100))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              const cards = Array.from(document.querySelectorAll('fe-product-card'));
              for (const card of cards) {
                const a = card.querySelector('a[href*="-p-"]');
                if (!a) continue;
                const href = a.href || '';
                if (!href || seen.has(href)) continue;
                if (!/macrocenter\\.com\\.tr\\//.test(href)) continue;
                if (!/-p-[a-z0-9]+/i.test(href)) continue;
                seen.add(href);

                // image: pick the img directly inside the product-link anchor; that one has alt = product title
                let titleImg = a.querySelector('img.product-image, img');
                // fallback: any product image inside card
                if (!titleImg) titleImg = card.querySelector('img.product-image');
                // Skip image candidates whose alt/parent class is a badge/coupon/promo
                const isBadgeImg = (img) => {
                  if (!img) return false;
                  const parent = img.parentElement;
                  const pcls = (parent && typeof parent.className === 'string') ? parent.className.toLowerCase() : '';
                  const icls = (typeof img.className === 'string') ? img.className.toLowerCase() : '';
                  const alt = (img.getAttribute('alt') || '').toLowerCase();
                  if (/badge|coupon|label|promo|kampanya|indirim|sticker/.test(pcls + ' ' + icls + ' ' + alt)) return true;
                  return false;
                };
                if (isBadgeImg(titleImg)) titleImg = null;

                let title = '';
                if (titleImg) {
                  const alt = titleImg.getAttribute('alt') || '';
                  if (alt && alt.length >= 3 && !/logo|placeholder|not-found/i.test(alt)) title = alt;
                }
                // fallback: derive from URL slug
                if (!title || title.length < 3) {
                  const m = href.match(/macrocenter\\.com\\.tr\\/([a-z0-9-]+)-p-/i);
                  if (m) title = m[1].replace(/-/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
                }
                if (!title || title.length < 3) continue;

                // image src
                let image = '';
                if (titleImg) {
                  image = titleImg.getAttribute('src') || titleImg.getAttribute('data-src') || '';
                }
                if (image && image.startsWith('//')) image = 'https:' + image;
                // Skip badge/coupon-looking image URLs
                if (image && /badge|coupon|sticker|promo[-_]?label/i.test(image)) image = '';

                // Pricing logic on Macrocenter:
                // - Regular price card: <fe-product-price class="price-no-discount">123,45 TL</fe-product-price>
                // - Money/loyalty discount: <fe-product-price class="price-old">321,00 TL</fe-product-price>
                //   + <div class="money-discount">Money ile 149,00 TL</div>
                // Look for both states.
                const priceEl = card.querySelector('fe-product-price');
                const moneyEl = card.querySelector('.money-discount, [class*="money-discount"]');
                const oldEl = card.querySelector('.price-old, [class*="price-old"], s, del');

                const priceText = priceEl ? (priceEl.innerText || '').trim() : '';
                const moneyText = moneyEl ? (moneyEl.innerText || '').trim() : '';
                const oldText = oldEl ? (oldEl.innerText || '').trim() : '';

                let current = null;
                let original = null;
                if (moneyText) {
                  // money discount path: priceText becomes the old/standard price, moneyText is the discounted
                  const ms = moneyText.match(/\\d{1,3}(?:\\.\\d{3})*,\\d{2}/);
                  current = ms ? turkishToFloat(ms[0]) : null;
                  // try to extract original (non-money) price
                  // priceText usually contains the standard TL price too (e.g. "321,00 TL Money ile 149,00 TL ...")
                  // find first TL token in price card text that doesn't belong to the money line
                  const standardTexts = [];
                  // priceEl might be multiple — collect all top-level prices except the money block
                  const allPriceEls = card.querySelectorAll('fe-product-price, .price, [class*="price"]');
                  for (const el of allPriceEls) {
                    const t = (el.innerText || '').trim();
                    // skip texts inside money-discount block
                    if (el.closest && el.closest('.money-discount, [class*="money-discount"]')) continue;
                    if (/\\d,\\d{2}\\s*TL/.test(t)) standardTexts.push(t);
                  }
                  for (const t of standardTexts) {
                    const v = turkishToFloat(t);
                    if (v && (!original || v > original)) original = v;
                  }
                  if (current && original && original <= current) original = null;
                } else if (oldText && priceText) {
                  // standard old/new split
                  current = turkishToFloat(priceText);
                  original = turkishToFloat(oldText);
                } else if (priceText) {
                  current = turkishToFloat(priceText);
                }

                if (!current || current < 1) continue;

                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                  if (discount < 0 || discount > 95) discount = 0;
                }
                // Look for explicit discount badge — ONLY inside elements whose class signals discount/promo,
                // never from the product title (which may contain "%25" as part of the product name).
                const badgeSelectors = '.discount-badge, .badge-discount, [class*="discount-badge"], [class*="badge-discount"], [class*="percent"], [class*="indirim-orani"]';
                const badgeEl = card.querySelector(badgeSelectors);
                if (badgeEl) {
                  const bt = (badgeEl.innerText || '').trim();
                  const m = bt.match(/%\\s*(\\d{1,2})\\b/);
                  if (m) {
                    const b = parseInt(m[1], 10);
                    if (b >= 1 && b <= 90 && b > discount) discount = b;
                  }
                }

                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(current),
                  original: original ? formatTL(original) : null,
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
                discount = prod.get("discount", 0)
                if discount < min_discount:
                    continue
                deals.append({
                    "title": (prod.get("title") or "")[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "macrocenter",
                    "category": category,
                    "last_updated": datetime.now().isoformat(),
                })
                kept += 1

            print(f"[Macrocenter] {category}: {raw_count} ham, {kept} kept (min_discount={min_discount})", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Macrocenter] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Macrocenter] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
