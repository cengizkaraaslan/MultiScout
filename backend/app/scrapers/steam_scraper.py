import json
import urllib.request
from datetime import datetime

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


def _format_price_tr(value: float) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


async def scrape_steam_deals(
    output_file: str,
    category: str = "oyun",
    min_discount: int = 10,
    max_pages: int = 1,
):
    url = "https://store.steampowered.com/api/featuredcategories?cc=tr&l=turkish"
    print("[Steam] Başlıyor: featured categories", flush=True)

    deals: list[dict] = []
    raw_count = 0

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        seen_ids: set = set()
        collected: list[dict] = []

        specials = data.get("specials")
        if isinstance(specials, dict):
            items = specials.get("items") or []
            collected.extend(items)

        for key, value in data.items():
            if key == "specials":
                continue
            if isinstance(value, dict):
                items = value.get("items")
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict) and it.get("discounted"):
                            collected.append(it)

        for item in collected:
            if not isinstance(item, dict):
                continue
            app_id = item.get("id")
            if app_id is None or app_id in seen_ids:
                continue
            seen_ids.add(app_id)
            raw_count += 1

            discount = item.get("discount_percent", 0) or 0
            if discount < min_discount:
                continue

            title = item.get("name", "") or ""
            final_cents = item.get("final_price", 0) or 0
            original_cents = item.get("original_price", 0) or 0
            price_tl = final_cents / 100.0
            price_str = _format_price_tr(price_tl)

            image = item.get("large_capsule_image") or item.get("header_image", "") or ""
            link = f"https://store.steampowered.com/app/{app_id}/"

            deal = {
                "title": title,
                "price": price_str,
                "original_price": _format_price_tr(original_cents / 100.0) if original_cents else None,
                "discount_percentage": int(discount),
                "link": link,
                "image": image,
                "category": category,
                "platform": "steam",
                "source": "steam",
                "last_updated": datetime.now().isoformat(),
            }
            deals.append(deal)

        async with get_file_lock(output_file):
            existing = load_deals(output_file)
            merged = merge_deals_by_link(existing, deals)
            save_deals(output_file, merged)

        print(f"[Steam]: {raw_count} ham, {len(deals)} kept", flush=True)
        return deals

    except Exception as e:
        print(f"[Steam] HATA: {e}", flush=True)
        return deals
