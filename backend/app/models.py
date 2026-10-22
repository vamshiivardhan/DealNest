from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base

class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "Amazon", "BigBasket"
    internal_code = Column(String, unique=True, nullable=False) # e.g., "AMAZON_TEZ_INDIA"
    
    # Relationships
    listings = relationship("StoreListing", back_populates="platform")


class CanonicalProduct(Base):
    """
    The master product entity. Multiple store listings will point here.
    """
    __tablename__ = "canonical_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)          # e.g., "Tata Salt Iodized"
    brand = Column(String, nullable=True)          # e.g., "Tata"
    category = Column(String, index=True)          # e.g., "foodgrains-oil-masala"
    base_quantity = Column(Float, nullable=True)   # e.g., 1000.0
    base_unit = Column(String, nullable=True)      # e.g., "g" or "ml"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    listings = relationship("StoreListing", back_populates="canonical_product")


class StoreListing(Base):
    """
    The specific URL and live price state on a given platform.
    """
    __tablename__ = "store_listings"

    id = Column(Integer, primary_key=True, index=True)
    canonical_product_id = Column(Integer, ForeignKey("canonical_products.id"), nullable=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    
    platform_uid = Column(String, index=True, nullable=False)  # ASIN or BB ID
    raw_title = Column(String, nullable=False)                 # Exact title from the store
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    
    # Live State (Updates on every scrape)
    current_mrp = Column(Float, nullable=True)
    current_selling_price = Column(Float, nullable=False)
    in_stock = Column(Boolean, default=True)
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ensure we don't have duplicate listings for the same platform UID
    __table_args__ = (UniqueConstraint('platform_id', 'platform_uid', name='uix_platform_uid'),)

    # Relationships
    platform = relationship("Platform", back_populates="listings")
    canonical_product = relationship("CanonicalProduct", back_populates="listings")
    price_history = relationship("PriceHistory", back_populates="listing", cascade="all, delete-orphan")


class PriceHistory(Base):
    """
    Time-series log of price changes for historical analytics.
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    store_listing_id = Column(Integer, ForeignKey("store_listings.id", ondelete="CASCADE"), nullable=False)
    
    selling_price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=True)
    in_stock = Column(Boolean, default=True)
    
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    listing = relationship("StoreListing", back_populates="price_history")
