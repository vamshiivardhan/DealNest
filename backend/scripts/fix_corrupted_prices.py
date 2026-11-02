"""Normalize sub-rupee listing deltas in the local DealNest PostgreSQL DB.

The seed file is used as a recovery source only when a listing price is missing
or nonpositive and the seed has a plausible positive price. Existing nonzero
values are left alone because they may be newer live-verified prices.
"""

import json
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data" / "data-bb.json"
ENV_PATH = ROOT / "backend" / ".env"


def database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if value:
        return value

    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            key, separator, raw_value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL":
                return raw_value.strip().strip("\"'")

    return "postgresql+psycopg://vamshij@localhost:5432/dealnest_db"


def read_seed_prices() -> dict[str, tuple[float | None, float | None]]:
    if not SEED_PATH.exists():
        return {}

    items = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    prices = {}
    for item in items:
        uid = item.get("uid")
        if uid is None:
            continue
        # Older seed records use old_price/new_price for MRP/selling price.
        mrp = item.get("mrp", item.get("old_price"))
        selling = item.get("selling_price", item.get("new_price"))
        prices[str(uid)] = (
            float(mrp) if mrp is not None else None,
            float(selling) if selling is not None else None,
        )
    return prices


def main() -> None:
    dsn = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    seed_prices = read_seed_prices()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.platform_uid, s.current_mrp, s.current_selling_price
                FROM store_listings AS s
                JOIN platforms AS p ON p.id = s.platform_id
                WHERE p.name = 'BigBasket'
                """
            )
            listings = cur.fetchall()

            seed_pairs_found = 0
            seed_pairs_matching = 0
            seed_restored = 0
            implausible_seed_prices_normalized = 0
            for listing_id, uid, mrp, selling in listings:
                seed_pair = seed_prices.get(str(uid))
                if seed_pair is None:
                    continue
                seed_mrp, seed_selling = seed_pair
                if seed_mrp is None or seed_selling is None:
                    continue
                seed_pairs_found += 1

                if mrp is not None and selling is not None:
                    if round(float(mrp), 2) == round(seed_mrp, 2) and round(float(selling), 2) == round(seed_selling, 2):
                        seed_pairs_matching += 1

                    # The seed has one clearly implausible 1-paise selling
                    # price against a ₹48 MRP. With no trustworthy sale price
                    # in the seed, use the known MRP as a no-discount fallback
                    # instead of surfacing a fabricated 100% deal.
                    if (
                        seed_selling < 1
                        and seed_mrp >= 1
                        and round(float(selling), 2) == round(seed_selling, 2)
                        and round(float(mrp), 2) == round(seed_mrp, 2)
                    ):
                        cur.execute(
                            "UPDATE store_listings SET current_selling_price = current_mrp WHERE id = %s",
                            (listing_id,),
                        )
                        implausible_seed_prices_normalized += cur.rowcount
                        continue

                # Recover only missing/invalid DB values. Never replace valid
                # live prices with the older seed snapshot.
                restore_mrp = mrp is None or float(mrp) <= 0
                restore_selling = selling is None or float(selling) <= 0
                if (restore_mrp or restore_selling) and seed_mrp > 0 and seed_selling >= 1:
                    next_mrp = seed_mrp if restore_mrp else mrp
                    next_selling = seed_selling if restore_selling else selling
                    cur.execute(
                        """
                        UPDATE store_listings
                        SET current_mrp = %s, current_selling_price = %s
                        WHERE id = %s
                        """,
                        (next_mrp, next_selling, listing_id),
                    )
                    seed_restored += cur.rowcount

            cur.execute(
                """
                SELECT count(*)
                FROM store_listings AS s
                JOIN platforms AS p ON p.id = s.platform_id
                WHERE p.name = 'BigBasket'
                  AND s.current_mrp IS NOT NULL
                  AND abs(s.current_mrp - s.current_selling_price) BETWEEN 0.005 AND 0.015
                  AND (
                    s.current_mrp IS DISTINCT FROM round(s.current_selling_price)
                    OR s.current_selling_price IS DISTINCT FROM round(s.current_selling_price)
                  )
                """
            )
            cent_delta_rows = cur.fetchone()[0]

            cur.execute(
                """
                SELECT count(*)
                FROM store_listings AS s
                JOIN platforms AS p ON p.id = s.platform_id
                WHERE p.name = 'BigBasket'
                  AND s.current_mrp IS NOT NULL
                  AND s.current_mrp - s.current_selling_price < 1.0
                  AND (
                    s.current_mrp IS DISTINCT FROM round(s.current_selling_price)
                    OR s.current_selling_price IS DISTINCT FROM round(s.current_selling_price)
                  )
                """
            )
            under_one_rows = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE store_listings AS s
                SET current_selling_price = round(s.current_selling_price),
                    current_mrp = round(s.current_selling_price)
                FROM platforms AS p
                WHERE p.id = s.platform_id
                  AND p.name = 'BigBasket'
                  AND s.current_mrp IS NOT NULL
                  AND s.current_mrp - s.current_selling_price < 1.0
                  AND (
                    s.current_mrp IS DISTINCT FROM round(s.current_selling_price)
                    OR s.current_selling_price IS DISTINCT FROM round(s.current_selling_price)
                  )
                RETURNING s.id
                """
            )
            normalized_rows = len(cur.fetchall())

    print(f"BigBasket listings inspected: {len(listings)}")
    print(f"Seed price pairs found: {seed_pairs_found}; already matching DB: {seed_pairs_matching}")
    print(f"Rows restored from seed for missing/invalid DB prices: {seed_restored}")
    print(f"Implausible sub-₹1 seed prices reset to known MRP: {implausible_seed_prices_normalized}")
    print(f"Rows still needing sub-₹1 normalization before cleanup: {under_one_rows}")
    print(f"Rows still needing cleanup with an approximately ₹0.01 delta: {cent_delta_rows}")
    print(f"Rows normalized to a whole-rupee price and matching MRP: {normalized_rows}")
    if seed_pairs_found > seed_pairs_matching:
        print("Nonmatching seed pairs were preserved as potentially newer live prices.")


if __name__ == "__main__":
    main()
