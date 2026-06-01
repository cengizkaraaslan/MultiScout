import asyncio
import random
from datetime import datetime
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [{name:'X'}]});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr']});
Object.defineProperty(navigator, 'platform', {get: () => 'iPhone'});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 5});
window.chrome = {runtime: {}};
"""


async def scrape_decathlon_deals(
    output_file: str,
    category: str = "spor",
    min_discount: int = 5,
    max_pages: int = 1
):
    deals: list[dict] = []
    url = f"https://www.decathlon.com.tr/search?Ntt={quote_plus(category)}"
    print(f"[Decathlon] Başlıyor: {url}", flush=True)

    # 3 deneme, her deneme arasında uzun bekleme (rate limit için)
    for attempt in range(3):
        if attempt > 0:
            wait = random.uniform(15, 30)
            print(f"[Decathlon] {category} retry {attempt+1}/3, {wait:.0f}s bekliyor...", flush=True)
            await asyncio.sleep(wait)
        ok, products = await _try_scrape(url, category)
        if ok:
            deals = [d for d in products if d.get("discount", 0) >= min_discount]
            print(f"[Decathlon] {category}: {len(products)} ham, {len(deals)} kept", flush=True)
            break
    else:
        print(f"[Decathlon] {category}: tüm denemeler başarısız", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        normalized = []
        for d in deals:
            normalized.append({
                "title": (d.get("title") or "")[:150],
                "price": d.get("price", "N/A"),
                "discount_percentage": d.get("discount", 0),
                "link": d.get("link", ""),
                "image": d.get("image", ""),
                "source": "decathlon",
                "category": category,
                "last_updated": datetime.now().isoformat()
            })
        merged = merge_deals_by_link(existing, normalized)
        print(f"[Decathlon] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(normalized)})...", flush=True)
        save_deals(output_file, merged)


async def _try_scrape(url: str, category: str) -> tuple[bool, list]:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                viewport={"width": 390, "height": 844},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                ),
                extra_http_headers={
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                },
            )
            await context.add_init_script(STEALTH)
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(6, 9))
            title = await page.title()
            if "dakika lütfen" in title or "Bir dakika" in title:
                await asyncio.sleep(8)
                title = await page.title()
                if "dakika lütfen" in title or "Bir dakika" in title:
                    print(f"[Decathlon] Cloudflare aşılamadı ({category})", flush=True)
                    await browser.close()
                    return False, []

            # Önce scroll, sonra attached durumda selector bekle (visible değil)
            for _ in range(5):
                await page.mouse.wheel(0, random.randint(1000, 1500))
                await page.wait_for_timeout(random.randint(700, 1100))
            try:
                await page.wait_for_selector('a.dpb-product-model-link', state="attached", timeout=10000)
            except Exception:
                # Yine de dene — belki başka class kullanılıyor
                product_count = await page.evaluate("document.querySelectorAll('a[href*=\"/p/\"]').length")
                if product_count < 5:
                    t2 = await page.title()
                    print(f"[Decathlon] {category} ürün yok — title='{t2[:50]}' all-p={product_count}", flush=True)
                    await browser.close()
                    return False, []

            products_data = await page.evaluate("""() => {
              const turkishToFloat = (s) => {
                if (!s) return null;
                const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                return m ? parseFloat(m[0].replace(/\\./g, '').replace(',', '.')) : null;
              };
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const seen = new Set();
              const out = [];
              // Decathlon: sadece ana ürün model linkleri
              const links = Array.from(document.querySelectorAll('a.dpb-product-model-link'));
              const linksByHref = new Map();
              for (const a of links) {
                const href = a.getAttribute('href') || '';
                if (!href.includes('/p/')) continue;
                if (!linksByHref.has(href)) linksByHref.set(href, a);
              }
              for (const [href, linkEl] of linksByHref) {
                const absHref = href.startsWith('http') ? href : 'https://www.decathlon.com.tr' + href;
                if (seen.has(absHref)) continue;
                seen.add(absHref);
                let title = (linkEl.querySelector('.vh, [class*="product-title"]')?.innerText || '').trim();
                if (!title) title = linkEl.getAttribute('aria-label') || (linkEl.innerText || '').trim();
                title = title.replace(/\\s+/g, ' ').trim();
                if (title.length < 5) continue;
                const container = linkEl.closest('article, [class*="product"], [class*="Product"], li, div[class*="dpb"]') || linkEl.parentElement?.parentElement || linkEl;
                const txt = container.innerText || '';
                // ₺X veya X TL formatları
                const tryMatches = (txt.match(/₺\\s*\\d{1,3}(?:[\\.,]\\d{3})*(?:[,\\.]\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}\\s*TL|\\d+,\\d{2}\\s*TL/g) || [])
                    .map(s => s.replace('₺', '').replace(/\\s/g, '').trim());
                const prices = tryMatches.map(turkishToFloat).filter(v => v && v > 0);
                if (prices.length === 0) continue;
                const current = Math.min(...prices);
                const original = prices.length > 1 ? Math.max(...prices) : null;
                let discount = 0;
                if (original && original > current && (original - current) / original > 0.01) {
                  discount = Math.round(((original - current) / original) * 100);
                }
                const badge = txt.match(/%\\s*(\\d{1,2})|-\\s*%(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1] || badge[2]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }
                const imgEl = container.querySelector('img') || linkEl.querySelector('img');
                let image = imgEl?.getAttribute('src') || imgEl?.getAttribute('data-src') || imgEl?.getAttribute('data-original') || '';
                if (image && image.startsWith('//')) image = 'https:' + image;
                out.push({title: title.substring(0,150), price: formatTL(current), discount, link: absHref, image});
              }
              return out;
            }""")

            await browser.close()
            return True, products_data

    except Exception as e:
        print(f"[Decathlon] HATA ({category}): {e}", flush=True)
        return False, []
