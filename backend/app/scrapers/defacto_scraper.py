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


async def scrape_defacto_deals(
    output_file: str,
    category: str = "kadin",
    min_discount: int = 5,
    max_pages: int = 1
):
    deals: list[dict] = []
    url = f"https://www.defacto.com.tr/arama?q={quote_plus(category)}"
    print(f"[Defacto] Başlıyor: {url}", flush=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
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
                extra_http_headers={
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )
            await context.add_init_script(STEALTH)
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2.5, 4.5))

            for _ in range(5):
                await page.mouse.wheel(0, random.randint(1200, 1800))
                await page.wait_for_timeout(random.randint(600, 1000))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:[.,]\\d{2})?/);
                if (!m) return null;
                // Defacto uses "1049.99" style (dot as decimal); also handles "1.299,99" if appears
                let raw = m[0];
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                }
                return parseFloat(raw);
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              let items = document.querySelectorAll('.catalog-products__item');
              if (items.length === 0) items = document.querySelectorAll('[class*="catalog-products__item"]');
              items.forEach((item) => {
                const linkEl = item.querySelector('.product-card__title--name') || item.querySelector('a[href]');
                if (!linkEl) return;
                let href = linkEl.getAttribute('href') || '';
                if (!href || href === '#') return;
                if (href.startsWith('/')) href = 'https://www.defacto.com.tr' + href;
                if (seen.has(href)) return;
                seen.add(href);

                let title = linkEl.getAttribute('title') || '';
                if (!title || title.length < 5) {
                  const titleEl = item.querySelector('.product-card__title--name span, .product-card__title, h2, h3');
                  if (titleEl) title = titleEl.innerText.trim();
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;

                const priceArea = item.querySelector('.product-catalog-price-area');
                if (!priceArea) return;
                const priceTxt = priceArea.innerText || '';
                const tlMatches = priceTxt.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*TL/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);
                if (prices.length === 0) return;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = priceTxt.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                const img = item.querySelector('img');
                let image = img?.getAttribute('src') || img?.getAttribute('data-src') || img?.getAttribute('data-original') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;

                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(current),
                  discount,
                  link: href,
                  image,
                });
              });
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
                    "title": prod.get("title", "")[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "defacto",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Defacto] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Defacto] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Defacto] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
