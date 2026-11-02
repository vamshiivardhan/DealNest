import sys
import os
import json
import re
import time
import random
from datetime import datetime

# Ensure backend directory is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Platform, StoreListing, PriceHistory


def _iter_sku_products(node, sku_id):
    """Yield only product dictionaries whose own ID matches the page SKU."""
    if isinstance(node, dict):
        if str(node.get("id", "")) == sku_id:
            yield node
        for value in node.values():
            yield from _iter_sku_products(value, sku_id)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_sku_products(value, sku_id)


def _price_as_float(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace("₹", "").replace(",", "").strip()
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _price_from_discount(product):
    pricing = product.get("pricing")
    if not isinstance(pricing, dict):
        return None, None
    discount = pricing.get("discount")
    if not isinstance(discount, dict):
        return None, None

    prim_price = discount.get("prim_price")
    sp_value = prim_price.get("sp") if isinstance(prim_price, dict) else None
    if sp_value is None:
        sp_value = discount.get("sp")
    return _price_as_float(sp_value), _price_as_float(discount.get("mrp"))


def _sku_from_url(url):
    match = re.search(r"/pd/(\d+)", url or "")
    return match.group(1) if match else None


def extract_live_bigbasket_price(page, item_url: str) -> tuple[float | None, float | None, bool]:
    selling_price = None
    mrp = None
    in_stock = True

    sku_id = _sku_from_url(item_url)
    if not sku_id:
        return None, None, in_stock

    # 1. Read prices from the narrowest ancestor of the main product title
    # that contains both labels. This keeps carousel prices out of the result.
    try:
        visible_prices = page.evaluate("""() => {
            const title = document.querySelector('h1');
            if (!title) return null;
            let node = title;
            for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
                const text = node.innerText || '';
                const price = text.match(/Price:\\s*₹\\s*([0-9]+(?:\\.[0-9]+)?)/i);
                const mrp = text.match(/MRP:\\s*₹\\s*([0-9]+(?:\\.[0-9]+)?)/i);
                if (price && mrp) {
                    return { sp: parseFloat(price[1]), mrp: parseFloat(mrp[1]) };
                }
            }
            return null;
        }""")
        if visible_prices:
            selling_price = _price_as_float(visible_prices.get("sp"))
            mrp = _price_as_float(visible_prices.get("mrp"))
    except Exception:
        pass

    html = page.content()

    # 2. Fall back to __NEXT_DATA__ only on the product dictionary matching
    # this URL's SKU. Other products in carousels and recommendations are ignored.
    next_data_matches = re.findall(
        r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    for raw_json in next_data_matches:
        try:
            page_data = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError):
            continue

        for product in _iter_sku_products(page_data, sku_id):
            parsed_sp, parsed_mrp = _price_from_discount(product)
            if selling_price is None and parsed_sp is not None:
                selling_price = parsed_sp
            if mrp is None and parsed_mrp is not None:
                mrp = parsed_mrp
            if selling_price is not None and mrp is not None:
                break
        if selling_price is not None and mrp is not None:
            break

    # 3. Final fallback to JSON-LD only when its Product SKU matches the URL.
    if selling_price is None or mrp is None:
        ld_matches = re.findall(
            r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        for ld_raw in ld_matches:
            try:
                data = json.loads(ld_raw)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("@type")
                    is_product = item_type == "Product" or (
                        isinstance(item_type, list) and "Product" in item_type
                    )
                    item_sku = item.get("sku")
                    if not is_product or (item_sku is not None and str(item_sku) != sku_id):
                        continue

                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    if not isinstance(offers, dict):
                        offers = {}

                    if selling_price is None:
                        selling_price = _price_as_float(offers.get("price"))
                    if mrp is None:
                        mrp = _price_as_float(
                            offers.get("highPrice")
                            or offers.get("listPrice")
                            or item.get("mrp")
                        )
                    availability = str(offers.get("availability", "")).lower()
                    if "outofstock" in availability:
                        in_stock = False
                    break
            except Exception:
                continue

    if selling_price is not None and (mrp is None or mrp < selling_price):
        mrp = selling_price

    return selling_price, mrp, in_stock


def sync_bigbasket_prices(limit: int | None = None, offset: int = 0):
    db: Session = SessionLocal()
    try:
        query = (
            db.query(StoreListing)
            .join(Platform, StoreListing.platform_id == Platform.id)
            .filter(Platform.name == "BigBasket")
            .order_by(StoreListing.id.asc())
        )
        listings = query.offset(offset).limit(limit).all()

        total = len(listings)
        print(f"🚀 Connecting to live Chrome session (port 9222) for {total} products...\n")

        with sync_playwright() as p:
            # Connect over Chrome DevTools Protocol to the open browser
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            updated_count = 0
            consecutive_403s = 0
            for idx, item in enumerate(listings, start=1):
                item_number = offset + idx
                print(f"[{item_number}/{offset + total}] Checking: {item.raw_title[:45]}...")
                try:
                    response = page.goto(item.url, wait_until="domcontentloaded", timeout=25000)
                    status_code = response.status if response else "Unknown"
                    page.wait_for_timeout(1500)

                    access_denied = status_code == 403 or "Access Denied" in page.title()
                    if access_denied:
                        consecutive_403s += 1
                        print(f"   ❌ Access Denied (HTTP {status_code}) on {item.url}")
                        if consecutive_403s >= 2:
                            print(
                                "🚨 WAF BLOCK DETECTED. Stopping script to prevent IP ban. "
                                f"Resume later from item {item_number}."
                            )
                            break
                        if idx % 25 == 0:
                            print("   ☕ Taking a brief 15-second human pause to avoid rate limits...")
                            time.sleep(random.uniform(12.0, 18.0))
                        time.sleep(random.uniform(3.5, 6.5))
                        continue

                    if status_code == 200:
                        consecutive_403s = 0

                    live_sp, live_mrp, in_stock = extract_live_bigbasket_price(page, item_url=item.url)

                    if live_sp is not None:
                        old_sp = float(item.current_selling_price) if item.current_selling_price is not None else 0.0

                        item.current_selling_price = live_sp
                        item.current_mrp = live_mrp
                        item.in_stock = in_stock
                        item.last_updated = datetime.utcnow()

                        history_entry = PriceHistory(
                            store_listing_id=item.id,
                            mrp=live_mrp,
                            selling_price=live_sp,
                            in_stock=in_stock,
                            recorded_at=datetime.utcnow(),
                        )
                        db.add(history_entry)
                        db.commit()
                        updated_count += 1

                        if round(old_sp, 2) != round(live_sp, 2):
                            print(f"   ✅ [HTTP {status_code}] PRICE CHANGED: DB ₹{old_sp} -> LIVE ₹{live_sp} (MRP: ₹{live_mrp})")
                        else:
                            print(f"   ✓ [HTTP {status_code}] Verified Live: ₹{live_sp} (MRP: ₹{live_mrp})")
                    else:
                        print(f"   ⚠️ [HTTP {status_code}] Loaded page, but no price found")

                except Exception as e:
                    db.rollback()
                    print(f"   ❌ Error loading URL: {str(e).splitlines()[0]}")

                if idx % 25 == 0:
                    print("   ☕ Taking a brief 15-second human pause to avoid rate limits...")
                    time.sleep(random.uniform(12.0, 18.0))

                time.sleep(random.uniform(3.5, 6.5))

        print(f"\n🎉 Sync Complete! Successfully verified/updated {updated_count}/{total} items.")

    finally:
        db.close()


if __name__ == "__main__":
    sync_bigbasket_prices(offset=372)
