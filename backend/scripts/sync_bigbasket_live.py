"""Concurrent BigBasket Matrix API scraper and DealNest database sync."""

import argparse
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://dealnest:dealnest@51.20.107.225:5432/dealnest_db",
)
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import CanonicalProduct, PriceHistory, StoreListing  # noqa: E402


BASE_URL = "https://www.bigbasket.com"
MATRIX_URL = f"{BASE_URL}/listing-svc/v2/products"
CATEGORIES = [
    "electronics", "fashion", "fruits-vegetables", "foodgrains-oil-masala",
    "bakery-cakes-dairy", "beverages", "snacks-branded-foods", "beauty-hygiene",
    "cleaning-household", "kitchen-garden-pets", "eggs-meat-fish",
    "gourmet-world-food", "baby-care", "paan-corner",
]
MAX_WORKERS = 15
REQUEST_TIMEOUT = 30
SCRAPER_API_URL = "https://api.scraperapi.com/"
SCRAPER_API_KEY = "17cb5d57fe01142ce83b2eefa772355a"
COOKIE_LOCK = threading.Lock()
_cookie_index = 0


def load_cookies() -> list[str]:
    script_pool = Path(__file__).resolve().with_name("bb_cookie_pool.txt")
    cwd_pool = Path.cwd() / "bb_cookie_pool.txt"
    pool_path = script_pool if script_pool.is_file() else cwd_pool
    if not pool_path.is_file():
        raise FileNotFoundError(
            f"Cookie pool not found at {script_pool} or {cwd_pool}. Run generate_bb_cookies.py first."
        )
    cookies = [line.strip() for line in pool_path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    if not cookies:
        raise ValueError(f"No cookies found in {pool_path}")
    print(f"Loaded {len(cookies)} BigBasket session cookie(s) from {pool_path}.")
    return cookies


def next_cookie(cookies: list[str]) -> str:
    global _cookie_index
    with COOKIE_LOCK:
        cookie = cookies[_cookie_index % len(cookies)]
        _cookie_index += 1
        return cookie


def request_headers(cookie: str) -> dict[str, str]:
    is_bbnow = "xentrycontext=bbnow" in cookie.lower()
    return {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "accept": "application/json, text/plain, */*",
        "x-channel": "BB-WEB",
        "x-entry-context-id": "10" if is_bbnow else "100",
        "x-entry-context": "bbnow" if is_bbnow else "bb-b2c",
        "osmos-enabled": "true",
        "cookie": cookie,
    }


def fetch_page(category: str, page_number: int, cookies: list[str], retries: int = 3):
    params = {"type": "pc", "slug": category, "page": page_number}
    headers = request_headers(next_cookie(cookies))
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                MATRIX_URL, params=params,
                headers=headers, timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 403:
                target_url = requests.Request("GET", MATRIX_URL, params=params).prepare().url
                print(f"   HTTP 403 for {category} page {page_number}; retrying through ScraperAPI.")
                response = requests.get(
                    SCRAPER_API_URL,
                    params={
                        "api_key": SCRAPER_API_KEY,
                        "url": target_url,
                        "country_code": "in",
                        "keep_headers": "true",
                    },
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
            if response.status_code == 429:
                last_error = requests.HTTPError("HTTP 429 Too Many Requests")
                if attempt < retries:
                    time.sleep(4)
                    continue
                break
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(4 if getattr(getattr(exc, "response", None), "status_code", None) == 429
                           else min(2 ** attempt, 4))
    print(f"   Request failed for {category} page {page_number}: {last_error}")
    return None


def product_info(data):
    if not isinstance(data, dict):
        return {}
    tabs = data.get("tabs") or []
    if not tabs or not isinstance(tabs[0], dict):
        return {}
    info = tabs[0].get("product_info")
    return info if isinstance(info, dict) else {}


def extract_products(data) -> list[dict]:
    info = product_info(data)
    products = info.get("products") or []
    extracted = []
    for item in products:
        if not isinstance(item, dict):
            continue
        product_id = str(item.get("id", "")).strip()
        description = item.get("desc", "") or ""
        brand_data = item.get("brand") or {}
        brand = brand_data.get("name", "") if isinstance(brand_data, dict) else ""
        relative_url = item.get("absolute_url", "") or ""
        full_url = f"{BASE_URL}{relative_url}" if relative_url.startswith("/") else relative_url
        pricing = item.get("pricing") or {}
        discount_data = pricing.get("discount") or {}
        prim_price = discount_data.get("prim_price") or {}
        try:
            mrp = float(discount_data.get("mrp") or 0.0)
            selling_price = float(prim_price.get("sp") or 0.0)
        except (TypeError, ValueError):
            continue
        images = item.get("images") or []
        image_url = ""
        if images and isinstance(images[0], dict):
            image_url = images[0].get("l") or images[0].get("m") or images[0].get("url", "")
        availability = item.get("availability") or {}
        avail_status = availability.get("avail_status", "001") if isinstance(availability, dict) else "001"
        if not product_id or not full_url or selling_price <= 0:
            continue
        extracted.append({
            "product_id": product_id,
            "description": description,
            "brand": brand,
            "url": full_url,
            "mrp": mrp,
            "selling_price": selling_price,
            "image_url": image_url,
            "in_stock": avail_status == "001",
        })
    return extracted


def discover(cookies: list[str]) -> tuple[list[dict], list[tuple[str, int]]]:
    print(f"Phase 1 Discovery: fetching page 1 for {len(CATEGORIES)} categories...")
    all_products: list[dict] = []
    tasks: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_page, cat, 1, cookies): cat for cat in CATEGORIES}
        for future in as_completed(futures):
            category = futures[future]
            data = future.result()
            if data is None:
                continue
            all_products.extend(extract_products(data))
            info = product_info(data)
            pages = info.get("number_of_pages", 1)
            try:
                pages = int(pages or 1)
            except (TypeError, ValueError):
                pages = 1
            tasks.extend((category, page) for page in range(2, max(1, pages) + 1))
            print(f"   {category}: {len(info.get('products') or [])} on page 1; {pages} page(s)")
    random.shuffle(tasks)
    print(f"Phase 1 complete: discovered {len(tasks)} additional page task(s).")
    return all_products, tasks


def scrape_pages(tasks: list[tuple[str, int]], cookies: list[str], products: list[dict]) -> list[dict]:
    print(f"Phase 2 Matrix Scraping: fetching {len(tasks)} page(s) with {MAX_WORKERS} workers...")
    if tasks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_page, cat, page, cookies): (cat, page)
                       for cat, page in tasks}
            completed = 0
            for future in as_completed(futures):
                cat, page = futures[future]
                data = future.result()
                if data is not None:
                    products.extend(extract_products(data))
                completed += 1
                if completed % 50 == 0 or completed == len(tasks):
                    print(f"   Matrix pages completed: {completed}/{len(tasks)}")
    # Deduplicate by product ID, falling back to canonical URL when an ID is absent.
    deduped = {}
    for item in products:
        key = item["product_id"] or item["url"]
        deduped[key] = item
    products = list(deduped.values())
    print(f"Phase 2 complete: collected {len(products)} unique scraped product(s).")
    return products


def sync_database(products: list[dict], upsert_all: bool) -> tuple[int, int]:
    print("Phase 3 Database Commit: matching and applying scraped prices...")
    db = SessionLocal()
    updated = inserted = 0
    try:
        # Select only columns used here: the deployed platforms table may not
        # include every optional column present in the ORM model (such as base_url).
        platform_row = db.execute(text(
            "SELECT id, name FROM platforms WHERE name ILIKE 'bigbasket' LIMIT 1"
        )).first()
        if platform_row is None:
            raise RuntimeError("BigBasket platform row was not found in platforms.")
        platform_id = platform_row.id
        existing = db.query(StoreListing).filter(StoreListing.platform_id == platform_id).all()
        by_uid = {str(row.platform_uid): row for row in existing}
        by_url = {row.url.rstrip("/"): row for row in existing}
        by_pd = {}
        for row in existing:
            uid = str(row.platform_uid or "")
            match = re.search(r"\d+", uid)
            url_match = re.search(r"/pd/(\d+)", row.url or "")
            title_match = re.search(r"\b(\d{5,})\b", row.raw_title or "")
            for value in (match.group(0) if match else None,
                          url_match.group(1) if url_match else None,
                          title_match.group(1) if title_match else None):
                if value:
                    by_pd[value] = row

        history_rows = []
        for item in products:
            listing = by_uid.get(item["product_id"]) or by_url.get(item["url"].rstrip("/")) or by_pd.get(item["product_id"])
            if listing is None and not upsert_all:
                continue
            title = " ".join(part for part in (item["brand"], item["description"]) if part).strip()
            if listing is None:
                canonical = CanonicalProduct(
                    name=(item["description"] or title or item["product_id"])[:255],
                    brand=(item["brand"] or None), image_url=(item["image_url"] or None),
                )
                db.add(canonical)
                db.flush()
                listing = StoreListing(
                    canonical_product_id=canonical.id,
                    platform_id=platform_id,
                    platform_uid=item["product_id"],
                    raw_title=(title or item["description"] or item["product_id"])[:500],
                    url=item["url"], image_url=item["image_url"] or None,
                    current_mrp=item["mrp"], current_selling_price=item["selling_price"],
                    in_stock=item["in_stock"], location="HYDERABAD",
                )
                db.add(listing)
                db.flush()
                inserted += 1
            else:
                listing.current_selling_price = item["selling_price"]
                listing.current_mrp = item["mrp"]
                listing.in_stock = item["in_stock"]
                listing.image_url = item["image_url"] or listing.image_url
                listing.url = item["url"] or listing.url
                listing.last_updated = datetime.utcnow()
                updated += 1
                if listing.canonical_product:
                    listing.canonical_product.image_url = item["image_url"] or listing.canonical_product.image_url
                    if item["brand"] and not listing.canonical_product.brand:
                        listing.canonical_product.brand = item["brand"][:100]
            history_rows.append(PriceHistory(
                store_listing_id=listing.id,
                selling_price=item["selling_price"], mrp=item["mrp"],
                in_stock=item["in_stock"],
            ))
        db.add_all(history_rows)
        db.commit()
        print(f"Phase 3 complete: {updated} existing listing(s) updated; {inserted} new listing(s) inserted; "
              f"{len(history_rows)} price history record(s) committed.")
        return updated, inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upsert-all", action="store_true",
                        help="insert newly discovered products as DealNest listings; default only updates existing listings")
    parser.add_argument("--update-existing", action="store_true",
                        help="update only listings already present (the default)")
    args = parser.parse_args()
    started = time.monotonic()
    try:
        cookies = load_cookies()
        products, tasks = discover(cookies)
        products = scrape_pages(tasks, cookies, products)
        updated, inserted = sync_database(products, upsert_all=args.upsert_all)
        print(f"Sync complete: scraped {len(products)} item(s), matched/updated {updated} existing listing(s), "
              f"inserted {inserted}; total execution time {time.monotonic() - started:.1f}s.")
    except Exception as exc:
        print(f"BigBasket sync failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
