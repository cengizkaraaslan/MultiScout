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

YARGICI_CATEGORY_URLS = {
    "kadin":          "https://www.yargici.com.tr/kadin",
    "erkek":          "https://www.yargici.com.tr/erkek",
    "kadin-elbise":   "https://www.yargici.com.tr/arama?q=elbise",
    "kadin-pantolon": "https://www.yargici.com.tr/arama?q=pantolon",
    "kadin-bluz":     "https://www.yargici.com.tr/arama?q=bluz",
    "kadin-etek":     "https://www.yargici.com.tr/arama?q=etek",
    "kadin-mont":     "https://www.yargici.com.tr/arama?q=mont",
    "erkek-gomlek":   "https://www.yargici.com.tr/arama?q=g%C3%B6mlek",
    "erkek-pantolon": "https://www.yargici.com.tr/arama?q=erkek+pantolon",
    "aksesuar":       "https://www.yargici.com.tr/arama?q=aksesuar",
}


async def scrape_yargici_deals(
    output_file: str,
    category: str = "kadin",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or YARGICI_CATEGORY_URLS.get(category) or f"https://www.yargici.com.tr/{category}"
    print(f"[Yargici] Başlıyor: {url}", flush=True)

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

            for _ in range(6):
                await page.mouse.wheel(0, random.randint(1200, 1800))
                await page.wait_for_timeout(random.randint(600, 1000))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:[.,]\\d{3})+(?:[.,]\\d{2})?|\\d+(?:[.,]\\d{2})?/);
                if (!m) return null;
                let raw = m[0];
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if (/^\\d{1,3}(?:\\.\\d{3})+$/.test(raw)) {
                  raw = raw.replace(/\\./g, '');
                }
                const v = parseFloat(raw);
                return isNaN(v) ? null : v;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              const seen = new Set();
              const out = [];
              for (const a of anchors) {
                let href = a.href || '';
                if (!/yargici\\.com(?:\\.tr)?.*-p-\\d+/.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                // Walk up to find card boundary
                let card = a;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const t = (card.innerText || card.textContent || '');
                  if (/TL|₺/.test(t) && t.length < 1500) break;
                }
                if (!card) continue;

                // Title
                const img = card.querySelector('img');
                const imgAlt = (img?.alt || '').trim();
                let title = '';
                const t = card.querySelector('h3, h2, [class*="name"], [class*="title"]');
                if (t) title = (t.innerText || t.textContent || '').trim();
                if (title.length < 5) {
                  const aText = (a.innerText || a.textContent || '').trim();
                  title = aText.split(/\\d{1,3}(?:[.,]\\d{3})*[,.]\\d{2}\\s*TL/)[0].trim();
                }
                if (title.length < 5) title = imgAlt;
                title = title.replace(/^\\d+\\s+ve\\s+Üzeri.*İndirim\\s*/i, '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;
                // Skip promo-like titles
                if (/ve\\s+Üzeri.*İndirim/i.test(title)) continue;

                // Prices from card text
                const cardText = (card.innerText && card.innerText.length > 0) ? card.innerText : (card.textContent || '');
                const tlMatches = cardText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);
                if (prices.length === 0) continue;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = cardText.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = img?.getAttribute('src') || img?.getAttribute('data-src') || img?.getAttribute('data-original') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;

                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(current),
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
                    "title": prod.get("title", "")[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "yargici",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Yargici] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Yargici] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Yargici] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
