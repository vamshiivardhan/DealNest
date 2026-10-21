"""SQLAlchemy ORM models for DealNest's initial database schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    """Canonical product identity independent of individual stores."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "quantity IS NULL OR quantity > 0", name="ck_products_quantity_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120))
    variant: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store_listings: Mapped[list[StoreListing]] = relationship(back_populates="product")


class Store(Base):
    """Shopping platform represented by DealNest."""

    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("name", name="uq_stores_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store_listings: Mapped[list[StoreListing]] = relationship(back_populates="store")


class StoreListing(Base):
    """Store-specific listing, optionally matched to a canonical product."""

    __tablename__ = "store_listings"
    __table_args__ = (
        UniqueConstraint(
            "store_id", "source_product_id", name="uq_listing_store_source_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    source_product_id: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    product_url: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    product: Mapped[Product | None] = relationship(back_populates="store_listings")
    store: Mapped[Store] = relationship(back_populates="store_listings")
    current_offers: Mapped[list[CurrentOffer]] = relationship(back_populates="listing")
    price_history: Mapped[list[PriceHistory]] = relationship(back_populates="listing")


class CurrentOffer(Base):
    """Latest known price for a listing in a delivery location."""

    __tablename__ = "current_offers"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "location_code", name="uq_current_offer_listing_location"
        ),
        CheckConstraint("selling_price >= 0", name="ck_current_offer_price_nonnegative"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="ck_current_offer_mrp_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("store_listings.id"), nullable=False)
    location_code: Mapped[str] = mapped_column(String(128), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    available: Mapped[bool | None] = mapped_column(Boolean)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    listing: Mapped[StoreListing] = relationship(back_populates="current_offers")


class PriceHistory(Base):
    """Historical price observations for a listing and delivery location."""

    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "location_code",
            "observed_at",
            name="uq_price_history_collection_cycle",
        ),
        CheckConstraint("selling_price >= 0", name="ck_price_history_price_nonnegative"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="ck_price_history_mrp_nonnegative"),
        Index(
            "ix_price_history_listing_location_time",
            "listing_id",
            "location_code",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("store_listings.id"), nullable=False)
    location_code: Mapped[str] = mapped_column(String(128), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    available: Mapped[bool | None] = mapped_column(Boolean)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    listing: Mapped[StoreListing] = relationship(back_populates="price_history")


__all__ = ["Product", "Store", "StoreListing", "CurrentOffer", "PriceHistory"]
