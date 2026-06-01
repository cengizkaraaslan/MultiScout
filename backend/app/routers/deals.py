from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db, Deal
from app.core.auth import require_api_key
from datetime import datetime

router = APIRouter()


# Üst kategori grupları — bilinen kategori slug'larını üst gruplara map'ler.
# Tarayıcılar (Amazon/Trendyol/N11/Marketler/Moda/Ev) ürettiği kategoriler hep
# burada yer almalı, aksi takdirde "Diğer" altına düşer.
_CATEGORY_GROUPS: dict[str, list[str]] = {
    "Elektronik": [
        "elektronik", "telefon", "bilgisayar", "notebook", "tablet", "tv",
        "televizyon", "kulaklik", "yazici", "klima", "buzdolabi",
        "camasir-makinesi", "bulasik-makinesi", "firin", "ankastre",
        "elektrikli-supurge", "kahve-makinesi", "kahve-makineleri",
        "beyaz-esya", "beyazesya", "kucuk-ev-aletleri", "oyun-konsol",
        "samsung-galaxy", "iphone", "macbook", "elektrik-supurge",
        "monitor", "gaming", "is-laptop", "ofis-laptop", "gaming-laptop",
        "rtx-4060", "rtx-4070", "i9", "intel-ultra",
        "nirvana", "nirvana-x", "excalibur", "via", "monoblock",
        "tulpar", "abra", "huma",
        "phones", "tablets", "laptops", "wearables", "audio", "monitors",
        "smart-screens", "smart-home", "accessories", "routers",
        "iphone", "ipad", "mac", "watch", "airpods", "homepod",
        "macbook-air", "macbook-pro", "imac",
    ],
    "Yiyecek & İçecek": [
        "gida", "temel-gida", "sut-kahvalti", "sut-kahvaltilik",
        "sut-urunleri-kahvaltilik", "et-tavuk", "et-tavuk-balik",
        "et-urunleri-ve-sarkuteri", "et-et-urunleri", "sarkuteri-kahvaltilik",
        "sebze-meyve", "meyve-sebze", "icecek", "icecekler", "atistirmalik",
        "sivi-yag-margarin", "dondurma", "kahve", "cekirdek-kahve",
        "filtre-kahve", "kapsul-kahve",
        # Peynirci Baba — kahvaltılık / şarküteri / kuru gıda detay slug'ları
        "indirimli-urunler", "beyaz-peynir", "kasar-peyniri", "ithal-peynirler",
        "kahvaltilik-soslar", "et-urunleri", "kavurma", "fume-et",
        "gunluk-sut", "ayran", "bal", "helva", "findik-fistik-ezmesi",
        "cay", "baharat", "bakliyat", "eriste", "ekmek",
        "hazir-tatlilar", "dilimli-zeytinler", "gurme-urunler",
    ],
    "Temizlik & Bakım": [
        "temizlik", "hijyen", "hijyen-bakim", "hijyen-bebek",
    ],
    "Kişisel Bakım & Kozmetik": [
        "kisisel-bakim", "makyaj", "ruj", "maskara", "fondoten", "far", "oje",
        "cilt-bakim", "yuz-kremi", "gunes-kremi", "serum", "sac-bakim",
        "sampuan", "sac-boyama", "erkek-bakim", "tras-kremi", "el-kremi",
        "vucut-losyon", "deodorant", "parfum", "kadin-parfum", "erkek-parfum",
        "unisex-parfum", "kozmetik", "vitamin", "elektrikli", "cilt-bakimi",
        "mini", "setler", "dudak", "yuz", "goz",
    ],
    "Kitap & Hobi": [
        "kitap", "egitim-kitaplari", "cocuk-kitaplari", "cocuk-kitabi",
        "yabanci-dilde", "yabanci-dil", "edebiyat", "cok-satan",
        "kisisel-gelisim", "egitim-sinav", "tarih", "felsefe", "akademik",
        "bilim-arastirma", "muzik-cd", "muzik-film", "kirtasiye",
    ],
    "Oyuncak & Bebek": [
        "oyuncak", "bebek", "bebek-oyuncak", "erkek-cocuk", "kiz-cocuk",
        "egitici", "hot-wheels", "fisher-price", "barbie", "puzzle",
        "anne-bebek", "bebek-urunleri", "bebek-tekstili", "bebek-kiyafet",
        "bebek-cocuk", "hobi-oyuncak", "lego", "themes", "technic", "city",
        "star-wars", "harry-potter", "friends", "ninjago", "duplo",
        "creator", "categories",
    ],
    "Spor & Outdoor": [
        "spor", "kosu", "bisiklet", "kamp", "yoga", "krampon",
        "spor-ayakkabi", "kadin-spor-ayakkabi", "erkek-spor-ayakkabi",
        "esofman", "milli-takim", "574", "lifestyle", "bahce-balkon",
    ],
    "Moda — Kadın": [
        "kadin", "kadin-elbise", "kadin-pantolon", "kadin-bluz",
        "kadin-tisort", "kadin-mont", "kadin-etek", "kadin-kot-pantolon",
        "kadin-ic-giyim", "kadin-outlet", "kadin-ayakkabi", "kadin-canta",
        "kadin-dis-giyim", "kadin-ust-giyim", "kadin-alt-giyim",
        "kadin-aksesuar", "kadin-yaz", "kadin-saat", "kadin-giyim",
        "elbise", "outlet-kadin",
    ],
    "Moda — Erkek": [
        "erkek", "erkek-tisort", "erkek-pantolon", "erkek-gomlek",
        "erkek-mont", "erkek-sweat", "erkek-sweatshirt", "erkek-kot-pantolon",
        "erkek-outlet", "erkek-ayakkabi", "erkek-dis-giyim", "erkek-ust-giyim",
        "erkek-alt-giyim", "erkek-aksesuar", "erkek-saat", "erkek-giyim",
        "outlet-erkek", "takim-elbise", "ceket", "gomlek", "pantolon",
        "polo", "sweat", "tisort",
    ],
    "Moda — Çocuk": [
        "cocuk", "cocuk-kiyafet", "cocuk-saat", "cocuk-ayakkabi",
    ],
    "Moda — İç Giyim": [
        "ic-giyim", "sutyen", "kulot", "pijama", "gecelik", "corap",
        "mayo", "bikini", "tayt", "spor-sutyen",
    ],
    "Ayakkabı": [
        "ayakkabi", "bot", "sandalet", "terlik",
    ],
    "Ev & Yaşam": [
        "ev", "ev-yasam", "ev-tekstili", "ev-aksesuar", "dekorasyon",
        "yatak-odasi", "banyo", "mutfak", "sofra", "hali-kilim", "hali",
        "kilim", "perde", "yastik", "yorgan", "nevresim", "yatak-ortusu",
        "yorgan", "havlu", "mutfak-tekstili", "masa-ortusu", "yatak",
        "yemek-odasi", "yemek-masasi", "yemek-takimlari", "kahvalti-takimi",
        "tencere-takimlari", "tencere-seti", "tava", "su-bardagi",
        "cay-bardagi", "cay", "tabak", "vazo", "kase", "ceyiz",
        "oturma-grubu", "tv-unitesi", "aydinlatma", "koltuk", "kanepe",
        "sandalye", "gardrop", "calisma-masasi", "berjer", "mobilya",
        "kampanyali", "yeni-urunler", "indirim", "indirimli",
        "tekstil", "yatak-tekstil", "catal-kasik-bicak",
    ],
    "Saat & Aksesuar": [
        "saat", "akilli-saat", "klasik-saat", "spor-saat",
        "casio", "guess", "fossil", "michael-kors", "aksesuar",
    ],
    "Mücevher": [
        "kolye", "yuzuk", "kupe", "bilezik", "bileklik", "altin",
        "pirlanta", "zincir",
    ],
    "Çiçek & Hediye": [
        "cicek", "hediye", "hediyelik",
    ],
    "Ofis & Kırtasiye": [
        "ofis", "ofis-kirtasiye",
    ],
    "Oyun": [
        "oyun", "oyun-konsol",
    ],
}


def _build_category_tree(categories: list[str]) -> dict:
    tree: dict = {}
    seen: set[str] = set()
    for top, items in _CATEGORY_GROUPS.items():
        members = [c for c in items if c in categories]
        if members:
            tree[top] = members
            seen.update(members)
    extras = [c for c in categories if c not in seen]
    if extras:
        tree["Diğer"] = extras
    return tree


def _categories_for_platform(db: Session, platform: str | None) -> list[str]:
    """Veritabanından platforma göre distinct kategori listesi döner.
    platform=None veya 'hepsi' → tüm platformlardaki kategoriler birleşimi.
    Boş dönerse statik tarayıcı config'inden fallback."""
    from app.services.admin_settings import enabled_stores

    query = db.query(Deal.category).distinct()
    if platform and platform.lower() != "hepsi":
        query = query.filter(Deal.platform == platform.lower())
    else:
        en = enabled_stores()
        if en:
            query = query.filter(Deal.platform.in_(en))

    cats = [c[0] for c in query.all() if c[0]]
    cats = sorted(set(cats))
    if cats:
        return cats

    # DB boşsa scraper config'ten fallback (henüz hiç scrape yapılmamış olabilir)
    return _fallback_categories_for(platform)


_MARKETFIYATI_PLATFORMS = {"a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi"}


def _fallback_categories_for(platform: str | None) -> list[str]:
    """Scraper config map'lerinden statik kategori listesi."""
    p = (platform or "").lower()
    if p in _MARKETFIYATI_PLATFORMS:
        try:
            from app.core.category_mapping import MARKETFIYATI_CATEGORIES
            return list(MARKETFIYATI_CATEGORIES.keys())
        except Exception:
            return []
    # platform key'ine göre <KEY>_CATEGORY_URLS aramayı dene
    if p and p != "hepsi":
        try:
            from app.core import category_mapping as cm
            attr_name = f"{p.upper().replace('-', '_')}_CATEGORY_URLS"
            mapping = getattr(cm, attr_name, None)
            if isinstance(mapping, dict):
                return list(mapping.keys())
        except Exception:
            pass
    # hepsi veya bilinmeyen platform → union of all config maps
    try:
        from app.core import category_mapping as cm
        union: set[str] = set()
        for name in dir(cm):
            if name.endswith("_CATEGORY_URLS") or name == "MARKETFIYATI_CATEGORIES":
                v = getattr(cm, name, None)
                if isinstance(v, dict):
                    union.update(v.keys())
        return sorted(union)
    except Exception:
        return []


@router.get("/categories")
def get_categories(platform: str | None = Query(None), db: Session = Depends(get_db)):
    return {"status": "success", "categories": _categories_for_platform(db, platform)}


@router.get("/category-tree")
def get_category_tree(platform: str | None = Query(None), db: Session = Depends(get_db)):
    cats = _categories_for_platform(db, platform)
    return {"status": "success", "data": _build_category_tree(cats), "categories": cats}


@router.get("/category-counts")
def get_category_counts(platform: str | None = Query(None), db: Session = Depends(get_db)):
    """Her kategori için ürün sayısı. Sidebar badge'leri ve toplam göstergesi için."""
    from sqlalchemy import func
    from app.services.admin_settings import enabled_stores

    q = db.query(Deal.category, func.count(Deal.id))
    if platform and platform.lower() != "hepsi":
        q = q.filter(Deal.platform == platform.lower())
    else:
        en = enabled_stores()
        if en:
            q = q.filter(Deal.platform.in_(en))

    rows = q.group_by(Deal.category).all()
    counts = {c: n for c, n in rows if c}
    total = sum(counts.values())
    return {"status": "success", "data": counts, "total": total}


@router.get("/deals")
def get_deals(platform: str = Query("amazon"), category: str = Query(None), min_discount: int = Query(0), skip: int = Query(0), limit: int = Query(30), sort_by: str = Query("last_updated"), db: Session = Depends(get_db)):
    try:
        from sqlalchemy import func, cast, Float
        from app.services.admin_settings import enabled_stores

        query = db.query(Deal)
        enabled = enabled_stores()
        if platform.lower() == "hepsi":
            if enabled:
                query = query.filter(Deal.platform.in_(enabled))
        else:
            if platform.lower() not in enabled:
                return {"status": "success", "data": [], "total": 0, "message": f"{platform} mağazası admin tarafından devre dışı"}
            query = query.filter(Deal.platform == platform.lower())
        if category:
            query = query.filter(Deal.category == category.lower())
        if min_discount > 0:
            query = query.filter(Deal.discount_percentage >= min_discount)

        if sort_by == "price":
            price_numeric = cast(
                func.replace(
                    func.replace(
                        func.regexp_replace(Deal.price, r'[^\d,.]', '', 'g'),
                        '.',
                        ''
                    ),
                    ',',
                    '.'
                ),
                Float
            )
            query = query.order_by(price_numeric.asc())
        elif sort_by == "discount":
            query = query.order_by(Deal.discount_percentage.desc())
        else:
            query = query.order_by(Deal.last_updated.desc())

        total = query.count()
        deals = query.offset(skip).limit(limit).all()
        deals_list = [
            {
                "title": d.title,
                "price": d.price,
                "discount_percentage": d.discount_percentage,
                "link": d.link,
                "image": d.image,
                "category": d.category,
                "platform": d.platform,
                "source": d.source,
                "last_updated": d.last_updated.isoformat() if d.last_updated else None,
                "price_history": d.price_history or [],
                "deal_score": d.deal_score
            }
            for d in deals
        ]
        return {"status": "success", "data": deals_list, "total": total}
    except Exception as e:
        return {"status": "error", "message": str(e)}


CAMPAIGN_PLATFORMS = {
    "burgerking", "mcdonalds",
    "vodafone", "turkcell", "turktelekom",
    "maximum", "bonus", "world", "axess",
}

# BOGO başlıklarını yakala — "1 alana 1 bedava", "ikincisi bedava",
# "1+1 hediye", "2 al 1 öde" gibi varyasyonlar.
import re as _re
_BOGO_RE = _re.compile(
    r"(?:alana?|al)\s*\d+\s*bedava|"
    r"ikincisi\s+bedava|"
    r"\b[123]\s*\+\s*1\b|"
    r"\b\d+\s*al\s*\d+\s*[ödeöde]+|"
    r"hediye(?:li)?\b|"
    r"bedava\b",
    _re.IGNORECASE,
)


@router.get("/campaigns")
def get_campaigns(
    bogo_only: bool = Query(False),
    limit: int = Query(300),
    db: Session = Depends(get_db),
):
    """Kampanyalar sayfası kaynağı. İki kaynaktan beslenir:

    1. Kampanya-yönelimli platformlar (burgerking vb.) — tüm dealları
    2. Mevcut market scraperlarındaki ürünler — başlığında BOGO/hediye
       deseni geçenler (1 alana 1 bedava, ikincisi bedava, hediyeli, 2+1)

    bogo_only=true ise sadece BOGO/hediye deseni geçenler döner.
    """
    try:
        from app.services.admin_settings import enabled_stores
        enabled = set(enabled_stores())

        # 1) Kampanya-platformları
        campaign_q = db.query(Deal).filter(Deal.platform.in_(CAMPAIGN_PLATFORMS & enabled))
        campaign_rows = campaign_q.order_by(Deal.last_updated.desc()).limit(limit).all()

        # 2) Market dealları içinde BOGO başlık deseni
        market_platforms = {
            "a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi",
            "hakmarexpress", "macrocenter", "bizimtoptan", "peynircibaba",
        } & enabled
        bogo_rows: list[Deal] = []
        if market_platforms:
            q = db.query(Deal).filter(Deal.platform.in_(market_platforms))
            for r in q.order_by(Deal.last_updated.desc()).limit(800).all():
                title = (r.title or "")
                if _BOGO_RE.search(title):
                    bogo_rows.append(r)
                    if len(bogo_rows) >= limit:
                        break

        def _tag(r: Deal, kind: str) -> dict:
            return {
                "title": r.title,
                "price": r.price,
                "discount_percentage": r.discount_percentage,
                "link": r.link,
                "image": r.image,
                "category": r.category,
                "platform": r.platform,
                "campaign_kind": kind,
                "last_updated": r.last_updated.isoformat() if r.last_updated else None,
            }

        out: list[dict] = []
        if not bogo_only:
            out.extend(_tag(r, "kampanya") for r in campaign_rows)
        out.extend(_tag(r, "bogo") for r in bogo_rows)

        return {"status": "success", "data": out, "total": len(out)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/deals-cleanup-json", dependencies=[Depends(require_api_key)])
def cleanup_json_duplicates(platform: str = Query("all"), db: Session = Depends(get_db)):
    try:
        from app.services.sync_service import cleanup_json_duplicates, PLATFORM_FILES

        if platform == "all":
            total_removed = 0
            for plat in PLATFORM_FILES.keys():
                removed = cleanup_json_duplicates(plat)
                total_removed += removed
            return {"status": "success", "message": f"Toplam {total_removed} duplicate silindi."}
        else:
            removed = cleanup_json_duplicates(platform)
            return {"status": "success", "message": f"{removed} duplicate silindi."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/deals-reset-db", dependencies=[Depends(require_api_key)])
def reset_database(db: Session = Depends(get_db)):
    try:
        db.query(Deal).delete()
        db.commit()

        from app.services.sync_service import sync_json_to_db, PLATFORM_FILES

        for platform in PLATFORM_FILES.keys():
            sync_json_to_db(platform, db)

        total = db.query(Deal).count()
        return {"status": "success", "message": f"Veritabanı sıfırlandı. {total} ürün yüklendi."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/deals-cleanup-duplicates", dependencies=[Depends(require_api_key)])
def cleanup_db_duplicates(db: Session = Depends(get_db)):
    try:
        from app.models.database import cleanup_duplicates
        removed = cleanup_duplicates(db)
        return {"status": "success", "message": f"{removed} duplicate ürün silindi."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
