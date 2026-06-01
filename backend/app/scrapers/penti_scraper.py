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

PENTI_CATEGORY_URLS = {
    "sutyen":      "https://www.penti.com/arama?q=s%C3%BCtyen",
    "kulot":       "https://www.penti.com/arama?q=k%C3%BClot",
    "pijama":      "https://www.penti.com/arama?q=pijama",
    "gecelik":     "https://www.penti.com/arama?q=gecelik",
    "corap":       "https://www.penti.com/arama?q=%C3%A7orap",
    "mayo":        "https://www.penti.com/arama?q=mayo",
    "bikini":      "https://www.penti.com/arama?q=bikini",
    "tayt":        "https://www.penti.com/arama?q=tayt",
    "sport-buste": "https://www.penti.com/arama?q=spor+s%C3%BCtyen",
}


async def scrape_penti_deals(
    output_file: str,
    category: str = "sutyen",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    if category_url:
        url = category_url
    elif category in PENTI_CATEGORY_URLS:
        url = PENTI_CATEGORY_URLS[category]
    else:
        url = f"https://www.penti.com/arama?q={quote_plus(category)}"
    print(f"[Penti] Basliyor: {url}", flush=True)

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
              const seen = new Set();
              const out = [];

              // Penti yapısı:
              //   .prd (card root, textLen=2598)
              //     <a class="prd-link" href="/tr/.../p/...">
              //       .prd-block1 (image swiper)
              // Gerçek card: .prd (root), anchor a.prd-link içinde
              let cards = Array.from(document.querySelectorAll('.prd'));
              if (cards.length === 0) {
                // Fallback: a.prd-link'lerden walk-up
                const anchors = Array.from(document.querySelectorAll('a.prd-link, a[href*="/p/"]'));
                const cardSet = new Set();
                anchors.forEach(a => {
                  let c = a;
                  for (let i=0;i<4;i++) { if (!c.parentElement) break; c = c.parentElement; if (typeof c.className === 'string' && /prd|product-card/i.test(c.className)) break; }
                  if (c) cardSet.add(c);
                });
                cards = Array.from(cardSet);
              }

              cards.forEach((card) => {
                // Penti: anchor a.prd-link card içinde veya card wrapper'ı
                const a = card.querySelector('a.prd-link') || card.querySelector('a[href*="/p/"]') || card.querySelector('a[href]');
                if (!a) return;
                let href = a.href || a.getAttribute('href') || '';
                if (!href) return;
                if (href.startsWith('/')) href = 'https://www.penti.com' + href;
                if (!/penti\\.com.*\\/p\\//.test(href)) return;
                if (seen.has(href)) return;
                seen.add(href);

                const img = card.querySelector('img');
                let title = (img && img.getAttribute('alt')) || '';
                title = title.replace(/\\s*-\\s*\\d+\\s*$/, '').trim();
                if (title.length < 5) {
                  const t = card.querySelector('h3, h2, [class*="name"], [class*="Name"], [class*="title"], [class*="Title"]');
                  if (t) title = (t.innerText || t.textContent || '').trim();
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;

                // textContent fallback (innerText display:none olabilir)
                const cardText = (card.innerText || '').length > 0 ? card.innerText : (card.textContent || '');
                const tlMatches = cardText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 0);
                if (prices.length === 0) return;
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
                  if (!image) {
                    const srcset = img.getAttribute('srcset') || '';
                    if (srcset) {
                      image = srcset.split(',')[0].trim().split(' ')[0];
                    }
                  }
                }
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
                    "source": "penti",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Penti] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Penti] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Penti] Toplam {len(merged)} urun kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
