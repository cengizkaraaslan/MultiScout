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


async def scrape_gratis_deals(
    output_file: str,
    category: str = "parfum",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or f"https://www.gratis.com/search?q={quote_plus(category)}"
    print(f"[Gratis] Başlıyor: {url}", flush=True)

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

            for _ in range(5):
                await page.mouse.wheel(0, random.randint(1200, 1700))
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
              const anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              for (const a of anchors) {
                const href = a.href || '';
                if (!href || seen.has(href)) continue;
                if (!/gratis\\.com\\//.test(href)) continue;
                if (!/-p-\\d+/.test(href)) continue;
                seen.add(href);

                // walk up to product card root
                let card = a;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const cls = typeof card.className === 'string' ? card.className : '';
                  if (/rounded-xl/.test(cls) && /flex-col/.test(cls)) break;
                }

                // title: prefer img.alt if descriptive, else first long line
                const img = card.querySelector('img');
                let title = '';
                const cardText = (card.innerText || '').trim();
                const lines = cardText.split('\\n').map(s => s.trim()).filter(Boolean);
                // skip lines that are pure numbers, ratings, TL amounts, or threshold text
                for (const line of lines) {
                  if (line.length < 5) continue;
                  if (/^\\(\\d+\\)$/.test(line)) continue;          // (23) rating count
                  if (/^\\d+(\\.\\d+)?(B|K)?\\+?$/.test(line)) continue;  // 3,3B+ sales
                  if (/TL/i.test(line)) continue;
                  if (/Alışverişe|Üzeri|Sepette|Hediye|Tür|^\\+\\d+$/i.test(line)) continue;
                  title = line;
                  break;
                }
                if (!title && img) {
                  const alt = img.getAttribute('alt') || '';
                  if (alt && alt.length > 5 && alt.toLowerCase() !== 'product') title = alt;
                }
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;

                // prices: extract all TL matches, EXCLUDE "250 TL ve Üzeri" threshold (no kuruş part)
                const tlMatches = cardText.match(/\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?\\s*TL/g) || [];
                // filter out threshold lines (e.g. "250 TL ve Üzeri Alışverişe")
                const realPrices = [];
                for (const m of tlMatches) {
                  // threshold appears next to "ve Üzeri" — find substring around it
                  const idx = cardText.indexOf(m);
                  const ctx = cardText.substring(Math.max(0, idx - 5), idx + m.length + 30);
                  if (/ve Üzeri|Alışverişe|Sepette/i.test(ctx)) {
                    // also if the price has NO kuruş ("250 TL" not "250,00 TL") it's almost certainly a threshold
                    if (!/,\\d{2}/.test(m)) continue;
                  }
                  const v = turkishToFloat(m);
                  if (v && v >= 5) realPrices.push(v);
                }
                if (realPrices.length === 0) continue;
                const current = Math.min(...realPrices);
                const original = realPrices.length > 1 ? Math.max(...realPrices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                // badge override
                const badge = cardText.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = img?.getAttribute('src') || img?.getAttribute('data-src') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;

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
                    "source": "gratis",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Gratis] {category}: {raw_count} ham, {kept} kept (min_discount={min_discount})", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Gratis] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Gratis] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
