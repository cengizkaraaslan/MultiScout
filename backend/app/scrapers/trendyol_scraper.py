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


async def scrape_trendyol_deals(
    output_file: str,
    category: str = "elektronik",
    min_discount: int = 5,
    max_pages: int = 1
):
    deals: list[dict] = []
    url = f"https://www.trendyol.com/sr?q={category}&discount=1"
    print(f"[Trendyol] Başlıyor: {url}", flush=True)

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
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
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
            await asyncio.sleep(random.uniform(3, 6))

            blocked_keywords = ("dakika lütfen", "Bir dakika", "Robot", "Güvenlik")
            title = await page.title()
            if any(k in title for k in blocked_keywords):
                await asyncio.sleep(5)
                title = await page.title()
                if any(k in title for k in blocked_keywords):
                    print("[Trendyol] Bot challenge geçilemedi", flush=True)
                    await browser.close()
                    return

            for _ in range(4):
                await page.evaluate("window.scrollBy(0, 1500)")
                await page.wait_for_timeout(800)

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              const cards = document.querySelectorAll('a.seller-store-product-card[href*="-p-"], a[data-testid="seller-store-product-card"], a.p-card-chldrn-cntnr, a[href*="-p-"]');
              cards.forEach((linkEl) => {
                if (!linkEl || linkEl.tagName !== 'A') return;
                const href = linkEl.getAttribute('href') || '';
                if (!href.includes('-p-')) return;
                const absHref = href.startsWith('http') ? href : 'https://www.trendyol.com' + href;
                const cleanHref = absHref.split('?')[0];
                if (seen.has(cleanHref)) return;
                seen.add(cleanHref);
                const img = linkEl.querySelector('img');
                let title = '';
                const titleEl = linkEl.querySelector('.product-name, .prdct-desc-cntnr-name, .prdct-desc-cntnr-ttl, [data-testid="seller-store-product-card-name"], [class*="ProductDesc"], h3, [class*="ttl"]');
                if (titleEl) title = titleEl.innerText.trim();
                if (!title || title.length < 5) title = img?.getAttribute('alt') || linkEl.getAttribute('title') || linkEl.getAttribute('aria-label') || '';
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;
                const txt = linkEl.innerText || '';
                const tlMatches = txt.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?\\s*TL|\\d+,\\d{2}\\s*TL/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter(v => v && v >= 3);
                if (prices.length === 0) return;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) discount = Math.round(((original - current) / original) * 100);
                const badge = txt.match(/-\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }
                if (discount > 90) return;
                let image = img?.getAttribute('src') || img?.getAttribute('data-src') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;
                out.push({title: title.substring(0,150), price: formatTL(current), discount, link: cleanHref, image});
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
                    "source": "trendyol",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Trendyol] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Trendyol] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Trendyol] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


async def scrape_trendyol_prices(search_query: str):
    prices = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            url = f"https://www.trendyol.com/sr?q={search_query}"
            await page.goto(url, timeout=60000, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            products_data = await page.evaluate("""() => {
                const items = document.querySelectorAll('.p-card-wrppr');
                if (items.length > 0) {
                    const titleEl = items[0].querySelector('.prdct-desc-cntnr-name, .prdct-desc-cntnr-ttl');
                    const priceEl = items[0].querySelector('.prc-box-dscntd, [class*="price"]');
                    return {
                        title: titleEl ? titleEl.innerText : '',
                        price: priceEl ? priceEl.innerText : 'N/A'
                    };
                }
                return null;
            }""")

            if products_data and products_data['title']:
                prices.append({
                    "title": products_data['title'][:80],
                    "price": products_data['price'],
                    "source": "trendyol"
                })
            await browser.close()
    except Exception as e:
        print(f"[Trendyol] Fiyat hatası: {e}", flush=True)
    return prices


async def compare_prices(amazon_product):
    try:
        title = amazon_product.get("title", "")[:50]
        trendyol_prices = await scrape_trendyol_prices(title)
        return {"amazon": amazon_product, "trendyol": trendyol_prices}
    except Exception as e:
        print(f"[Trendyol] Karşılaştırma hatası: {e}", flush=True)
        return None
