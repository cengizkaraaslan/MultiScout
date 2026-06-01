import asyncio
import random
from datetime import datetime
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


async def scrape_n11_deals(
    output_file: str,
    category: str = "elektronik",
    min_discount: int = 5,
    max_pages: int = 1
):
    url = f"https://www.n11.com/arama?q={quote_plus(category)}"
    deals: list[dict] = []
    print(f"[N11] Başlıyor: {url}", flush=True)

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
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9"},
            )
            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US','en']});
                window.chrome = {runtime: {}};
                """
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.uniform(3, 5))

            title = (await page.title()) or ""
            if "Robot" in title or "Güvenlik" in title:
                print(f"[N11] {category}: olası bot koruması (title='{title}'), 5s daha bekleniyor", flush=True)
                await asyncio.sleep(5)
                title = (await page.title()) or ""
                if "Robot" in title or "Güvenlik" in title:
                    print(f"[N11] {category}: bot koruması aşılamadı (title='{title}'), atlanıyor", flush=True)
                    await browser.close()
                    return

            # N11 lazy-load: tüm ürün listesini gör
            for _ in range(8):
                await page.mouse.wheel(0, random.randint(1200, 1600))
                await page.wait_for_timeout(random.randint(500, 900))
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              const items = Array.from(document.querySelectorAll('a.product-item[href*="/urun/"], a[href*="/urun/"]'));
              items.forEach((linkEl) => {
                const href = linkEl.getAttribute('href') || '';
                if (!href.includes('/urun/')) return;
                const absHref = href.startsWith('http') ? href : 'https://www.n11.com' + href;
                const cleanHref = absHref.split('?')[0];
                if (seen.has(cleanHref)) return;
                seen.add(cleanHref);
                // N11 ürün card'ı linkEl'i kendisi içerir
                const container = linkEl.closest('[class*="searchResults"], [class*="productList"], section, div') || linkEl;
                // İLK img kupon/badge rozeti olabilir (class="square-size", parent="top-left-badge")
                // Gerçek ürün resmi: img.listing-items-image veya img.swiper-lazy
                const img = linkEl.querySelector('img.listing-items-image, img.swiper-lazy')
                  || Array.from(linkEl.querySelectorAll('img')).find(i => {
                       const cls = typeof i.className === 'string' ? i.className : '';
                       const alt = i.getAttribute('alt') || '';
                       // kupon/badge ve add-icon filtrele
                       if (/square-size|card-add-button-icon|top-left-badge|coupon|kupon|voucher/i.test(cls)) return false;
                       if (/^(SQUARE|add-icon|kupon|coupon)$/i.test(alt)) return false;
                       const par = i.parentElement;
                       const parCls = par && typeof par.className === 'string' ? par.className : '';
                       if (/top-left-badge|coupon|kupon|badge/i.test(parCls)) return false;
                       return true;
                     })
                  || linkEl.querySelector('img');
                let title = (img?.getAttribute('alt') || linkEl.getAttribute('title') || linkEl.getAttribute('aria-label') || '').trim();
                // alt "SQUARE"/"add-icon" + olası whitespace/casing varyasyonları: başlık değildir
                if (title && /^(square|add[-_ ]?icon|kupon|coupon|badge|logo|tasarim)$/i.test(title)) title = '';
                if (!title || title.length < 5) {
                  const titleEl = linkEl.querySelector('h3, h2, [class*="productName"], [class*="title"], [class*="name"]');
                  if (titleEl) title = titleEl.innerText.trim();
                }
                if (!title || title.length < 5) {
                  const lines = (linkEl.innerText || '').split('\\n').map(s => s.trim()).filter(s => s.length > 5 && !/TL|%|^[\\d.,]+$/.test(s));
                  title = lines[0] || '';
                }
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) return;
                const txt = linkEl.innerText || '';
                const tlMatches = txt.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?\\s*TL|\\d+,\\d{2}\\s*TL|\\d{3,}\\s*TL/g) || [];
                const prices = tlMatches.map(turkishToFloat).filter(v => v && v > 0);
                if (prices.length === 0) return;
                // En düşük geçerli fiyatı seç (en az 3 TL — gramaj/birim fiyatlarını ele)
                const validPrices = prices.filter(p => p >= 3);
                if (validPrices.length === 0) return;
                const current = Math.min(...validPrices);
                const original = validPrices.length > 1 ? Math.max(...validPrices) : null;
                let discount = 0;
                if (original && original > current) discount = Math.round(((original - current) / original) * 100);
                // Sadece eksi-yüzde formatı kabul et (indirim badge): "-%30"
                const badge = txt.match(/-\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }
                if (discount > 90) return;  // gürültü
                // src "data:image/svg+xml..." gibi placeholder olabilir → o zaman data-src'i tercih et
                const srcAttr = img?.getAttribute('src') || '';
                const dataSrcAttr = img?.getAttribute('data-src') || '';
                let image = (srcAttr && !srcAttr.startsWith('data:')) ? srcAttr : (dataSrcAttr || srcAttr);
                if (image && image.startsWith('//')) image = 'https:' + image;
                out.push({title: title.substring(0,150), price: formatTL(current), discount, link: cleanHref, image});
              });
              return out;
            }""")

            raw = len(products_data)
            kept = 0
            for prod in products_data:
                discount = prod.get("discount", 0)
                if discount < min_discount:
                    continue
                # Defansif: title badge alt-text'i / image /org/ path'inde ise = atla
                # Valid n11scdn ürün resmi: /a1/{boyut}/.../IMG-xxx.jpg
                # Badge/sponsor logosu:   /a1/org/.../xxx.png
                ptitle = (prod.get("title") or "").strip()
                pimage = prod.get("image") or ""
                badge_titles = {"SQUARE", "ADD-ICON", "ADDICON", "KUPON", "COUPON", "BADGE", "LOGO"}
                if ptitle.upper() in badge_titles or "n11scdn.akamaized.net/a1/org/" in pimage:
                    continue
                # Çok kısa veya tek-kelime title da şüpheli (en az 12 karakter ürün başlığı için)
                if len(ptitle) < 12:
                    continue
                deals.append({
                    "title": prod.get("title", ""),
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": prod.get("link", ""),
                    "image": prod.get("image", ""),
                    "source": "n11",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1
            print(f"[N11] {category}: {raw} ham, {kept} kept", flush=True)
            await browser.close()
    except Exception as e:
        print(f"[N11] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[N11] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


async def scrape_n11_prices(search_query: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"https://www.n11.com/arama?q={quote_plus(search_query)}", timeout=60000, wait_until="networkidle")

            data = await page.evaluate("""() => {
                const item = document.querySelector('a.product-card, a[href*="/p/"]');
                if (!item) return null;
                const titleEl = item.querySelector('.product-card__detail-title, h3, [class*="title"], [class*="name"]');
                const priceEl = item.querySelector('.product-card__detail-prices-price, [class*="price"]');
                return {
                    title: titleEl ? titleEl.innerText.trim() : '',
                    price: priceEl ? priceEl.innerText.trim() : 'N/A'
                };
            }""")
            await browser.close()
            return [data] if data else []
    except Exception:
        return []
