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

IDEFIX_CATEGORY_URLS = {
    "kitap":             "https://www.idefix.com/Search/?query=kitap",
    "cok-satan":         "https://www.idefix.com/Search/?query=%C3%A7ok+satan+kitap",
    "edebiyat":          "https://www.idefix.com/Search/?query=edebiyat",
    "cocuk-kitabi":      "https://www.idefix.com/Search/?query=%C3%A7ocuk+kitab%C4%B1",
    "yabanci-dil":       "https://www.idefix.com/Search/?query=yabanc%C4%B1+dilde+kitap",
    "muzik-cd":          "https://www.idefix.com/Search/?query=m%C3%BCzik+cd",
    "elektronik":        "https://www.idefix.com/Search/?query=elektronik",
    "oyuncak":           "https://www.idefix.com/Search/?query=oyuncak",
    "hediyelik":         "https://www.idefix.com/Search/?query=hediyelik",
}


async def scrape_idefix_deals(
    output_file: str,
    category: str = "kitap",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    if category_url:
        url = category_url
    elif category in IDEFIX_CATEGORY_URLS:
        url = IDEFIX_CATEGORY_URLS[category]
    else:
        url = f"https://www.idefix.com/Search/?query={quote_plus(category)}"
    print(f"[Idefix] Başlıyor: {url}", flush=True)

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
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:[.,]\\d{2})?/);
                if (!m) return null;
                let raw = m[0];
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                }
                return parseFloat(raw);
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';

              const anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              const seenHrefs = new Set();
              const out = [];

              for (const a of anchors) {
                const href = a.href;
                if (!href || !/idefix\\.com.*-p-\\d+/.test(href)) continue;
                if (seenHrefs.has(href)) continue;
                seenHrefs.add(href);

                // Walk up to find the card boundary
                let card = a;
                let found = false;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const t = (card.innerText || card.textContent || '');
                  if (/TL|₺/.test(t) && t.length < 1500) { found = true; break; }
                }
                if (!card) continue;

                // Title: try img.alt first, then various heading/title classes
                const img = card.querySelector('img');
                let title = (img && img.alt ? img.alt : '').trim();
                if (title.length < 3) {
                  const t = card.querySelector('h3, h2, [class*="name"], [class*="title"], [class*="product-title"]');
                  if (t) title = (t.innerText || t.textContent || '').trim();
                }
                if (!title || title.length < 3) {
                  title = (a.innerText || a.textContent || '').trim();
                }
                title = title.replace(/^Yeni\\s+/, '').replace(/\\s+/g, ' ').trim();
                if (title.length < 3) continue;

                // Prices
                const cardText = (card.innerText && card.innerText.length > 0) ? card.innerText : (card.textContent || '');
                const tlMatches = cardText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((p) => p && p > 0);
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

                let image = '';
                if (img) {
                  image = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original') || '';
                }
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
                    "source": "idefix",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Idefix] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Idefix] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Idefix] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
