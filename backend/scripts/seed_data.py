import sys
import os
import json
from datetime import datetime, timedelta

# Add the backend directory to the Python path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Platform, CanonicalProduct, StoreListing, PriceHistory

def seed_bigbasket_data():
    db = SessionLocal()
    
    # 1. Ensure the BigBasket Platform exists
    platform = db.query(Platform).filter(Platform.internal_code == "BIGBASKET_PAN_INDIA").first()
    if not platform:
        platform = Platform(name="BigBasket", internal_code="BIGBASKET_PAN_INDIA")
        db.add(platform)
        db.commit()
        db.refresh(platform)

    # 2. Load the JSON data
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "data-bb.json")
    
    if not os.path.exists(data_path):
        print(f"Error: Could not find data file at {data_path}")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    print(f"Loaded {len(items)} items from data-bb.json. Starting ingestion...")

    new_listings = 0
    updated_listings = 0

    for item in items:
        # Extract fields safely
        uid = str(item.get("uid"))
        name = item.get("name", "Unknown Product")
        brand = item.get("brand", "Unknown Brand")
        category = item.get("category", "Uncategorized")
        new_price = float(item.get("new_price", 0.0))
        old_price = float(item.get("old_price", 0.0))
        url = item.get("url", "")
        image_url = item.get("image", "")
        in_stock = True if item.get("stock") == "In Stock" else False

        # 3. Upsert Canonical Product
        # (For MVP, matching simply by name and brand. Phase 4 will use fuzzy/AI matching)
        canonical = db.query(CanonicalProduct).filter(
            CanonicalProduct.name == name,
            CanonicalProduct.brand == brand
        ).first()

        if not canonical:
            canonical = CanonicalProduct(
                name=name,
                brand=brand,
                category=category
            )
            db.add(canonical)
            db.commit()
            db.refresh(canonical)

        # 4. Upsert Store Listing
        listing = db.query(StoreListing).filter(
            StoreListing.platform_id == platform.id,
            StoreListing.platform_uid == uid
        ).first()

        if not listing:
            listing = StoreListing(
                canonical_product_id=canonical.id,
                platform_id=platform.id,
                platform_uid=uid,
                raw_title=name,
                url=url,
                image_url=image_url,
                current_mrp=old_price,
                current_selling_price=new_price,
                in_stock=in_stock
            )
            db.add(listing)
            db.commit()
            db.refresh(listing)
            new_listings += 1
            
            # --- PORTFOLIO TRICK: Seed initial price history ---
            # Insert the 'old' price as if it was recorded yesterday
            if old_price > 0 and old_price != new_price:
                history_old = PriceHistory(
                    store_listing_id=listing.id,
                    selling_price=old_price,
                    mrp=old_price,
                    in_stock=True,
                    recorded_at=datetime.utcnow() - timedelta(days=1)
                )
                db.add(history_old)

            # Insert the 'new' price for today
            history_new = PriceHistory(
                store_listing_id=listing.id,
                selling_price=new_price,
                mrp=old_price,
                in_stock=in_stock,
                recorded_at=datetime.utcnow()
            )
            db.add(history_new)
            db.commit()

        else:
            # Listing exists. Update live price if it changed
            if listing.current_selling_price != new_price or listing.in_stock != in_stock:
                listing.current_selling_price = new_price
                listing.current_mrp = old_price
                listing.in_stock = in_stock
                listing.last_updated = datetime.utcnow()
                
                # Log the new price to history
                new_history = PriceHistory(
                    store_listing_id=listing.id,
                    selling_price=new_price,
                    mrp=old_price,
                    in_stock=in_stock,
                    recorded_at=datetime.utcnow()
                )
                db.add(new_history)
                db.commit()
                updated_listings += 1

    db.close()
    print(f"Ingestion complete! Created {new_listings} new listings, updated {updated_listings} existing listings.")

if __name__ == "__main__":
    seed_bigbasket_data()
