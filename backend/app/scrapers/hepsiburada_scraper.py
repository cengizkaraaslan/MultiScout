import asyncio
import random
from datetime import datetime
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
window.chrome = {runtime: {}, app: {}, csi: () => {}, loadTimes: () => {}};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters)
);
"""


async def scrape_hepsiburada_deals(
    output_file: str,
    category: str = "elektronik",
    min_discount: int = 5,
    max_pages: int = 1
):
    deals: list[dict] = []
    # m.hepsiburada.com bazı network'lerde DNS çözülemez, hep desktop kullan
    ua = DESKTOP_UA
    viewport = {"width": 1920, "height": 1080}
    url = f"https://www.hepsiburada.com/ara?q={quote_plus(category)}&filter%5Bdiscounted%5D=true"
    print(f"[Hepsiburada] Başlıyor: {url}", flush=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--disable-extensions",
                    "--disable-default-apps",
                ]
            )
            context = await browser.new_context(
                viewport=viewport,
                user_agent=ua,
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                extra_http_headers={
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Sec-Ch-Ua": '"Chromium";v="121", "Not A(Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
            )
            await context.add_init_script(STEALTH_SCRIPT)
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2.5, 4.5))
            title = await page.title()
            print(f"[Hepsiburada] Sayfa başlığı: {title}", flush=True)
            if "Güvenlik" in title or "Robot" in title or "DDoS" in title.lower():
                await asyncio.sleep(random.uniform(4, 7))
                title = await page.title()
                if "Güvenlik" in title or "Robot" in title:
                    print(f"[Hepsiburada] Bot duvarına takıldı, atlanıyor.", flush=True)
                    await browser.close()
                    return

            for _ in range(4):
                await page.mouse.wheel(0, random.randint(800, 1400))
                await asyncio.sleep(random.uniform(0.5, 1.2))

            products_data = await page.evaluate("""() => {
                const turkishToFloat = (s) => {
                    if (!s) return null;
                    const m = s.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?|\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+(?:,\\d{2})?/);
                    if (!m) return null;
                    return parseFloat(m[0].replace(/\\./g, '').replace(',', '.'));
                };
                const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' TL';

                const seen = new Set();
                const products = [];

                const items = document.querySelectorAll('li[id^="i"], [class*="horizontalProductCard"], [class*="productCard"]');
                items.forEach((item) => {
                    const linkEl = item.querySelector('a[href*="-p-"]') || (item.tagName === 'A' && item.href?.includes('-p-') ? item : null);
                    if (!linkEl) return;
                    const href = linkEl.getAttribute('href') || '';
                    if (!href.includes('-p-')) return;
                    const absHref = href.startsWith('http') ? href : 'https://www.hepsiburada.com' + href;
                    const cleanHref = absHref.split('?')[0];
                    if (seen.has(cleanHref)) return;
                    seen.add(cleanHref);

                    let title = item.querySelector('[data-test-id^="title-"]')?.innerText?.trim() || '';
                    if (!title) title = linkEl.getAttribute('title') || linkEl.getAttribute('aria-label') || '';
                    if (!title) {
                        const lines = (linkEl.innerText || '').split('\\n').map(s => s.trim()).filter(s => s.length > 5);
                        title = lines[0] || '';
                    }
                    title = title.replace(/\\s+/g, ' ').trim();
                    if (title.length < 5) return;

                    const priceEl = item.querySelector('[data-test-id^="final-price-"]');
                    const priceTxt = priceEl ? priceEl.innerText : (item.innerText || '');
                    const tlMatches = priceTxt.match(/\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?\\s*TL|\\d+,\\d{2}\\s*TL|\\d+(?:\\.\\d{3})+\\s*TL/g) || [];
                    const prices = tlMatches.map(s => turkishToFloat(s)).filter(v => v && v > 0);
                    if (prices.length === 0) return;

                    const current = Math.min(...prices);
                    const original = prices.length > 1 ? Math.max(...prices) : null;
                    let discount = 0;
                    if (original && original > current) {
                        discount = Math.round(((original - current) / original) * 100);
                    }
                    const fullText = item.innerText || '';
                    const badgeMatch = fullText.match(/-\\s*%(\\d{1,2})|%(\\d{1,2})/);
                    if (badgeMatch) {
                        const badge = parseInt(badgeMatch[1] || badgeMatch[2]);
                        if (badge >= 1 && badge <= 90 && badge > discount) discount = badge;
                    }

                    const img = item.querySelector('img');
                    let image = img?.getAttribute('src') || img?.getAttribute('data-src') || '';
                    if (image && image.startsWith('//')) image = 'https:' + image;

                    products.push({
                        title: title.substring(0, 150),
                        price: formatTL(current),
                        discount,
                        link: cleanHref,
                        image
                    });
                });
                return products;
            }""")

            print(f"[Hepsiburada] {category}: {len(products_data)} ham ürün", flush=True)
            kept = 0
            for prod in products_data:
                discount = prod.get("discount", 0)
                if discount < min_discount:
                    continue
                deals.append({
                    "title": prod.get("title", ""),
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": prod.get("link", ""),
                    "image": prod.get("image", ""),
                    "source": "hepsiburada",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1
            print(f"[Hepsiburada] {category}: {kept} ürün min_discount={min_discount}% sonrası kaldı", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Hepsiburada] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Hepsiburada] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


async def scrape_hepsiburada_prices(search_query: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=DESKTOP_UA,
                viewport={"width": 390, "height": 844},
                locale="tr-TR",
            )
            await context.add_init_script(STEALTH_SCRIPT)
            page = await context.new_page()
            await page.goto(f"https://www.hepsiburada.com/ara?q={quote_plus(search_query)}", timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            data = await page.evaluate("""() => {
                const item = document.querySelector('li[id^="i"], a[href*="/p-"]');
                if (!item) return null;
                const title = item.querySelector('[data-test-id="product-card-name"], h3, h2')?.innerText.trim()
                    || item.getAttribute('title')
                    || (item.innerText || '').split('\\n')[0];
                const text = item.innerText || '';
                const m = text.match(/\\d{1,3}(?:\\.\\d{3})*,\\d{2}\\s*TL|\\d+,\\d{2}\\s*TL/);
                return {
                    title: (title || '').trim(),
                    price: m ? m[0] : 'N/A'
                };
            }""")
            await browser.close()
            return [data] if data and data['title'] else []
    except Exception:
        return []
