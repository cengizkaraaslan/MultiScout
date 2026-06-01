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

DR_CATEGORY_URLS = {
    "kitap":             "https://www.dr.com.tr/kategori/kitap",
    "egitim-kitaplari":  "https://www.dr.com.tr/kategori/egitim-kitaplari",
    "cocuk-kitaplari":   "https://www.dr.com.tr/kategori/cocuk-kitaplari",
    "yabanci-dilde":     "https://www.dr.com.tr/kategori/yabanci-dilde-kitaplar",
    "elektronik":        "https://www.dr.com.tr/kategori/elektronik",
    "hobi-oyuncak":      "https://www.dr.com.tr/kategori/hobi-oyuncak",
    "kirtasiye":         "https://www.dr.com.tr/kategori/ofis-kirtasiye",
    "muzik-film":        "https://www.dr.com.tr/kategori/muzik-film",
    "hediyelik":         "https://www.dr.com.tr/kategori/hediyelik",
}


async def scrape_dr_deals(
    output_file: str,
    category: str = "kitap",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or DR_CATEGORY_URLS.get(category) or f"https://www.dr.com.tr/kategori/{category}"
    print(f"[DR] Başlıyor: {url}", flush=True)

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
                // Strip TL/₺ and whitespace
                let raw = s.replace(/\\s*(TL|₺)\\s*/gi, '').trim();
                // Match Turkish number formats:
                //   1.299,99   (dot thousand sep, comma decimal)
                //   1.299      (dot thousand sep, no decimal)
                //   215,00     (comma decimal)
                //   215        (plain)
                const m = raw.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d+(?:,\\d{2})?|\\d+/);
                if (!m) return null;
                let num = m[0];
                if (num.includes(',')) {
                  num = num.replace(/\\./g, '').replace(',', '.');
                }
                // No comma but has dot → could be thousands sep ("1.299" = 1299)
                else if (num.includes('.')) {
                  // If looks like thousands grouping (e.g. "1.299" or "12.345"), strip dots
                  // Heuristic: if dot is followed by exactly 3 digits at end of token, treat as thousands
                  if (/^\\d{1,3}(?:\\.\\d{3})+$/.test(num)) {
                    num = num.replace(/\\./g, '');
                  }
                }
                const f = parseFloat(num);
                return isNaN(f) ? null : f;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              const cards = Array.from(document.querySelectorAll('.product-card'));
              for (const card of cards) {
                let a = card.querySelector('a[href*="urunno="]')
                     || card.querySelector('a[href*="/kitap/"]')
                     || card.querySelector('a[href]');
                if (!a) continue;
                let href = a.href || a.getAttribute('href') || '';
                if (!href) continue;
                if (href.startsWith('/')) href = 'https://www.dr.com.tr' + href;
                if (!/dr\\.com\\.tr/.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                // Title from img alt (most reliable per probe)
                const img = card.querySelector('img');
                let title = (img && img.getAttribute('alt') || '').trim();
                if (title.length < 3) {
                  const t = card.querySelector('h3, h2, [class*="product-name"], [class*="name"], [class*="title"]');
                  if (t) title = (t.innerText || '').trim();
                }
                // Clean "Yeni " / "Yeni 445 kişi favoriledi!" prefixes
                title = title
                  .replace(/^Yeni\\s+\\d+\\s+kişi\\s+favoriledi!?\\s*/i, '')
                  .replace(/^Yeni\\s+/i, '')
                  .replace(/\\s+/g, ' ')
                  .trim();
                if (title.length < 3) continue;

                const cardText = card.innerText || '';
                // ONLY take values explicitly suffixed with TL or ₺ to avoid dates like "03.06.2026"
                const tlMatches = cardText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);
                if (prices.length === 0) continue;

                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                // Badge fallback like "%20"
                const badge = cardText.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = (img && (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original'))) || '';
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
                    "source": "dr",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[DR] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[DR] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[DR] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
