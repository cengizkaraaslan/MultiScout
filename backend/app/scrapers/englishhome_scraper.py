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

ENGLISHHOME_CATEGORY_URLS = {
    "havlu":           "https://www.englishhome.com/havlu",
    "nevresim":        "https://www.englishhome.com/nevresim-takimi",
    "yatak-ortusu":    "https://www.englishhome.com/yatak-ortusu",
    "yastik":          "https://www.englishhome.com/yastik",
    "yorgan":          "https://www.englishhome.com/yorgan",
    "kilim":           "https://www.englishhome.com/kilim",
    "perde":           "https://www.englishhome.com/perde",
    "masa-ortusu":     "https://www.englishhome.com/masa-ortusu-runner",
    "mutfak-tekstili": "https://www.englishhome.com/mutfak-tekstili",
    "bebek-tekstili":  "https://www.englishhome.com/bebek-tekstili",
}


async def scrape_englishhome_deals(
    output_file: str,
    category: str = "havlu",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    url = category_url or ENGLISHHOME_CATEGORY_URLS.get(category) or f"https://www.englishhome.com/c-{category}"
    print(f"[EnglishHome] Başlıyor: {url}", flush=True)

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
                // Turkish format: 1.234,56 (dot=thousand, comma=decimal)
                if (raw.includes(',')) {
                  raw = raw.replace(/\\./g, '').replace(',', '.');
                } else if (/\\.\\d{3}(?!\\d)/.test(raw)) {
                  // Pure thousands separator like "1.299" -> 1299
                  raw = raw.replace(/\\./g, '');
                }
                const n = parseFloat(raw);
                return isNaN(n) ? null : n;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';

              const anchors = Array.from(document.querySelectorAll('a[href]'));
              const seen = new Set();
              const out = [];

              for (const a of anchors) {
                const img = a.querySelector('img');
                if (!img) continue;
                const imgAlt = (img.getAttribute('alt') || '').trim();
                if (!imgAlt || imgAlt.length < 5) continue;
                if (/menü|navigasyon|logo|app|google play|app store|icon|banner/i.test(imgAlt)) continue;

                let href = a.getAttribute('href') || '';
                if (!href || href === '#') continue;
                if (href.startsWith('/')) href = 'https://www.englishhome.com' + href;
                if (!/englishhome\\.com/.test(href)) continue;

                let pathname = '';
                try { pathname = new URL(href).pathname; } catch (e) { continue; }
                if (/^\\/(kurumsal|hikayemiz|magazalarimiz|franchising|blog|sss|kategori|kampanya|iletisim|hesap|sepet|favoriler|giris|uyelik|kvkk|gizlilik|cerez|sozlesme|yardim)/i.test(pathname)) continue;
                if (pathname === '/' || pathname === '') continue;
                if (seen.has(href)) continue;

                // Walk up to find a card-sized container with TL
                let card = a;
                let found = false;
                for (let i = 0; i < 6; i++) {
                  if (!card.parentElement) break;
                  card = card.parentElement;
                  const cls = typeof card.className === 'string' ? card.className : '';
                  if (/app-text|footer|header|nav|menu/i.test(cls)) continue;
                  const t = (card.innerText || card.textContent || '');
                  if (/TL|₺/.test(t) && t.length < 1500) { found = true; break; }
                }
                if (!found) continue;

                let title = imgAlt;
                if (title.length < 5) {
                  const t = card.querySelector('h3, h2, [class*="name"], [class*="title"]');
                  if (t) title = (t.innerText || t.textContent || '').trim();
                }
                title = (title || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;
                if (/Üzeri Alışveriş|Alışverişlerinizde|Üzeri Tüm|hediye/i.test(title)) continue;

                const cardText = (card.innerText && card.innerText.length > 0) ? card.innerText : (card.textContent || '');
                // Filter "X TL Üzeri" / "X TL ve Üzeri" promo thresholds
                const cleanedText = cardText.replace(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)\\s*(?:ve\\s*)?Üzeri/gi, '');

                const tlMatches = cleanedText.match(/\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?\\s*(?:TL|₺)/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter((n) => n && n > 5);
                if (prices.length === 0) continue;

                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = cleanedText.match(/%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }

                let image = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;
                if (image && image.startsWith('/')) image = 'https://www.englishhome.com' + image;

                seen.add(href);
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
                title = (prod.get("title") or "").strip()
                if len(title) < 5:
                    continue
                deals.append({
                    "title": title[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "englishhome",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[EnglishHome] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[EnglishHome] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[EnglishHome] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
