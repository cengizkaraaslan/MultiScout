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


BOYNER_CATEGORY_URLS = {
    # Direkt kategori (tested OK)
    "kadin": "https://www.boyner.com.tr/kadin-c-2",
    "erkek": "https://www.boyner.com.tr/erkek-c-3",
    # Search-tabanli (Boyner search 200 OK + 27 TL match)
    "kadin-elbise":   "https://www.boyner.com.tr/search?q=kad%C4%B1n+elbise",
    "kadin-pantolon": "https://www.boyner.com.tr/search?q=kad%C4%B1n+pantolon",
    "kadin-ayakkabi": "https://www.boyner.com.tr/search?q=kad%C4%B1n+ayakkab%C4%B1",
    "kadin-canta":    "https://www.boyner.com.tr/search?q=kad%C4%B1n+%C3%A7anta",
    "erkek-tisort":   "https://www.boyner.com.tr/search?q=erkek+ti%C5%9F%C3%B6rt",
    "erkek-ayakkabi": "https://www.boyner.com.tr/search?q=erkek+ayakkab%C4%B1",
    "parfum":         "https://www.boyner.com.tr/search?q=parf%C3%BCm",
    "kozmetik":       "https://www.boyner.com.tr/search?q=kozmetik",
}


async def scrape_boyner_deals(
    output_file: str,
    category: str = "kadin",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []

    if category_url:
        url = category_url
    elif category in BOYNER_CATEGORY_URLS:
        url = BOYNER_CATEGORY_URLS[category]
    else:
        url = f"https://www.boyner.com.tr/search?q={quote_plus(category)}"

    print(f"[Boyner] Basliyor: {url}", flush=True)

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
            # Boyner SSR partial, JS hidration gerekli
            await asyncio.sleep(random.uniform(4.0, 5.5))

            for _ in range(5):
                await page.mouse.wheel(0, random.randint(1200, 1800))
                await page.wait_for_timeout(random.randint(700, 1100))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                // Turkish format: "1.234,56" or "1.299" or "999,99"
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d+,\\d{2}|\\d+/);
                if (!m) return null;
                let raw = m[0];
                if (raw.includes(',')) {
                  // has decimal: remove thousand dots, swap comma to dot
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if (/^\\d{1,3}(?:\\.\\d{3})+$/.test(raw)) {
                  // pure thousand-grouped integer: strip dots
                  raw = raw.replace(/\\./g, '');
                }
                const v = parseFloat(raw);
                return isFinite(v) ? v : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';

              const anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              const seenHrefs = new Set();
              const out = [];

              for (const a of anchors) {
                let href = a.getAttribute('href') || '';
                if (!href || href === '#') continue;
                if (href.startsWith('/')) href = 'https://www.boyner.com.tr' + href;
                // strict: Boyner product anchors
                if (!/boyner\\.com\\.tr\\/.+-p-\\d+/.test(href)) continue;
                if (seenHrefs.has(href)) continue;
                seenHrefs.add(href);

                // Card boundary: parent chain'de TL/₺ var ise dur
                let card = a;
                let found = false;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const txt = card.innerText || '';
                  if (/TL|₺/.test(txt)) {
                    found = true;
                    break;
                  }
                }
                if (!found || !card) continue;

                // Title: card icinde h3/h2/[class*="name"]/[class*="title"]/img.alt
                let title = '';
                const titleEl = card.querySelector('h3, h2, [class*="name"], [class*="title"], [class*="Name"], [class*="Title"]');
                if (titleEl) title = (titleEl.innerText || '').trim();
                if (!title || title.length < 5) {
                  const img = card.querySelector('img');
                  if (img) title = (img.getAttribute('alt') || '').trim();
                }
                if (!title || title.length < 5) {
                  title = (a.getAttribute('title') || a.getAttribute('aria-label') || '').trim();
                }
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;

                // Price: card.innerText'ten "999,99 TL" / "1.299 TL" matches
                const cardTxt = card.innerText || '';
                const tlMatches = cardTxt.match(/\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);
                if (prices.length === 0) continue;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                // Badge: "%XX" varsa override (band 1-90)
                const badge = cardTxt.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                // Image
                const img = card.querySelector('img');
                let image = '';
                if (img) {
                  image = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy') || '';
                  if (image && image.startsWith('//')) image = 'https:' + image;
                  if (image && image.startsWith('/')) image = 'https://www.boyner.com.tr' + image;
                }

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
                    "source": "boyner",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Boyner] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Boyner] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Boyner] Toplam {len(merged)} urun kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
