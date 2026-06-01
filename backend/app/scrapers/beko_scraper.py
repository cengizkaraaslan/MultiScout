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

BEKO_CATEGORY_URLS = {
    "buzdolabi":         "https://www.beko.com.tr/buzdolabi",
    "camasir-makinesi":  "https://www.beko.com.tr/camasir-makinesi",
    "bulasik-makinesi":  "https://www.beko.com.tr/bulasik-makinesi",
    "firin":             "https://www.beko.com.tr/firin",
    "ankastre":          "https://www.beko.com.tr/ankastre",
    "kucuk-ev-aletleri": "https://www.beko.com.tr/kucuk-ev-aletleri",
    "kahve-makinesi":    "https://www.beko.com.tr/kahve-makineleri",
    "elektrikli-supurge":"https://www.beko.com.tr/elektrikli-supurgeler",
    "klima":             "https://www.beko.com.tr/klima",
    "televizyon":        "https://www.beko.com.tr/televizyonlar",
}


async def scrape_beko_deals(
    output_file: str,
    category: str = "buzdolabi",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or BEKO_CATEGORY_URLS.get(category) or f"https://www.beko.com.tr/{category}"
    print(f"[Beko] Başlıyor: {url}", flush=True)

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
                const m = s.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?|\\d+(?:[.,]\\d{2})?/);
                if (!m) return null;
                let raw = m[0];
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if (/^\\d{1,3}(?:\\.\\d{3})+$/.test(raw)) {
                  raw = raw.replace(/\\./g, '');
                }
                const n = parseFloat(raw);
                return isNaN(n) ? null : n;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              let cards = Array.from(document.querySelectorAll('.prd-inner'));
              if (cards.length === 0) cards = Array.from(document.querySelectorAll('.product-item'));
              for (const card of cards) {
                const candidates = Array.from(card.querySelectorAll('a[href]')).filter(a => {
                  const h = a.getAttribute('href') || '';
                  return h && h !== '#' && !/^javascript:/i.test(h);
                });
                const a = candidates[0];
                if (!a) continue;
                let href = a.href;
                if (!href) {
                  let raw = a.getAttribute('href') || '';
                  if (!raw) continue;
                  href = raw.startsWith('/') ? 'https://www.beko.com.tr' + raw : raw;
                }
                if (href.startsWith('/')) href = 'https://www.beko.com.tr' + href;
                if (!/beko\\.com\\.tr/.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                const img = card.querySelector('img');
                let title = (img && img.getAttribute('alt') || '').trim();
                if (/^[A-Z][\\d_]+_/i.test(title) || (/TA\\d|TA\\s\\d/i.test(title) && title.length < 30)) title = '';
                // Promo banner title'larını skip et
                if (/Peşin Fiyat|Taksit|Kampanya|Hediye|Yeşil Buton|Sepette/i.test(title)) title = '';
                if (title.length < 5) {
                  const t = card.querySelector('h3, h2, [class*="name"], [class*="title"]');
                  if (t) title = (t.innerText || t.textContent || '').trim();
                }
                title = title.replace(/^Hızlı İncele\\s+/i, '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;

                const cardText = (card.innerText || '').length > 0 ? card.innerText : (card.textContent || '');
                const priceMatches = cardText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = priceMatches.map(turkishToFloat).filter(p => p && p > 0);
                if (prices.length === 0) continue;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = cardText.match(/-?\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = img && (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original')) || '';
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
                    "source": "beko",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Beko] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Beko] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Beko] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
