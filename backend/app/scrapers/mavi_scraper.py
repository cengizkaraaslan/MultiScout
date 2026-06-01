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


async def scrape_mavi_deals(
    output_file: str,
    category: str = "kadin",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    if category_url:
        url = category_url
    else:
        url = f"https://www.mavi.com/arama?q={quote_plus(category)}"
    print(f"[Mavi] Başlıyor: {url}", flush=True)

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
                let raw = m[0];
                // Mavi uses Turkish format "1.234,56" (dot=thousands, comma=decimal)
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if ((raw.match(/\\./g) || []).length === 1 && /\\.\\d{3}$/.test(raw)) {
                  // "1.234" style (thousands only, no decimals) -> strip dot
                  raw = raw.replace(/\\./g, '');
                }
                return parseFloat(raw);
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];

              // Mavi: product URL pattern /{slug}/p/{N}. Anchorları al, parent chain'de TL fiyat bul.
              let anchors = Array.from(document.querySelectorAll('a[href*="/p/"]'));
              if (anchors.length === 0) {
                anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              }
              const cards = [];
              const seenHrefs = new Set();
              anchors.forEach((a) => {
                const href = a.getAttribute('href') || '';
                if (!href || seenHrefs.has(href)) return;
                seenHrefs.add(href);
                // Walk up until current node text contains TL/₺
                let card = a;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const t = (card.innerText || '');
                  if (/TL|₺/.test(t)) break;
                }
                if (!card) return;
                cards.push({card, anchor: a});
              });

              cards.forEach(({card, anchor}) => {
                let href = anchor.getAttribute('href') || '';
                if (!href || href === '#') return;
                if (href.startsWith('/')) href = 'https://www.mavi.com' + href;
                if (!href.startsWith('http')) return;
                if (seen.has(href)) return;
                seen.add(href);

                // Title: try multiple selectors
                let title = '';
                const titleEl = card.querySelector('h3, h2, [class*="name"], [class*="Name"], [class*="title"], [class*="Title"]');
                if (titleEl) title = titleEl.innerText || titleEl.textContent || '';
                if (!title || title.trim().length < 5) {
                  const img = card.querySelector('img[alt]');
                  if (img) title = img.getAttribute('alt') || '';
                }
                if (!title || title.trim().length < 5) {
                  title = anchor.getAttribute('title') || anchor.innerText || '';
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;

                // Price: gather all price-like text in card
                const priceEls = card.querySelectorAll('[class*="price"], [class*="Price"]');
                let priceTxt = '';
                priceEls.forEach((el) => { priceTxt += ' ' + (el.innerText || el.textContent || ''); });
                if (!priceTxt.trim()) {
                  priceTxt = card.innerText || '';
                }

                // Match TL or ₺ amounts
                const tlMatches = priceTxt.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                let prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);

                if (prices.length === 0) {
                  // Fallback: numbers near ₺/TL without spaces
                  const fb = priceTxt.match(/(?:TL|₺)\\s*\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?/g) || [];
                  prices = fb.map(turkishToFloat).filter((n) => n && n > 0);
                }
                if (prices.length === 0) return;

                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }

                // Discount badge has priority: "%XX" or "-%XX"
                const cardTxt = card.innerText || '';
                const badge = cardTxt.match(/-?\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90) discount = b;
                }

                const img = card.querySelector('img');
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
                    "source": "mavi",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Mavi] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Mavi] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Mavi] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


MAVI_CATEGORY_URLS = {
    # Mavi'nin ana kot kategorileri /c/N pattern'inde
    "erkek-kot-pantolon": "https://www.mavi.com/erkek/jean/c/2",
    "kadin-kot-pantolon": "https://www.mavi.com/kadin/jean/c/1",
    # Geri kalanlar search-based
    "erkek-tisort":  "https://www.mavi.com/search?text=erkek+ti%C5%9F%C3%B6rt",
    "erkek-gomlek":  "https://www.mavi.com/search?text=erkek+g%C3%B6mlek",
    "kadin-tisort":  "https://www.mavi.com/search?text=kad%C4%B1n+ti%C5%9F%C3%B6rt",
    "kadin-elbise":  "https://www.mavi.com/search?text=kad%C4%B1n+elbise",
    "erkek-sweat":   "https://www.mavi.com/search?text=erkek+sweatshirt",
    "erkek-mont":    "https://www.mavi.com/search?text=erkek+mont",
    "kadin-mont":    "https://www.mavi.com/search?text=kad%C4%B1n+mont",
}
