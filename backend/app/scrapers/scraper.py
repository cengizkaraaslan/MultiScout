import json
import os
import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

FILE_WRITE_LOCK = asyncio.Lock()

CATEGORY_URLS = {
    "elektronik": "https://www.amazon.com.tr/s?i=electronics&s=electronics&pct-off=20-",
    "gida": "https://www.amazon.com.tr/s?i=grocery&s=grocery&pct-off=20-",
    "kitap": "https://www.amazon.com.tr/s?i=stripbooks&s=stripbooks&pct-off=20-",
    "oyuncak": "https://www.amazon.com.tr/s?i=toys&s=toys&pct-off=20-",
    "spor": "https://www.amazon.com.tr/s?i=sports&s=sports&pct-off=20-",
    "moda": "https://www.amazon.com.tr/s?i=fashion&s=fashion&pct-off=20-",
    "ev": "https://www.amazon.com.tr/s?i=home&s=home&pct-off=20-",
    "kisisel-bakim": "https://www.amazon.com.tr/s?i=beauty&s=beauty&pct-off=20-",
    "bebek": "https://www.amazon.com.tr/s?i=baby&s=baby&pct-off=20-",
    "ofis": "https://www.amazon.com.tr/s?i=office-products&s=office-products&pct-off=20-",
}

def load_deals_history(history_file: str):
    """Mevcut fiyat geçmişini yükle"""
    if Path(history_file).exists():
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_asin(link: str) -> str:
    match = re.search(r"/dp/([A-Z0-9]{10})", link)
    return match.group(1) if match else ""


def is_bad_title(title: str) -> bool:
    lowered = title.lower().strip()
    return (
        not lowered
        or lowered == "isimsiz ürün"
        or "yıldız üzerinden" in lowered
        or "fiyat" in lowered
        or "indirim" in lowered
        or lowered.startswith("%")
        or len(lowered) < 8
    )


def parse_turkish_price(value: str) -> float | None:
    match = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", value or "")
    if not match:
        return None
    return float(match.group(0).replace(".", "").replace(",", "."))


def calculate_discount_from_prices(current_price_text: str, old_price_texts: list[str]) -> int:
    current_price = parse_turkish_price(current_price_text)
    if current_price is None or current_price <= 0:
        return 0

    old_prices = []
    for text in old_price_texts:
        old_price = parse_turkish_price(text)
        if old_price and old_price > current_price:
            old_prices.append(old_price)

    if not old_prices:
        return 0

    old_price = min(old_prices)
    calculated_discount = round(((old_price - current_price) / old_price) * 100)
    return calculated_discount if 1 <= calculated_discount <= 90 else 0


async def scrape_amazon_deals(output_file: str, history_file: str = "deals_history.json", category: str = "gida", min_discount: int = 20, max_pages: int = 3):
    print(f"Scraping başladı... Kategori: {category}, Min İndirim: {min_discount}%")
    deals = []
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_timestamp = datetime.now().isoformat(timespec="minutes")

    category_url = CATEGORY_URLS.get(category.lower(), CATEGORY_URLS["gida"])

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.amazon.com.tr/", timeout=120000)
            await asyncio.sleep(random.uniform(2, 4))
            for page_number in range(1, max_pages + 1):
                page_url = f"{category_url}&page={page_number}"
                await page.goto(page_url, timeout=120000, wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(1, 2))
                try:
                    await page.wait_for_load_state("networkidle", timeout=30000)
                except:
                    print("Network idle timeout, continuing anyway...")
                await asyncio.sleep(1)

                page_title = await page.title()
                print("Amazon sayfası yüklendi, HTML başlığı:", page_title)

                html_content = await page.content()
                if "Robot" in page_title or "captcha" in html_content.lower() or "Üzgünüz" in page_title or len(html_content) < 5000:
                    print(f"Bot korumasına yakalanıldı! Başlık: {page_title}, İçerik uzunluğu: {len(html_content)}")
                    break

                for i in range(3):
                    await page.mouse.wheel(0, 1200)
                    await asyncio.sleep(0.7)

                cards = await page.query_selector_all('.ProductCard-module__card_uyr_Jh7WpSkPx4iEpn4w')
                if not cards:
                    cards = await page.query_selector_all('[data-component-type="s-search-result"]')
                if not cards:
                    cards = await page.query_selector_all('div[data-asin]')
                print(f"{category} sayfa {page_number} kart sayısı: {len(cards)}")

                if not cards:
                    break

                for card in cards:
                    try:
                        img_el = await card.query_selector('img')
                        alt_text = await img_el.get_attribute('alt') if img_el else ""
                        title = alt_text.strip() if alt_text and not is_bad_title(alt_text) else "İsimsiz Ürün"

                        if is_bad_title(title):
                            title_div = await card.query_selector('[class*="title"]')
                            if not title_div:
                                title_div = await card.query_selector('div[class*="truncate"]')
                            title = await title_div.inner_text() if title_div else "İsimsiz Ürün"

                        if is_bad_title(title):
                            a_tags = await card.query_selector_all('a[href*="/dp/"]')
                            for a in a_tags:
                                text = (await a.inner_text()).strip()
                                if not is_bad_title(text):
                                    title = text
                                    break

                        # Ürünün kendi fiyatını almak için daha spesifik bir seçici kullanıyoruz
                        # Ana fiyatı al (sadece kartın içindeki .a-price öğesi)
                        price_el = await card.query_selector('.a-price .a-offscreen')
                        if not price_el:
                            price_el = await card.query_selector('.a-price-whole')

                        price_text = await price_el.inner_text() if price_el else ""

                        # Sadece bu kartın içindeki eski fiyatları al
                        old_price_elements = await card.query_selector_all(':scope .a-text-price .a-offscreen, :scope .a-price.a-text-price .a-offscreen')
                        old_price_texts = []
                        for old_price_el in old_price_elements:
                            old_price_text = (await old_price_el.inner_text()).strip()
                            if old_price_text:
                                old_price_texts.append(old_price_text)

                        discount_percentage = calculate_discount_from_prices(price_text, old_price_texts)

                        if discount_percentage == 0:
                            all_text = await card.inner_text()
                            discount_patterns = [
                                r'%\s*(\d{1,2})\s*(?:indirim|tasarruf)',
                                r'(\d{1,2})\s*%\s*(?:indirim|tasarruf)',
                                r'(?:indirim|tasarruf)\s*%\s*(\d{1,2})',
                                r'(?:indirim|tasarruf)\s*(\d{1,2})\s*%',
                            ]
                            for pattern in discount_patterns:
                                match = re.search(pattern, all_text, re.IGNORECASE)
                                if match:
                                    discount_percentage = int(match.group(1))
                                    break

                        link_el = await card.query_selector('a[href*="/dp/"]')
                        link = await link_el.get_attribute('href') if link_el else "#"
                        if link and not link.startswith("http"):
                            link = "https://www.amazon.com.tr" + link

                        img_src = await img_el.get_attribute('src') if img_el else ""

                        product_id = extract_asin(link)

                        if product_id and not is_bad_title(title) and price_text != "Fiyat Görülmüyor" and discount_percentage >= min_discount:
                            current_scrape_entry = {
                                "date": current_date,
                                "price": price_text,
                                "discount_percentage": discount_percentage
                            }

                            deals.append({
                                "title": title,
                                "price": price_text,
                                "discount_percentage": discount_percentage,
                                "link": link,
                                "image": img_src,
                                "category": category,
                                "last_updated": current_timestamp,
                                "price_history": [current_scrape_entry]
                            })
                    except Exception as e:
                        print("Ürün çekme hatası:", e)
                        continue

        except Exception as e:
            print("Sayfa yüklenirken hata:", e)
        finally:
            await browser.close()

    async with FILE_WRITE_LOCK:
        for p_ in (output_file, history_file):
            d_ = os.path.dirname(p_)
            if d_:
                os.makedirs(d_, exist_ok=True)
        history = load_deals_history(history_file)
        existing_deals = []
        if Path(output_file).exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_deals = json.load(f)
            except:
                existing_deals = []

        deals_by_asin = {}
        for deal in existing_deals:
            asin = extract_asin(deal.get("link", ""))
            if asin:
                deals_by_asin[asin] = deal

        for deal in deals:
            asin = extract_asin(deal.get("link", ""))
            if not asin:
                continue

            history_entry = history.get(asin)
            if not history_entry:
                history_entry = {
                    "title": deal["title"],
                    "link": deal["link"],
                    "image": deal["image"],
                    "category": category,
                    "price_history": []
                }
                history[asin] = history_entry
            else:
                history_entry["category"] = category

            current_scrape_entry = deal["price_history"][0]
            last_entry = history_entry["price_history"][-1] if history_entry["price_history"] else None
            if last_entry and last_entry["date"] == current_date:
                history_entry["price_history"][-1] = current_scrape_entry
            else:
                history_entry["price_history"].append(current_scrape_entry)

            deal["price_history"] = [current_scrape_entry]
            deals_by_asin[asin] = deal

        all_deals = list(deals_by_asin.values())

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_deals, f, ensure_ascii=False, indent=4)

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)

    print(f"Scraping bitti. {len(deals)} ürün bulundu.")
