"""Hakmar Express scraper — hakmarexpress.com.tr

Hakmar Express bir indirim marketi zinciri (BİM/ŞOK tarzı). Sitede klasik
"%X indirim" / üstü çizili eski-fiyat bilgisi YOKTUR — her gün düşük fiyat
modeli kullanır. Bu nedenle:
  - product-vertical-discount-container içindeki .old-price ve .discount-price
    span'leri neredeyse her zaman boştur.
  - Ürün hâlâ "fırsat" olarak yayınlanır (discount_percentage=0); admin
    paneli min_discount=0 ile filtreleyebilir.
  - Eğer bir gün .old-price dolu olursa, gerçek indirim yüzdesi hesaplanır.

URL örüntüsü:
  - Kategori sayfaları: https://www.hakmarexpress.com.tr/{slug}-c
    (slug-c suffix, ör. meyve-sebze-c, temel-gida-c)
  - Ürün sayfaları: /{slug}-{id}-p (ör. /patates-500-gr-1000809-p)

Ürün card DOM:
  div.product-vertical-view-container > a[href="/...-p"] > img.product-image-wrapper
  + KARDES div.product-vertical-info > a.product-vertical-title (başlık)
      + div.product-vertical-price ("19,98 ₺")
      + div.product-vertical-discount-container > .old-price + .discount-price
"""
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


async def scrape_hakmarexpress_deals(
    output_file: str,
    category: str = "temel-gida",
    min_discount: int = 5,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """
    Hakmar Express kategori sayfasından ürünleri çeker.

    category: API slug ("-c" suffix'siz). Örn. "temel-gida", "meyve-sebze".
    category_url: doğrudan URL ile bypass. Sağlanmazsa
        https://www.hakmarexpress.com.tr/{category}-c kullanılır.
    """
    deals: list[dict] = []
    base = "https://www.hakmarexpress.com.tr"
    slug = category if category.endswith("-c") else f"{category}-c"
    url = category_url or f"{base}/{slug}"
    print(f"[HakmarExpress] Başlıyor: {url}", flush=True)

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
                extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9"},
            )
            await context.add_init_script(STEALTH)
            page = await context.new_page()

            # SPA: önce anasayfayı ziyaret edip çerez/session warm-up yap
            await page.goto(base, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2.0, 3.0))

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(3.5, 5.0))

            # 404 sayfasına yönlendirildiyse iptal
            cur_url = page.url
            if "/404" in cur_url:
                print(f"[HakmarExpress] {category}: 404 ({cur_url}), atlanıyor", flush=True)
                await browser.close()
                # gene de boş kaydetmeyi atla — sadece return
                return

            # Lazy-load: tüm ürün kartlarını yüklemek için scroll
            for _ in range(20):
                await page.mouse.wheel(0, random.randint(1500, 2200))
                await page.wait_for_timeout(random.randint(450, 750))
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

              // Hakmar'da bir ürün kartı = tek bir div.product-vertical-view-container,
              // İÇİNDE:
              //   <a href="/...-p"><img class="product-image-wrapper"></a>
              //   <span class="badge-wrapper"></span>
              //   <div class="badge-buttons-container">…favori/liste btn</div>
              //   <div class="product-vertical-info">
              //     <a class="product-vertical-title">Başlık</a>
              //     <div class="product-vertical-price">19,98 ₺</div>
              //     <div class="product-vertical-discount-container">…</div>
              //   </div>
              // titleEl → parent (.product-vertical-info) → parent (.product-vertical-view-container = CARD).
              const titleAnchors = Array.from(document.querySelectorAll('a.product-vertical-title'));
              for (const titleEl of titleAnchors) {
                const href = titleEl.getAttribute('href') || '';
                if (!href || !/-\\d+-p$/.test(href)) continue;
                const absHref = href.startsWith('http') ? href : 'https://www.hakmarexpress.com.tr' + href;
                if (seen.has(absHref)) continue;
                seen.add(absHref);

                const title = (titleEl.textContent || '').replace(/\\s+/g, ' ').trim();
                if (title.length < 3) continue;

                const info = titleEl.closest('.product-vertical-info');
                if (!info) continue;
                const card = info.closest('.product-vertical-view-container');
                // Card image-link a[href$="-p"] (info içindeki title anchor'ından farklı, görseli wrap eden)
                let viewContainer = card;

                // Fiyatlar
                const priceEl = info.querySelector('.product-vertical-price');
                const priceTxt = priceEl ? priceEl.textContent : '';
                const current = turkishToFloat(priceTxt);
                if (!current || current <= 0) continue;
                // sepete eklenmeden gösterilen kuruşsuz "0,00 ₺" sepet özet yazısı vs. ele
                if (current < 0.5) continue;

                // İndirim alanı (genellikle boş)
                const oldEl = info.querySelector('.old-price');
                const discEl = info.querySelector('.discount-price');
                const oldTxt = oldEl ? (oldEl.textContent || '').trim() : '';
                const discTxt = discEl ? (discEl.textContent || '').trim() : '';
                let originalPrice = null;
                let discount = 0;
                // .old-price üstü çizili eski fiyat
                if (oldTxt) {
                  const ov = turkishToFloat(oldTxt);
                  if (ov && ov > current) {
                    originalPrice = ov;
                    discount = Math.round(((ov - current) / ov) * 100);
                  }
                }
                // .discount-price doluysa, ya yüzde ya da yeni fiyat olabilir
                if (!discount && discTxt) {
                  const pctMatch = discTxt.match(/(\\d{1,2})\\s*%/);
                  if (pctMatch) {
                    const b = parseInt(pctMatch[1]);
                    if (b >= 1 && b <= 90) discount = b;
                  }
                }

                // Resim: product-image-wrapper class'ı — KUPON/badge'leri ele:
                //   button içindeki SVG'ler, badge-wrapper span'i, ant icon'lar.
                let image = '';
                if (viewContainer) {
                  // Sadece kart kökündeki <a href$="-p"> içindeki görseli al
                  // (badge-buttons-container içindeki SVG/button'ları atla,
                  //  product-vertical-info içindeki içerikleri atla)
                  const imgEls = Array.from(viewContainer.querySelectorAll(':scope > a img, :scope > a > div img'));
                  for (const im of imgEls) {
                    const cls = typeof im.className === 'string' ? im.className : '';
                    const src = im.getAttribute('src') || im.getAttribute('data-src') || '';
                    if (!src || src.startsWith('data:')) continue;
                    // güvence: /ikonlar/ (haftaninurunu.png) ve toolbar/footer ele
                    if (/\\/ikonlar\\//i.test(src)) continue;
                    if (/db-toolbar|footer/i.test(cls)) continue;
                    if (/product-image-wrapper/i.test(cls) || !image) {
                      image = src;
                      if (/product-image-wrapper/i.test(cls)) break;
                    }
                  }
                  // fallback: kart kökündeki herhangi bir img
                  if (!image) {
                    const fallback = Array.from(viewContainer.querySelectorAll('img')).find(im => {
                      const cls = typeof im.className === 'string' ? im.className : '';
                      const src = im.getAttribute('src') || im.getAttribute('data-src') || '';
                      if (!src || src.startsWith('data:')) return false;
                      if (/\\/ikonlar\\//i.test(src)) return false;
                      // badge/button içindeki img'ları ele
                      let par = im.parentElement;
                      for (let k = 0; k < 4 && par; k++, par = par.parentElement) {
                        const pcls = typeof par.className === 'string' ? par.className : '';
                        if (/badge-wrapper|badge-buttons|ant-btn|coupon|kupon/i.test(pcls)) return false;
                      }
                      return true;
                    });
                    if (fallback) image = fallback.getAttribute('src') || fallback.getAttribute('data-src') || '';
                  }
                }
                if (image && image.startsWith('//')) image = 'https:' + image;

                out.push({
                  title: title.substring(0, 150),
                  price: formatTL(current),
                  original: originalPrice ? formatTL(originalPrice) : null,
                  discount,
                  link: absHref,
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
                    "title": (prod.get("title") or "")[:150],
                    "price": prod.get("price", "N/A"),
                    "discount_percentage": discount,
                    "link": link,
                    "image": prod.get("image", ""),
                    "source": "hakmarexpress",
                    "category": category,
                    "last_updated": datetime.now().isoformat(),
                })
                kept += 1

            print(f"[HakmarExpress] {category}: {raw_count} ham, {kept} kept (min_discount={min_discount})", flush=True)
            await browser.close()

    except Exception as e:
        print(f"[HakmarExpress] HATA ({category}): {e}", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(f"[HakmarExpress] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...", flush=True)
        save_deals(output_file, merged)
