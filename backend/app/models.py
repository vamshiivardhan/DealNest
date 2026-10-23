from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)   # e.g., "BigBasket", "JioMart"
    base_url = Column(Text, nullable=True)

    # Relationships
    listings = relationship("StoreListing", back_populates="platform", cascade="all, delete-orphan")


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True, index=True)
    brand = Column(String(100), nullable=True)
    image_url = Column(Text, nullable=True)

    # Relationships
    listings = relationship("StoreListing", back_populates="canonical_product")


class StoreListing(Base):
    __tablename__ = "store_listings"

    id = Column(Integer, primary_key=True, index=True)
    canonical_product_id = Column(Integer, ForeignKey("canonical_products.id"), nullable=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    platform_uid = Column(String(255), nullable=False, index=True)
    raw_title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    current_mrp = Column(Float, nullable=True)
    current_selling_price = Column(Float, nullable=False)
    in_stock = Column(Boolean, default=True)
    
    # Map the new location column
    location = Column(String(100), default="GUDIMALKAPUR", index=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    platform = relationship("Platform", back_populates="listings")
    canonical_product = relationship("CanonicalProduct", back_populates="listings")
    price_history = relationship("PriceHistory", back_populates="listing", cascade="all, delete-orphan")



class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    store_listing_id = Column(Integer, ForeignKey("store_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    selling_price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=True)
    in_stock = Column(Boolean, default=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    listing = relationship("StoreListing", back_populates="price_history")
