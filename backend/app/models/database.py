from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    price = Column(String)
    discount_percentage = Column(Integer)
    link = Column(String, unique=True, index=True)
    image = Column(String)
    category = Column(String, index=True)
    platform = Column(String, index=True)
    source = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow, index=True)
    price_history = Column(JSON, default=list)
    deal_score = Column(Float, default=0.0)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def cleanup_duplicates(db: Session):
    try:
        from sqlalchemy import func

        duplicates = db.query(Deal.link, func.count(Deal.id).label('count')).group_by(Deal.link).having(func.count(Deal.id) > 1).all()

        deleted_count = 0
        for link, _count in duplicates:
            deals = db.query(Deal).filter(Deal.link == link).order_by(Deal.last_updated.desc()).all()
            for deal in deals[1:]:
                db.delete(deal)
                deleted_count += 1

        db.commit()
        print(f"[CLEANUP] {deleted_count} duplicate deal silindi", flush=True)
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"[CLEANUP] Hata: {e}", flush=True)
        return 0


def _parse_price(value: str) -> float:
    if not value:
        return 0.0
    import re
    m = re.search(r"\d{1,3}(?:[. ]\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2}|\d+", value)
    if not m:
        return 0.0
    raw = m.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _compute_deal_score(price: str, discount: int, price_history: list) -> float:
    discount = max(0, min(int(discount or 0), 100))
    score = float(discount)

    cur = _parse_price(price)
    if price_history and cur > 0:
        old_prices = []
        for entry in price_history[-10:]:
            v = _parse_price(entry.get("price", ""))
            if v > 0:
                old_prices.append(v)
        if old_prices:
            peak = max(old_prices)
            if peak > cur:
                drop_pct = ((peak - cur) / peak) * 100
                score = max(score, drop_pct)
                if drop_pct > discount + 5:
                    score += 10

    return round(min(score, 100.0), 2)


def _build_price_history_entry(price: str, discount: int) -> dict:
    return {
        "date": datetime.utcnow().isoformat(),
        "price": price,
        "discount_percentage": discount,
    }


def save_deal_to_db(deal: dict, platform: str, db: Session, commit: bool = True):
    """Upsert deal. Set commit=False to batch multiple inserts in one transaction."""
    try:
        link = deal.get("link")
        if not link:
            return None

        existing = db.query(Deal).filter(Deal.link == link).first()
        new_price = deal.get("price", "")
        new_discount = int(deal.get("discount_percentage") or 0)

        if existing:
            if existing.price == new_price:
                existing.discount_percentage = new_discount or existing.discount_percentage
                existing.deal_score = _compute_deal_score(existing.price, existing.discount_percentage, existing.price_history or [])
                if commit:
                    db.commit()
                return existing

            existing.title = deal.get("title", existing.title)
            existing.price = new_price
            existing.discount_percentage = new_discount
            existing.image = deal.get("image", existing.image)
            existing.category = deal.get("category", existing.category)
            existing.last_updated = datetime.utcnow()

            price_history = list(existing.price_history or [])
            price_history.append(_build_price_history_entry(new_price, new_discount))
            existing.price_history = price_history
            existing.deal_score = _compute_deal_score(new_price, new_discount, price_history)

            if commit:
                db.commit()
                db.refresh(existing)
            return existing

        history = [_build_price_history_entry(new_price, new_discount)]
        new_deal = Deal(
            title=deal.get("title", ""),
            price=new_price,
            discount_percentage=new_discount,
            link=link,
            image=deal.get("image", ""),
            category=deal.get("category", ""),
            platform=platform,
            source=deal.get("source", ""),
            deal_score=_compute_deal_score(new_price, new_discount, history),
            price_history=history,
        )
        db.add(new_deal)
        if commit:
            db.commit()
            db.refresh(new_deal)
        return new_deal
    except Exception as e:
        if commit:
            db.rollback()
        print(f"[ERROR] Deal kaydedilemedi: {e}", flush=True)
        return None
