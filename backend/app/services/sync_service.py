import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.database import save_deal_to_db

PLATFORM_FILES = {
    "amazon": "data/deals.json",
    "trendyol": "data/deals_trendyol.json",
    "n11": "data/deals_n11.json",
    "hepsiburada": "data/deals_hepsiburada.json",
    "pazarama": "data/deals_pazarama.json",
    "ciceksepeti": "data/deals_ciceksepeti.json",
    "vatan": "data/deals_vatan.json",
    "teknosa": "data/deals_teknosa.json",
    "decathlon": "data/deals_decathlon.json",
    "steam": "data/deals_steam.json",
    "defacto": "data/deals_defacto.json",
    "mediamarkt": "data/deals_mediamarkt.json",
    "gratis": "data/deals_gratis.json",
    "a101": "data/deals_a101.json",
    "bim": "data/deals_bim.json",
    "sok": "data/deals_sok.json",
    "migros": "data/deals_migros.json",
    "carrefoursa": "data/deals_carrefoursa.json",
    "tarimkredi": "data/deals_tarimkredi.json",
    "hakmarexpress": "data/deals_hakmarexpress.json",
    "macrocenter": "data/deals_macrocenter.json",
    "bizimtoptan": "data/deals_bizimtoptan.json",
    "peynircibaba": "data/deals_peynircibaba.json",
    "burgerking": "data/deals_burgerking.json",
    "mcdonalds": "data/deals_mcdonalds.json",
    "vodafone": "data/deals_vodafone.json",
    "turkcell": "data/deals_turkcell.json",
    "turktelekom": "data/deals_turktelekom.json",
    "lcwaikiki": "data/deals_lcwaikiki.json",
    "koton": "data/deals_koton.json",
    "mavi": "data/deals_mavi.json",
    "boyner": "data/deals_boyner.json",
    "penti": "data/deals_penti.json",
    "watsons": "data/deals_watsons.json",
    "dr": "data/deals_dr.json",
    "karaca": "data/deals_karaca.json",
    "englishhome": "data/deals_englishhome.json",
    "idefix": "data/deals_idefix.json",
    "tchibo": "data/deals_tchibo.json",
    "mudo": "data/deals_mudo.json",
    "madamecoco": "data/deals_madamecoco.json",
    "vivense": "data/deals_vivense.json",
    "tepehome": "data/deals_tepehome.json",
    "skechers": "data/deals_skechers.json",
    "toyzz": "data/deals_toyzz.json",
    "yargici": "data/deals_yargici.json",
    "kitapyurdu": "data/deals_kitapyurdu.json",
    "pttavm": "data/deals_pttavm.json",
    "sportive": "data/deals_sportive.json",
    "newbalance": "data/deals_newbalance.json",
    "flo": "data/deals_flo.json",
    "hummel": "data/deals_hummel.json",
    "evidea": "data/deals_evidea.json",
    "beko": "data/deals_beko.json",
    "arcelik": "data/deals_arcelik.json",
    "vestel": "data/deals_vestel.json",
    "network": "data/deals_network.json",
    "northface": "data/deals_northface.json",
    "mac": "data/deals_mac.json",
    "apple": "data/deals_apple.json",
    "saatvesaat": "data/deals_saatvesaat.json",
    "altinbas": "data/deals_altinbas.json",
    "pasabahce": "data/deals_pasabahce.json",
    "akakce": "data/deals_akakce.json",
    "ramsey": "data/deals_ramsey.json",
    "atasay": "data/deals_atasay.json",
    "reebok": "data/deals_reebok.json",
    "sarar": "data/deals_sarar.json",
    "huawei": "data/deals_huawei.json",
    "lego": "data/deals_lego.json",
    "casper": "data/deals_casper.json",
    "monster": "data/deals_monster.json",
}


def _resolve(path: str) -> str:
    if os.path.isabs(path):
        return path
    if Path(path).exists():
        return path
    docker_path = f"/app/{path}"
    if Path(docker_path).exists():
        return docker_path
    return path


def sync_json_to_db(platform: str, db: Session):
    file_path = PLATFORM_FILES.get(platform)
    if not file_path:
        print(f"[SYNC] Bilinmeyen platform: {platform}", flush=True)
        return

    resolved = _resolve(file_path)
    if not Path(resolved).exists():
        print(f"[SYNC] {platform} için JSON dosyası bulunamadı: {resolved}", flush=True)
        return

    try:
        with open(resolved, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict) and 'deals' in data:
            deals = data['deals']
        elif isinstance(data, list):
            deals = data
        else:
            print(f"[SYNC] {platform} JSON formatı geçersiz", flush=True)
            return

        unique_deals: dict[str, dict] = {}
        for deal in deals:
            link = deal.get('link')
            if link:
                unique_deals[link] = deal

        synced_count = 0
        failed = 0
        for link, deal in unique_deals.items():
            try:
                if save_deal_to_db(deal, platform, db, commit=False) is not None:
                    synced_count += 1
            except Exception as e:
                failed += 1
                print(f"[SYNC] Deal hatası ({platform}): {e}", flush=True)
                db.rollback()

        try:
            db.commit()
        except Exception as e:
            print(f"[SYNC] Toplu commit hatası ({platform}): {e}", flush=True)
            db.rollback()

        print(f"[SYNC] {platform}: {synced_count} deal senkronize ({failed} hatalı)", flush=True)

    except Exception as e:
        print(f"[SYNC] {platform} senkronizasyon hatası: {e}", flush=True)


def cleanup_json_duplicates(platform: str) -> int:
    file_path = PLATFORM_FILES.get(platform)
    if not file_path:
        return 0

    resolved = _resolve(file_path)
    if not Path(resolved).exists():
        print(f"[JSON_CLEANUP] {platform} için JSON dosyası bulunamadı: {resolved}", flush=True)
        return 0

    try:
        with open(resolved, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict) and 'deals' in data:
            deals = data['deals']
        elif isinstance(data, list):
            deals = data
        else:
            print(f"[JSON_CLEANUP] {platform} JSON formatı geçersiz", flush=True)
            return 0

        seen_links: dict[str, dict] = {}
        for deal in deals:
            link = deal.get('link', '')
            if link:
                seen_links[link] = deal

        unique_deals = list(seen_links.values())
        removed_count = len(deals) - len(unique_deals)

        with open(resolved, 'w', encoding='utf-8') as f:
            json.dump(unique_deals, f, ensure_ascii=False, indent=2)

        print(f"[JSON_CLEANUP] {platform}: {removed_count} duplicate silindi, {len(unique_deals)} kaldı", flush=True)
        return removed_count

    except Exception as e:
        print(f"[JSON_CLEANUP] {platform} temizleme hatası: {e}", flush=True)
        return 0
