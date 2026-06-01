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


async def scrape_karaca_deals(
    output_file: str,
    category: str = "kahve-makineleri",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or f"https://www.karaca.com/{category}"
    print(f"[Karaca] Başlıyor: {url}", flush=True)

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
                // Karaca uses "1.234,56" Turkish format (dot thousands, comma decimal)
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if ((raw.match(/\\./g) || []).length === 1 && /\\.\\d{3}$/.test(raw)) {
                  // "1.234" → 1234 (thousands separator, no decimal)
                  raw = raw.replace(/\\./g, '');
                }
                return parseFloat(raw);
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];

              const anchors = Array.from(document.querySelectorAll('a[href*="/urun/"]'));
              for (const a of anchors) {
                let href = a.getAttribute('href') || '';
                if (!href || href === '#') continue;
                if (href.startsWith('/')) href = 'https://www.karaca.com' + href;
                if (!/karaca\\.com.*\\/urun\\//.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                // Walk up to nearest card that contains TL/₺ and isn't too big
                let card = a;
                let found = false;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const t = (card.innerText || card.textContent || '');
                  if (/TL|₺/.test(t) && t.length < 1500) { found = true; break; }
                }
                if (!found || !card) continue;

                // Title: anchor.innerText (Karaca'da gerçek ürün adı) → img.alt → h3
                // Karaca'da bazı img.alt'lar "Fırsat Ürünü A" gibi placeholder olabiliyor
                const img = card.querySelector('img');
                let title = (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim();
                // Anchor text fiyat/rating ile kirleniyorsa kısalt
                // "Title 4.8 (360) + 7.6B kişi favoriledi 12.999 TL" → İlk fiyat veya rating'e kadar
                title = title.split(/\\s+(?:\\d+\\.\\d+\\s*\\(|\\+\\s*\\d+|\\d{1,3}(?:[.,]\\d{3})*[,.]\\d{2}\\s*TL)/)[0].trim();
                if (!title || title.length < 5 || /^F\\u0131rsat\\s*\\u00dcr\\u00fcn\\u00fc/i.test(title)) {
                  // img.alt fallback (placeholder değilse)
                  const altText = img ? (img.getAttribute('alt') || '') : '';
                  if (altText && !/^F\\u0131rsat\\s*\\u00dcr\\u00fcn\\u00fc/i.test(altText)) {
                    title = altText.trim();
                  }
                }
                if (!title || title.length < 5) {
                  const h3 = card.querySelector('h3, h2');
                  if (h3) title = (h3.innerText || h3.textContent || '').trim();
                }
                if (!title || title.length < 5) {
                  const tEl = card.querySelector('[class*="title"], [class*="Title"], [class*="name"], [class*="Name"]');
                  if (tEl) title = (tEl.innerText || tEl.textContent || '').trim();
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;

                const cardText = (card.innerText || card.textContent || '');
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

                let image = '';
                if (img) {
                  image = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original') || '';
                  if (image && image.startsWith('//')) image = 'https:' + image;
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
                    "source": "karaca",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Karaca] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Karaca] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Karaca] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


KARACA_CATEGORY_URLS = {
    "kahve-makineleri":     "https://www.karaca.com/kahve-makineleri",
    "yemek-takimlari":      "https://www.karaca.com/yemek-takimlari",
    "kahvalti-takimi":      "https://www.karaca.com/kahvalti-takimi",
    "catal-kasik-bicak":    "https://www.karaca.com/catal-kasik-bicak-takimlari",
    "tencere-takimlari":    "https://www.karaca.com/tencere-takimlari",
    "tava":                 "https://www.karaca.com/tava",
    "cay-bardagi":          "https://www.karaca.com/cay-bardaklari",
    "su-bardagi":           "https://www.karaca.com/su-bardaklari",
    "kucuk-ev-aletleri":    "https://www.karaca.com/kucuk-ev-aletleri",
    "ev-tekstili":          "https://www.karaca.com/ev-tekstili",
}
