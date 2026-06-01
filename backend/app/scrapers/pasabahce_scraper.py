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

PASABAHCE_CATEGORY_URLS = {
    "sofra":          "https://www.pasabahce.com.tr/sofra",
    "bardak":         "https://www.pasabahce.com.tr/bardak",
    "kahve":          "https://www.pasabahce.com.tr/kahve",
    "cay":            "https://www.pasabahce.com.tr/cay",
    "tabak":          "https://www.pasabahce.com.tr/tabak",
    "vazo":           "https://www.pasabahce.com.tr/vazo",
    "kase":           "https://www.pasabahce.com.tr/kase",
    "cocuk":          "https://www.pasabahce.com.tr/cocuk-sofrasi",
    "outlet":         "https://www.pasabahce.com.tr/outlet",
    "yeni":           "https://www.pasabahce.com.tr/yeni-urunler",
}


async def scrape_pasabahce_deals(
    output_file: str,
    category: str = "sofra",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or PASABAHCE_CATEGORY_URLS.get(category) or f"https://www.pasabahce.com.tr/{category}"
    print(f"[Pasabahce] Başlıyor: {url}", flush=True)

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
                await page.wait_for_timeout(random.randint(700, 1100))

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:[.,]\\d{2})?/);
                if (!m) return null;
                let raw = m[0];
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if (/^\\d{1,3}(?:\\.\\d{3})+$/.test(raw)) {
                  raw = raw.replace(/\\./g, '');
                }
                return parseFloat(raw);
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              const anchors = Array.from(document.querySelectorAll('a[href*="-p-"]'));
              for (const a of anchors) {
                let href = a.href || a.getAttribute('href') || '';
                if (!href) continue;
                if (href.startsWith('/')) href = 'https://www.pasabahce.com.tr' + href;
                if (!/pasabahce\\.com/.test(href)) continue;
                if (!/-p-\\d+|-p-[\\w-]+/.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);

                let card = a;
                let found = false;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const t = (card.innerText || card.textContent || '');
                  if (/TL|₺/.test(t) && t.length < 600) { found = true; break; }
                }
                if (!found) continue;
                const cardText = (card.innerText || card.textContent || '');
                const cleanedText = cardText.replace(/\\d+\\s*TL\\s*ve\\s*ü(?:zeri|stü)/gi, '');

                const img = a.querySelector('img') || card.querySelector('img');
                let title = (img?.getAttribute('alt') || '').trim();
                if (/^(Paşabahçe|Logo|Banner)$/i.test(title)) title = '';
                if (title.length < 5) {
                  const t = card.querySelector('h3, h2, [class*="name"], [class*="title"], [class*="product-name"]');
                  if (t) title = (t.innerText || t.textContent || '').trim();
                }
                if (title.length < 5) {
                  title = (a.innerText || a.textContent || '').trim();
                }
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;

                const prices = (cleanedText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [])
                  .map(turkishToFloat)
                  .filter((p) => p && p > 0);
                if (prices.length === 0) continue;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = cleanedText.match(/-?\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = img?.getAttribute('src') || img?.getAttribute('data-src') || img?.getAttribute('data-original') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;
                if (image && image.startsWith('/')) image = 'https://www.pasabahce.com.tr' + image;

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
                    "source": "pasabahce",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Pasabahce] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Pasabahce] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Pasabahce] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
