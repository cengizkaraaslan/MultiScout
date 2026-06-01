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


async def scrape_koton_deals(
    output_file: str,
    category: str = "kadin",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    deals: list[dict] = []
    if category_url:
        url = category_url
    else:
        url = f"https://www.koton.com/arama?q={quote_plus(category)}"
    print(f"[Koton] Başlıyor: {url}", flush=True)

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
              const formatTL = (n) => n.toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' TL';
              const out = [];
              const seen = new Set();
              // Koton, her .product-item içinde `<div class="js-insider-product">` JSON taşır:
              //   { id, name, url, unit_price, unit_sale_price, product_image_url }
              // En güvenilir yol: bunu parse et.
              const cards = Array.from(document.querySelectorAll('.product-item'));
              for (const card of cards) {
                const jsonDiv = card.querySelector('.js-insider-product');
                if (!jsonDiv) continue;
                let data = null;
                try {
                  data = JSON.parse((jsonDiv.textContent || '').trim());
                } catch (e) { continue; }
                if (!data) continue;
                const link = (data.url || '').trim();
                if (!link || seen.has(link)) continue;
                seen.add(link);
                const title = (data.name || '').trim();
                if (title.length < 3) continue;
                const cur = parseFloat(data.unit_sale_price);
                const orig = parseFloat(data.unit_price);
                if (!cur || cur <= 0) continue;
                let discount = 0;
                if (orig && orig > cur) discount = Math.round(((orig - cur) / orig) * 100);
                // Badge override: card içinde "%XX" varsa öncelikli
                const cardTxt = card.innerText || '';
                const badge = cardTxt.match(/%\\s*(\\d{1,2})\\s+İNDİRİM/i) || cardTxt.match(/-\\s*%\\s*(\\d{1,2})/);
                if (badge) {
                  const b = parseInt(badge[1]);
                  if (b >= 1 && b <= 90 && b > discount) discount = b;
                }
                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(cur),
                  discount,
                  link,
                  image: data.product_image_url || '',
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
                    "source": "koton",
                    "category": category,
                    "last_updated": datetime.now().isoformat()
                })
                kept += 1

            print(f"[Koton] {category}: {raw_count} ham, {kept} kept", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[Koton] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[Koton] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)


KOTON_CATEGORY_URLS = {
    "kadin-elbise": "https://www.koton.com/kadin-elbise",
    "kadin-pantolon": "https://www.koton.com/kadin-pantolon",
    "kadin-bluz": "https://www.koton.com/kadin-bluz",
    "kadin-tisort": "https://www.koton.com/kadin-t-shirt",
    "kadin-mont": "https://www.koton.com/kadin-mont-kaban",
    "kadin-etek": "https://www.koton.com/kadin-etek",
    "erkek-tisort": "https://www.koton.com/erkek-t-shirt",
    "erkek-pantolon": "https://www.koton.com/erkek-pantolon",
    "erkek-gomlek": "https://www.koton.com/erkek-gomlek",
    "erkek-sweatshirt": "https://www.koton.com/erkek-sweatshirt",
    "erkek-mont": "https://www.koton.com/erkek-mont-kaban",
    "cocuk-kiyafet": "https://www.koton.com/cocuk",
}
