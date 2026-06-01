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


async def scrape_mediamarkt_deals(
    output_file: str,
    category: str = "elektronik",
    min_discount: int = 5,
    max_pages: int = 1
):
    deals: list[dict] = []
    url = f"https://www.mediamarkt.com.tr/tr/search.html?query={quote_plus(category)}"
    print(f"[MediaMarkt] Başlıyor: {url}", flush=True)

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
                await page.mouse.wheel(0, random.randint(1000, 1500))
                await page.wait_for_timeout(random.randint(600, 1000))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              let items = document.querySelectorAll('article[data-test="mms-product-card"]');
              if (items.length < 3) items = document.querySelectorAll('article[class*="product-card"], [class*="ProductCard"], [data-test*="product-card"]');
              items.forEach((item) => {
                const linkEl = item.querySelector('a[data-test="mms-router-link-product-list-item-link"]')
                  || item.querySelector('a[href*="/product/"]');
                if (!linkEl || !linkEl.href) return;
                if (seen.has(linkEl.href)) return;
                seen.add(linkEl.href);

                let title = item.querySelector('[data-test="product-title"]')?.innerText || '';
                if (!title || title.length < 5) {
                  title = linkEl.getAttribute('title') || linkEl.getAttribute('aria-label') || '';
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;

                const cardTxt = item.innerText || '';
                // Match prices like 6.999,00 or 25999,00; also pick currency-prefixed
                const tlMatches = cardTxt.match(/\\d{1,3}(?:\\.\\d{3})+,\\d{2}|\\d+,\\d{2}/g) || [];
                // Filter out tiny values (taksit installment amounts often appear) by keeping the
                // largest few. We'll use min as current, max as original if both present.
                const prices = tlMatches.map(turkishToFloat).filter(v => v && v >= 5);
                // Exclude obvious installment values: any value < max/3 is likely a taksit installment
                let usable = prices;
                if (prices.length >= 2) {
                  const maxP = Math.max(...prices);
                  usable = prices.filter(v => v >= maxP / 2.5);
                }
                if (usable.length === 0) return;
                const current = Math.min(...usable);
                const original = usable.length > 1 ? Math.max(...usable) : null;
                let discount = 0;
                if (original && original > current) discount = Math.round(((original - current) / original) * 100);

                // discount badge
                const pctMatch = cardTxt.match(/-?\\s*%\\s*(\\d{1,2})|%\\s*-?(\\d{1,2})/);
                if (pctMatch) {
                  const b = parseInt(pctMatch[1] || pctMatch[2]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }
                // strikethrough originals
                const strike = item.querySelector('s, del, [class*="strike"], [data-test*="old-price"], [class*="oldPrice"]');
                if (strike) {
                  const sTxt = strike.innerText || '';
                  const sVal = turkishToFloat(sTxt);
                  if (sVal && sVal > current) {
                    const d = Math.round(((sVal - current) / sVal) * 100);
                    if (d > discount) discount = d;
                  }
                }

                let image = item.querySelector('img')?.getAttribute('src') || item.querySelector('img')?.getAttribute('data-src') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;

                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(current),
                  discount,
                  link: linkEl.href,
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
                    "source": "mediamarkt",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[MediaMarkt] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[MediaMarkt] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[MediaMarkt] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
