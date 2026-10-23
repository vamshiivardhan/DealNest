import sys
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import StoreListing, PriceHistory

def extract_price_from_text(text: str) -> float:
    """Extract numeric float from string like '₹249' or 'Rs. 1,499.00'."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def run_live_scraper():
    db = SessionLocal()
    listings = db.query(StoreListing).all()
    total = len(listings)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {total} listings to check.")

    if total == 0:
        print("No store listings found in database. Seed data first.")
        db.close()
        return

    updated_count = 0

    with sync_playwright() as p:
        # Launch Chromium with stealth arguments to prevent bot detection hangs
        browser = p.chromium.launch(
            headless=True,  # Set to False if you want to visually watch the browser work
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        for idx, listing in enumerate(listings, start=1):
            title_preview = (listing.raw_title[:35] + "...") if len(listing.raw_title) > 35 else listing.raw_title
            print(f"[{idx}/{total}] Checking: {title_preview}")

            if not listing.url or not listing.url.startswith("http"):
                print("   ↳ Skipped: Invalid or missing URL.")
                continue

            try:
                # Fast timeout (15s) so one slow page does not block the entire run
                page.goto(listing.url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)

                # Modern selector fallbacks covering BigBasket product pages
                price_selectors = [
                    'h4:has-text("₹")',
                    'span:has-text("₹")',
                    'div[class*="Pricing___"] span',
                    'tr[class*="IyvVO"] span',
                    'td[class*="TableCell"] span'
                ]

                detected_price = 0.0
                for selector in price_selectors:
                    elements = page.locator(selector)
                    count = elements.count()
                    for i in range(min(count, 3)):
                        txt = elements.nth(i).inner_text().strip()
                        if "₹" in txt or "Rs" in txt:
                            val = extract_price_from_text(txt)
                            if val > 0:
                                detected_price = val
                                break
                    if detected_price > 0:
                        break

                if detected_price > 0:
                    old_price = listing.current_selling_price or 0.0
                    print(f"   ↳ Scraped Price: ₹{detected_price} (DB Price: ₹{old_price})")

                    if detected_price != old_price:
                        listing.current_selling_price = detected_price
                        listing.last_updated = datetime.utcnow()

                        history = PriceHistory(
                            store_listing_id=listing.id,
                            selling_price=detected_price,
                            mrp=listing.current_mrp,
                            in_stock=listing.in_stock,
                            recorded_at=datetime.utcnow()
                        )
                        db.add(history)
                        db.commit()
                        updated_count += 1
                        print(f"   ★ Price updated & logged to history!")
                else:
                    print("   ↳ Notice: Price element not found in DOM.")

            except Exception as err:
                print(f"   ↳ Request timeout or navigation error ({type(err).__name__}). Skipping.")
                continue

        browser.close()
        db.close()

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Complete. Updated {updated_count}/{total} listings.")

if __name__ == "__main__":
    run_live_scraper()
