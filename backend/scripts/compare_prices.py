"""Compare product prices from two CSV snapshots."""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MORNING_CSV = DATA_DIR / "morning.csv"
EVENING_CSV = DATA_DIR / "evening.csv"


def read_snapshot(path):
    """Return products keyed by Product_ID and warnings for unusable rows."""
    products = {}
    warnings = []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {"Product_ID", "Description", "Selling_Price"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"{path.name} must contain columns: Product_ID, Description, Selling_Price"
            )
        for row_number, row in enumerate(reader, start=2):
            product_id = (row.get("Product_ID") or "").strip()
            if not product_id:
                warnings.append(f"{path.name} row {row_number}: missing Product_ID; skipped")
                continue
            raw_price = (row.get("Selling_Price") or "").strip()
            try:
                price = Decimal(raw_price)
                if not price.is_finite() or price < 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                warnings.append(
                    f"{path.name} row {row_number} ({product_id}): invalid or missing price; skipped"
                )
                continue
            if product_id in products:
                warnings.append(
                    f"{path.name} row {row_number}: duplicate Product_ID {product_id}; later row used"
                )
            products[product_id] = {
                "description": (row.get("Description") or "").strip(),
                "price": price,
            }
    return products, warnings


def compare_prices(morning, evening):
    """Print price changes and counts for products valid in both snapshots."""
    morning_products, warnings = read_snapshot(morning)
    evening_products, evening_warnings = read_snapshot(evening)
    warnings.extend(evening_warnings)
    matched_ids = sorted(morning_products.keys() & evening_products.keys())
    counts = {"decreased": 0, "increased": 0, "unchanged": 0}

    print("Price comparison: Morning → Evening")
    print("-" * 88)
    print(f"{'Product_ID':<12} {'Description':<25} {'Morning':>12} {'Evening':>12} {'Change':>12} {'Change %':>12} Status")
    print("-" * 88)
    for product_id in matched_ids:
        morning_item = morning_products[product_id]
        evening_item = evening_products[product_id]
        old_price = morning_item["price"]
        new_price = evening_item["price"]
        difference = new_price - old_price
        percent = (difference / old_price * Decimal("100")) if old_price else None
        if difference < 0:
            status = "Decreased"
            counts["decreased"] += 1
        elif difference > 0:
            status = "Increased"
            counts["increased"] += 1
        else:
            status = "Unchanged"
            counts["unchanged"] += 1
        description = evening_item["description"] or morning_item["description"] or "(no description)"
        percent_text = f"{percent:+.2f}%" if percent is not None else "N/A (from zero)"
        print(
            f"{product_id:<12} {description[:25]:<25} {old_price:>12.2f} {new_price:>12.2f} "
            f"{difference:+12.2f} {percent_text:>12} {status}"
        )

    print("-" * 88)
    print(f"Summary: {len(matched_ids)} matched | {counts['decreased']} decreased | "
          f"{counts['increased']} increased | {counts['unchanged']} unchanged")
    print(f"Not compared: {len(morning_products.keys() ^ evening_products.keys())} product ID(s) present in only one snapshot")
    for warning in warnings:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    compare_prices(MORNING_CSV, EVENING_CSV)
