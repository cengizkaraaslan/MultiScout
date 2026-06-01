from fastapi import APIRouter, BackgroundTasks, Query, Depends, HTTPException
from datetime import datetime
import asyncio
from app.core.auth import require_api_key

router = APIRouter()

SCRAPE_ALL_STATUS = {
    "amazon": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "trendyol": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "hepsiburada": {"status": "idle", "message": "Stealth modu deneme aşamasında", "current_category": None, "updated_at": None},
    "n11": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "pazarama": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "ciceksepeti": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "vatan": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "teknosa": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "decathlon": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "steam": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "defacto": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "mediamarkt": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "gratis": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "a101": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "bim": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "sok": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "migros": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "carrefoursa": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "tarimkredi": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "hakmarexpress": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "macrocenter": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "bizimtoptan": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "peynircibaba": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "burgerking": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "mcdonalds": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "vodafone": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "turkcell": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "turktelekom": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "maximum": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "bonus": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "world": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "axess": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "lcwaikiki": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "koton": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "mavi": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "boyner": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "penti": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "watsons": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "dr": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "karaca": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "englishhome": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "idefix": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "tchibo": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "mudo": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "madamecoco": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "vivense": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "tepehome": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "skechers": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "toyzz": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "yargici": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "kitapyurdu": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "pttavm": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "sportive": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "newbalance": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "flo": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "hummel": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "evidea": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "beko": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "arcelik": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "vestel": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "network": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "northface": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "mac": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "apple": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "saatvesaat": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "altinbas": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "pasabahce": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "akakce": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "ramsey": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "atasay": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "reebok": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "sarar": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "huawei": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "lego": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "casper": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
    "monster": {"status": "idle", "message": "", "current_category": None, "updated_at": None},
}

# marketfiyati API ile beslenen marketler — tek API call ile 6 market beraber çıkar
MARKETFIYATI_PLATFORMS = {"a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi"}

CONCURRENT_SCRAPES = 2


def _aggregate_status() -> dict:
    statuses = [v.get("status") for v in SCRAPE_ALL_STATUS.values()]
    if "running" in statuses:
        top = "running"
    elif "error" in statuses:
        top = "error"
    elif statuses and all(s in ("completed", "idle", "disabled") for s in statuses):
        top = "completed" if "completed" in statuses else "idle"
    else:
        top = "idle"
    messages = [v.get("message") for v in SCRAPE_ALL_STATUS.values() if v.get("message")]
    return {
        "status": top,
        "message": "; ".join(m for m in messages if m) or "",
        "updated_at": datetime.now().isoformat(),
    }


async def run_platform_scrape(platform: str, min_discount: int):
    from app.scrapers.scraper import scrape_amazon_deals, CATEGORY_URLS
    from app.scrapers.trendyol_scraper import scrape_trendyol_deals
    from app.scrapers.n11_scraper import scrape_n11_deals
    from app.scrapers.hepsiburada_scraper import scrape_hepsiburada_deals
    from app.scrapers.pazarama_scraper import scrape_pazarama_deals
    from app.scrapers.ciceksepeti_scraper import scrape_ciceksepeti_deals
    from app.scrapers.vatan_scraper import scrape_vatan_deals
    from app.scrapers.teknosa_scraper import scrape_teknosa_deals
    from app.scrapers.decathlon_scraper import scrape_decathlon_deals
    from app.scrapers.steam_scraper import scrape_steam_deals
    from app.scrapers.defacto_scraper import scrape_defacto_deals
    from app.scrapers.mediamarkt_scraper import scrape_mediamarkt_deals
    from app.scrapers.gratis_scraper import scrape_gratis_deals
    from app.scrapers.marketfiyati_scraper import scrape_marketfiyati_all, ALL_MARKET_KEYS as MF_KEYS
    from app.scrapers.hakmarexpress_scraper import scrape_hakmarexpress_deals
    from app.scrapers.macrocenter_scraper import scrape_macrocenter_deals
    from app.scrapers.bizimtoptan_scraper import scrape_bizimtoptan_deals
    from app.scrapers.peynircibaba_scraper import scrape_peynircibaba_deals
    from app.scrapers.burgerking_scraper import scrape_burgerking_deals
    from app.scrapers.mcdonalds_scraper import scrape_mcdonalds_deals
    from app.scrapers.vodafone_scraper import scrape_vodafone_deals
    from app.scrapers.turkcell_scraper import scrape_turkcell_deals
    from app.scrapers.turktelekom_scraper import scrape_turktelekom_deals
    from app.scrapers.maximum_scraper import scrape_maximum_deals
    from app.scrapers.bonus_scraper import scrape_bonus_deals
    from app.scrapers.world_scraper import scrape_world_deals
    from app.scrapers.axess_scraper import scrape_axess_deals
    from app.scrapers.lcwaikiki_scraper import scrape_lcwaikiki_deals
    from app.scrapers.koton_scraper import scrape_koton_deals
    from app.scrapers.mavi_scraper import scrape_mavi_deals
    from app.scrapers.boyner_scraper import scrape_boyner_deals
    from app.scrapers.penti_scraper import scrape_penti_deals
    from app.scrapers.watsons_scraper import scrape_watsons_deals
    from app.scrapers.dr_scraper import scrape_dr_deals
    from app.scrapers.karaca_scraper import scrape_karaca_deals
    from app.scrapers.englishhome_scraper import scrape_englishhome_deals
    from app.scrapers.idefix_scraper import scrape_idefix_deals
    from app.scrapers.tchibo_scraper import scrape_tchibo_deals
    from app.scrapers.mudo_scraper import scrape_mudo_deals
    from app.scrapers.madamecoco_scraper import scrape_madamecoco_deals
    from app.scrapers.vivense_scraper import scrape_vivense_deals
    from app.scrapers.tepehome_scraper import scrape_tepehome_deals
    from app.scrapers.skechers_scraper import scrape_skechers_deals
    from app.scrapers.toyzz_scraper import scrape_toyzz_deals
    from app.scrapers.yargici_scraper import scrape_yargici_deals
    from app.scrapers.kitapyurdu_scraper import scrape_kitapyurdu_deals
    from app.scrapers.pttavm_scraper import scrape_pttavm_deals
    from app.scrapers.sportive_scraper import scrape_sportive_deals
    from app.scrapers.newbalance_scraper import scrape_newbalance_deals
    from app.scrapers.flo_scraper import scrape_flo_deals
    from app.scrapers.hummel_scraper import scrape_hummel_deals
    from app.scrapers.evidea_scraper import scrape_evidea_deals
    from app.scrapers.beko_scraper import scrape_beko_deals
    from app.scrapers.arcelik_scraper import scrape_arcelik_deals
    from app.scrapers.vestel_scraper import scrape_vestel_deals
    from app.scrapers.network_scraper import scrape_network_deals
    from app.scrapers.northface_scraper import scrape_northface_deals
    from app.scrapers.mac_scraper import scrape_mac_deals
    from app.scrapers.apple_scraper import scrape_apple_deals
    from app.scrapers.saatvesaat_scraper import scrape_saatvesaat_deals
    from app.scrapers.altinbas_scraper import scrape_altinbas_deals
    from app.scrapers.pasabahce_scraper import scrape_pasabahce_deals
    from app.scrapers.akakce_scraper import scrape_akakce_deals
    from app.scrapers.ramsey_scraper import scrape_ramsey_deals
    from app.scrapers.atasay_scraper import scrape_atasay_deals
    from app.scrapers.reebok_scraper import scrape_reebok_deals
    from app.scrapers.sarar_scraper import scrape_sarar_deals
    from app.scrapers.huawei_scraper import scrape_huawei_deals
    from app.scrapers.lego_scraper import scrape_lego_deals
    from app.scrapers.casper_scraper import scrape_casper_deals
    from app.scrapers.monster_scraper import scrape_monster_deals
    from app.core.category_mapping import (
        TRENDYOL_CATEGORY_URLS, HEPSIBURADA_CATEGORY_URLS, N11_CATEGORY_URLS,
        PAZARAMA_CATEGORY_URLS, CICEKSEPETI_CATEGORY_URLS,
        VATAN_CATEGORY_URLS, TEKNOSA_CATEGORY_URLS, DECATHLON_CATEGORY_URLS, STEAM_CATEGORY_URLS,
        DEFACTO_CATEGORY_URLS, MEDIAMARKT_CATEGORY_URLS, GRATIS_CATEGORY_URLS,
        MARKETFIYATI_CATEGORIES,
        HAKMAREXPRESS_CATEGORY_URLS, MACROCENTER_CATEGORY_URLS, BIZIMTOPTAN_CATEGORY_URLS,
        PEYNIRCIBABA_CATEGORY_URLS, BURGERKING_CATEGORY_URLS, MCDONALDS_CATEGORY_URLS,
        VODAFONE_CATEGORY_URLS, TURKCELL_CATEGORY_URLS, TURKTELEKOM_CATEGORY_URLS,
        MAXIMUM_CATEGORY_URLS, BONUS_CATEGORY_URLS, WORLD_CATEGORY_URLS, AXESS_CATEGORY_URLS,
        LCWAIKIKI_CATEGORY_URLS, KOTON_CATEGORY_URLS, MAVI_CATEGORY_URLS,
        BOYNER_CATEGORY_URLS, PENTI_CATEGORY_URLS, WATSONS_CATEGORY_URLS, DR_CATEGORY_URLS,
        KARACA_CATEGORY_URLS, ENGLISHHOME_CATEGORY_URLS, IDEFIX_CATEGORY_URLS, TCHIBO_CATEGORY_URLS,
        MUDO_CATEGORY_URLS, MADAMECOCO_CATEGORY_URLS, VIVENSE_CATEGORY_URLS,
        TEPEHOME_CATEGORY_URLS, SKECHERS_CATEGORY_URLS,
        TOYZZ_CATEGORY_URLS, YARGICI_CATEGORY_URLS, KITAPYURDU_CATEGORY_URLS,
        PTTAVM_CATEGORY_URLS, SPORTIVE_CATEGORY_URLS, NEWBALANCE_CATEGORY_URLS,
        FLO_CATEGORY_URLS, HUMMEL_CATEGORY_URLS, EVIDEA_CATEGORY_URLS,
        BEKO_CATEGORY_URLS, ARCELIK_CATEGORY_URLS, VESTEL_CATEGORY_URLS,
        NETWORK_CATEGORY_URLS, NORTHFACE_CATEGORY_URLS,
        MAC_CATEGORY_URLS, APPLE_CATEGORY_URLS,
        SAATVESAAT_CATEGORY_URLS, ALTINBAS_CATEGORY_URLS, PASABAHCE_CATEGORY_URLS,
        AKAKCE_CATEGORY_URLS, RAMSEY_CATEGORY_URLS, ATASAY_CATEGORY_URLS,
        REEBOK_CATEGORY_URLS, SARAR_CATEGORY_URLS, HUAWEI_CATEGORY_URLS, LEGO_CATEGORY_URLS,
        CASPER_CATEGORY_URLS, MONSTER_CATEGORY_URLS,
    )
    from app.services.sync_service import sync_json_to_db, PLATFORM_FILES
    from app.models.database import get_db

    global SCRAPE_ALL_STATUS
    print(f"[DEBUG] Platform taraması başladı: {platform}", flush=True)

    SCRAPE_ALL_STATUS[platform] = {
        "status": "running",
        "message": f"{platform.capitalize()} taraması yapılıyor...",
        "current_category": None,
        "updated_at": datetime.now().isoformat()
    }

    try:
        if platform == "amazon":
            categories = list(CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_amazon_deals(PLATFORM_FILES["amazon"], "data/deals_history.json", cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "trendyol":
            categories = list(TRENDYOL_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_trendyol_deals(PLATFORM_FILES["trendyol"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "n11":
            categories = list(N11_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_n11_deals(PLATFORM_FILES["n11"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "hepsiburada":
            categories = list(HEPSIBURADA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_hepsiburada_deals(PLATFORM_FILES["hepsiburada"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "pazarama":
            categories = list(PAZARAMA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_pazarama_deals(PLATFORM_FILES["pazarama"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "ciceksepeti":
            categories = list(CICEKSEPETI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_ciceksepeti_deals(PLATFORM_FILES["ciceksepeti"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "vatan":
            categories = list(VATAN_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_vatan_deals(PLATFORM_FILES["vatan"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "teknosa":
            categories = list(TEKNOSA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_teknosa_deals(PLATFORM_FILES["teknosa"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "decathlon":
            # Cloudflare rate limit — kategorileri seri tara, aralarda bekle
            categories = list(DECATHLON_CATEGORY_URLS.keys())
            for i, cat in enumerate(categories):
                try:
                    await scrape_decathlon_deals(PLATFORM_FILES["decathlon"], cat, min_discount)
                except Exception as e:
                    print(f"[Decathlon] {cat} error: {e}", flush=True)
                if i < len(categories) - 1:
                    await asyncio.sleep(20)
        elif platform == "steam":
            await scrape_steam_deals(PLATFORM_FILES["steam"], "oyun", min_discount)
        elif platform == "defacto":
            categories = list(DEFACTO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_defacto_deals(PLATFORM_FILES["defacto"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "mediamarkt":
            categories = list(MEDIAMARKT_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_mediamarkt_deals(PLATFORM_FILES["mediamarkt"], cat, min_discount)
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "gratis":
            categories = list(GRATIS_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_gratis_deals(
                        PLATFORM_FILES["gratis"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=GRATIS_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "hakmarexpress":
            # Hakmar Express: everyday-low-price model → discount yok, min_discount=0 zorla
            categories = list(HAKMAREXPRESS_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_hakmarexpress_deals(
                        PLATFORM_FILES["hakmarexpress"],
                        category=cat,
                        min_discount=0,
                        category_url=HAKMAREXPRESS_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "macrocenter":
            # Macrocenter: discount badge yok, Money kart loyalty fiyatı → min_discount=0
            categories = list(MACROCENTER_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_macrocenter_deals(
                        PLATFORM_FILES["macrocenter"],
                        category=cat,
                        min_discount=0,
                        category_url=MACROCENTER_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "bizimtoptan":
            # Bizim Toptan: toptan, sadece bulk-discount → min_discount=0 ile geniş kapsama
            categories = list(BIZIMTOPTAN_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_bizimtoptan_deals(
                        PLATFORM_FILES["bizimtoptan"],
                        category=cat,
                        min_discount=0,
                        category_url=BIZIMTOPTAN_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "peynircibaba":
            # Peynirci Baba: gerçek %X indirim göstergesi var, normal min_discount uygulanır
            categories = list(PEYNIRCIBABA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_peynircibaba_deals(
                        PLATFORM_FILES["peynircibaba"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=PEYNIRCIBABA_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "burgerking":
            # Burger King: kampanya — fiyat-bazlı değil, discount_percentage=0
            categories = list(BURGERKING_CATEGORY_URLS.keys())
            await asyncio.gather(*[
                scrape_burgerking_deals(
                    PLATFORM_FILES["burgerking"],
                    category=cat,
                    min_discount=0,
                    category_url=BURGERKING_CATEGORY_URLS[cat],
                )
                for cat in categories
            ], return_exceptions=True)
        elif platform == "mcdonalds":
            categories = list(MCDONALDS_CATEGORY_URLS.keys())
            await asyncio.gather(*[
                scrape_mcdonalds_deals(
                    PLATFORM_FILES["mcdonalds"],
                    category=cat,
                    min_discount=0,
                    category_url=MCDONALDS_CATEGORY_URLS[cat],
                )
                for cat in categories
            ], return_exceptions=True)
        elif platform == "vodafone":
            # Vodafone: scraper kendi LIST + SUB_PAGES zincirler
            # (category_url verilmezse default LIST'i kullanır).
            await scrape_vodafone_deals(
                PLATFORM_FILES["vodafone"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
            )
        elif platform == "turkcell":
            # Turkcell: ana /kampanyalar sayfası sadece kategori linkleri içeriyor;
            # gerçek kartlar SUB_PAGES'te. category_url geçmiyoruz ki scraper
            # kendi SUB_PAGES'i iterate etsin.
            await scrape_turkcell_deals(
                PLATFORM_FILES["turkcell"],
                category="kampanya",
                min_discount=0,
                max_pages=5,
            )
        elif platform == "turktelekom":
            # Türk Telekom: scraper category_url verilmeyince max_pages>=2 ile
            # hem mobil hem evde-internet sayfasını çekiyor.
            await scrape_turktelekom_deals(
                PLATFORM_FILES["turktelekom"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
            )
        elif platform == "maximum":
            await scrape_maximum_deals(
                PLATFORM_FILES["maximum"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
                category_url=MAXIMUM_CATEGORY_URLS["kampanya"],
            )
        elif platform == "bonus":
            await scrape_bonus_deals(
                PLATFORM_FILES["bonus"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
                category_url=BONUS_CATEGORY_URLS["kampanya"],
            )
        elif platform == "world":
            # World = YapıKredi hub: scraper bireysel + KOBİ alt sayfalarını
            # kendi dolaşıyor; category_url geçmiyoruz.
            await scrape_world_deals(
                PLATFORM_FILES["world"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
            )
        elif platform == "axess":
            await scrape_axess_deals(
                PLATFORM_FILES["axess"],
                category="kampanya",
                min_discount=0,
                max_pages=2,
                category_url=AXESS_CATEGORY_URLS["kampanya"],
            )
        elif platform == "lcwaikiki":
            categories = list(LCWAIKIKI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_lcwaikiki_deals(
                        PLATFORM_FILES["lcwaikiki"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=LCWAIKIKI_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "koton":
            categories = list(KOTON_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_koton_deals(
                        PLATFORM_FILES["koton"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=KOTON_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "mavi":
            categories = list(MAVI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_mavi_deals(
                        PLATFORM_FILES["mavi"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=MAVI_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "boyner":
            categories = list(BOYNER_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_boyner_deals(
                        PLATFORM_FILES["boyner"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=BOYNER_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "penti":
            categories = list(PENTI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_penti_deals(
                        PLATFORM_FILES["penti"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=PENTI_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "watsons":
            categories = list(WATSONS_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_watsons_deals(
                        PLATFORM_FILES["watsons"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=WATSONS_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "dr":
            categories = list(DR_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_dr_deals(
                        PLATFORM_FILES["dr"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=DR_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "karaca":
            categories = list(KARACA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_karaca_deals(
                        PLATFORM_FILES["karaca"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=KARACA_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "englishhome":
            categories = list(ENGLISHHOME_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_englishhome_deals(
                        PLATFORM_FILES["englishhome"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=ENGLISHHOME_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "idefix":
            categories = list(IDEFIX_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_idefix_deals(
                        PLATFORM_FILES["idefix"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=IDEFIX_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "tchibo":
            categories = list(TCHIBO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_tchibo_deals(
                        PLATFORM_FILES["tchibo"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=TCHIBO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "mudo":
            categories = list(MUDO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_mudo_deals(
                        PLATFORM_FILES["mudo"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=MUDO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "madamecoco":
            categories = list(MADAMECOCO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_madamecoco_deals(
                        PLATFORM_FILES["madamecoco"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=MADAMECOCO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "vivense":
            categories = list(VIVENSE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_vivense_deals(
                        PLATFORM_FILES["vivense"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=VIVENSE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "tepehome":
            categories = list(TEPEHOME_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_tepehome_deals(
                        PLATFORM_FILES["tepehome"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=TEPEHOME_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "skechers":
            categories = list(SKECHERS_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_skechers_deals(
                        PLATFORM_FILES["skechers"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=SKECHERS_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "toyzz":
            categories = list(TOYZZ_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_toyzz_deals(
                        PLATFORM_FILES["toyzz"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=TOYZZ_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "yargici":
            categories = list(YARGICI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_yargici_deals(
                        PLATFORM_FILES["yargici"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=YARGICI_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "kitapyurdu":
            categories = list(KITAPYURDU_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_kitapyurdu_deals(
                        PLATFORM_FILES["kitapyurdu"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=KITAPYURDU_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "pttavm":
            categories = list(PTTAVM_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_pttavm_deals(
                        PLATFORM_FILES["pttavm"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=PTTAVM_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "sportive":
            categories = list(SPORTIVE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_sportive_deals(
                        PLATFORM_FILES["sportive"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=SPORTIVE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "newbalance":
            categories = list(NEWBALANCE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_newbalance_deals(
                        PLATFORM_FILES["newbalance"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=NEWBALANCE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "flo":
            categories = list(FLO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_flo_deals(
                        PLATFORM_FILES["flo"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=FLO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "hummel":
            categories = list(HUMMEL_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_hummel_deals(
                        PLATFORM_FILES["hummel"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=HUMMEL_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "evidea":
            categories = list(EVIDEA_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_evidea_deals(
                        PLATFORM_FILES["evidea"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=EVIDEA_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "beko":
            categories = list(BEKO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_beko_deals(
                        PLATFORM_FILES["beko"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=BEKO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "arcelik":
            categories = list(ARCELIK_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_arcelik_deals(
                        PLATFORM_FILES["arcelik"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=ARCELIK_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "vestel":
            categories = list(VESTEL_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_vestel_deals(
                        PLATFORM_FILES["vestel"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=VESTEL_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "network":
            categories = list(NETWORK_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_network_deals(
                        PLATFORM_FILES["network"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=NETWORK_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "northface":
            categories = list(NORTHFACE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_northface_deals(
                        PLATFORM_FILES["northface"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=NORTHFACE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "mac":
            categories = list(MAC_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_mac_deals(
                        PLATFORM_FILES["mac"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=MAC_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "apple":
            categories = list(APPLE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_apple_deals(
                        PLATFORM_FILES["apple"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=APPLE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "saatvesaat":
            categories = list(SAATVESAAT_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_saatvesaat_deals(
                        PLATFORM_FILES["saatvesaat"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=SAATVESAAT_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "altinbas":
            categories = list(ALTINBAS_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_altinbas_deals(
                        PLATFORM_FILES["altinbas"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=ALTINBAS_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "pasabahce":
            categories = list(PASABAHCE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_pasabahce_deals(
                        PLATFORM_FILES["pasabahce"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=PASABAHCE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "akakce":
            categories = list(AKAKCE_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_akakce_deals(
                        PLATFORM_FILES["akakce"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=AKAKCE_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "ramsey":
            categories = list(RAMSEY_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_ramsey_deals(
                        PLATFORM_FILES["ramsey"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=RAMSEY_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "atasay":
            categories = list(ATASAY_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_atasay_deals(
                        PLATFORM_FILES["atasay"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=ATASAY_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "reebok":
            categories = list(REEBOK_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_reebok_deals(
                        PLATFORM_FILES["reebok"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=REEBOK_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "sarar":
            categories = list(SARAR_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_sarar_deals(
                        PLATFORM_FILES["sarar"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=SARAR_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "huawei":
            categories = list(HUAWEI_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_huawei_deals(
                        PLATFORM_FILES["huawei"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=HUAWEI_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "lego":
            categories = list(LEGO_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_lego_deals(
                        PLATFORM_FILES["lego"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=LEGO_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "casper":
            categories = list(CASPER_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_casper_deals(
                        PLATFORM_FILES["casper"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=CASPER_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform == "monster":
            categories = list(MONSTER_CATEGORY_URLS.keys())
            for index in range(0, len(categories), CONCURRENT_SCRAPES):
                batch = categories[index:index + CONCURRENT_SCRAPES]
                await asyncio.gather(*[
                    scrape_monster_deals(
                        PLATFORM_FILES["monster"],
                        category=cat,
                        min_discount=min_discount,
                        category_url=MONSTER_CATEGORY_URLS[cat],
                    )
                    for cat in batch
                ], return_exceptions=True)
        elif platform in MARKETFIYATI_PLATFORMS:
            # Tek API call ile 7 market — diğer 6'sının statüsünü de güncelle
            out_files = {mk: PLATFORM_FILES[mk] for mk in MF_KEYS}
            for cat, kws in MARKETFIYATI_CATEGORIES.items():
                try:
                    await scrape_marketfiyati_all(out_files, category=cat, keywords=kws, min_discount=min_discount)
                except Exception as e:
                    print(f"[MarketFiyati] {cat} hata: {e}", flush=True)

        SCRAPE_ALL_STATUS[platform] = {
            "status": "completed",
            "message": f"{platform.capitalize()} taraması tamamlandı.",
            "current_category": None,
            "updated_at": datetime.now().isoformat()
        }

        db_gen = get_db()
        db = next(db_gen)
        try:
            if platform in MARKETFIYATI_PLATFORMS:
                # 7 marketin hepsini DB'ye senkronize et + status'larını "completed" yap
                for mk in MF_KEYS:
                    try:
                        sync_json_to_db(mk, db)
                    except Exception as e:
                        print(f"[SYNC] {mk} hata: {e}", flush=True)
                    if mk != platform:
                        SCRAPE_ALL_STATUS[mk] = {
                            "status": "completed",
                            "message": "MarketFiyati taramasıyla güncellendi.",
                            "current_category": None,
                            "updated_at": datetime.now().isoformat(),
                        }
            else:
                sync_json_to_db(platform, db)
        finally:
            db.close()

    except Exception as e:
        SCRAPE_ALL_STATUS[platform] = {
            "status": "error",
            "message": str(e),
            "current_category": None,
            "updated_at": datetime.now().isoformat()
        }
    print(f"[DEBUG] Platform taraması tamamlandı: {platform}", flush=True)


async def run_scrape_all_job(min_discount: int, platform: str = "all"):
    from app.services.admin_settings import enabled_stores
    if platform == "all":
        enabled = set(enabled_stores())
        all_platforms = [
            "amazon","trendyol","n11","hepsiburada","pazarama","ciceksepeti",
            "vatan","teknosa","decathlon","steam","defacto","mediamarkt","gratis",
            "a101","bim","sok","migros","carrefoursa","tarimkredi",
            "hakmarexpress","macrocenter","bizimtoptan","peynircibaba",
            "burgerking","mcdonalds","vodafone","turkcell","turktelekom",
            "maximum","bonus","world","axess",
            "lcwaikiki","koton","mavi",
            "boyner","penti","watsons","dr",
            "karaca","englishhome","idefix","tchibo",
            "mudo","madamecoco","vivense",
            "tepehome","skechers",
            "toyzz","yargici","kitapyurdu",
            "pttavm","sportive","newbalance",
            "flo","hummel","evidea",
            "beko","arcelik","vestel",
            "network","northface",
            "mac","apple",
            "saatvesaat","altinbas","pasabahce",
            "akakce","ramsey","atasay","reebok","sarar","huawei","lego","casper","monster",
        ]
        tasks = []
        # marketfiyati platformları içinde herhangi biri açıksa tek bir tarama yeter
        marketfiyati_done = False
        for p in all_platforms:
            if p not in enabled:
                continue
            if p in MARKETFIYATI_PLATFORMS:
                if marketfiyati_done:
                    continue
                marketfiyati_done = True
            md = max(min_discount, 10) if p == "steam" else min_discount
            tasks.append(run_platform_scrape(p, md))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    else:
        await run_platform_scrape(platform, min_discount)


@router.post("/scrape-all", dependencies=[Depends(require_api_key)])
def scrape_all(background_tasks: BackgroundTasks, platform: str = Query("all"), min_discount: int = Query(5)):
    if platform == "all":
        if any(v.get("status") == "running" for k, v in SCRAPE_ALL_STATUS.items() if k != "hepsiburada"):
            raise HTTPException(status_code=409, detail="Bir tarama zaten çalışıyor.")
    else:
        if SCRAPE_ALL_STATUS.get(platform, {}).get("status") == "running":
            raise HTTPException(status_code=409, detail=f"{platform} taraması zaten çalışıyor.")

    background_tasks.add_task(run_scrape_all_job, min_discount, platform)
    return {"status": "success", "message": f"{platform} taraması arka planda başlatıldı."}


@router.get("/scrape-all-status")
def get_scrape_all_status():
    agg = _aggregate_status()
    data = {**agg, **SCRAPE_ALL_STATUS}
    return {"status": "success", "data": data}


@router.get("/scrape-status")
def get_scrape_status(category: str = Query("gida")):
    SCRAPE_STATUS: dict = {}
    category = category.lower()
    return {
        "status": "success",
        "data": SCRAPE_STATUS.get(category, {
            "status": "idle",
            "message": f"{category.capitalize()} için aktif tarama yok.",
            "updated_at": None,
        })
    }
