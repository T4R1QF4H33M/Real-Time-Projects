"""Generate synthetic raw sales extracts for a fictional UAE electronics retailer.

The data is deliberately messy, the way real POS exports often are:
mixed date formats, prices stored as text ("AED 1,299.00"), stray whitespace,
inconsistent casing, duplicate rows, unknown product codes, missing values and
returns recorded as negative quantities.

    python generate_data.py --months 6 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

RAW = Path(__file__).resolve().parent / "data" / "raw"

STORES = [
    ("ST01", "Dubai Mall", "Dubai", "Mall"),
    ("ST02", "Mall of the Emirates", "Dubai", "Mall"),
    ("ST03", "Ibn Battuta", "Dubai", "Mall"),
    ("ST04", "Yas Mall", "Abu Dhabi", "Mall"),
    ("ST05", "Al Wahda", "Abu Dhabi", "Mall"),
    ("ST06", "City Centre Sharjah", "Sharjah", "Mall"),
    ("ST07", "Ajman High Street", "Ajman", "Street"),
    ("ST08", "Online", "All", "Online"),
]

PRODUCTS = [
    ("P1001", "Smartphone X", "Phones", 2899), ("P1002", "Smartphone Lite", "Phones", 1299),
    ("P1003", "Budget Phone", "Phones", 549), ("P2001", "Laptop Pro 14", "Laptops", 6499),
    ("P2002", "Laptop Air 13", "Laptops", 3999), ("P2003", "Student Laptop", "Laptops", 2199),
    ("P3001", "Wireless Earbuds", "Audio", 449), ("P3002", "Noise-Cancelling Headphones", "Audio", 1199),
    ("P3003", "Bluetooth Speaker", "Audio", 299), ("P4001", "Smartwatch", "Wearables", 1499),
    ("P4002", "Fitness Band", "Wearables", 249), ("P5001", "65W Charger", "Accessories", 149),
    ("P5002", "USB-C Cable", "Accessories", 49), ("P5003", "Phone Case", "Accessories", 89),
    ("P5004", "Power Bank", "Accessories", 179), ("P6001", "Tablet 11", "Tablets", 2499),
]

STORE_WEIGHT = [18, 15, 9, 14, 7, 10, 5, 22]
PRODUCT_WEIGHT = [6, 9, 7, 2, 3, 4, 14, 5, 8, 5, 6, 12, 18, 15, 10, 3]
PAYMENT = ["Card", "card", "CARD ", "Cash", "cash", "Apple Pay", "Tabby"]


def _messy_date(d: datetime, rng: random.Random) -> str:
    fmt = rng.choices(["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%b-%Y %H:%M"], [70, 20, 10])[0]
    return d.strftime(fmt)


def _messy_price(p: float, rng: random.Random) -> str:
    style = rng.choices(["plain", "aed", "comma"], [60, 25, 15])[0]
    if style == "aed":
        return f"AED {p:,.2f}"
    if style == "comma":
        return f"{p:,.2f}"
    return f"{p:.2f}"


def generate(months: int, seed: int, start: date = date(2026, 1, 1)) -> list[Path]:
    rng = random.Random(seed)
    RAW.mkdir(parents=True, exist_ok=True)

    with open(RAW / "stores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["store_code", "store_name", "emirate", "channel"])
        w.writerows(STORES)

    with open(RAW / "products.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sku", "product_name", "category", "list_price_aed"])
        for sku, name, cat, price in PRODUCTS:
            # messy casing / whitespace in the master data too
            w.writerow([sku, f" {name} " if rng.random() < 0.2 else name, cat.upper() if rng.random() < 0.2 else cat, price])

    files = []
    txn = 100000
    for m in range(months):
        month_start = (start.replace(day=1) + timedelta(days=32 * m)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        path = RAW / f"sales_{month_start:%Y_%m}.csv"
        rows = []
        day = month_start
        while day < next_month:
            weekend = day.weekday() in (5, 6)  # UAE weekend (Sat/Sun) is busier
            seasonal = 1.35 if day.month == 3 else 1.0  # e.g. Ramadan/Eid promotions
            for _ in range(int(rng.randint(40, 60) * (1.3 if weekend else 1.0) * seasonal)):
                txn += 1
                store = rng.choices(STORES, STORE_WEIGHT)[0][0]
                sku, _, _, list_price = rng.choices(PRODUCTS, PRODUCT_WEIGHT)[0]
                qty = rng.choices([1, 2, 3, 4], [75, 17, 6, 2])[0]
                discount = rng.choices([0, 0.05, 0.1, 0.2], [70, 15, 10, 5])[0]
                when = datetime.combine(day, datetime.min.time()) + timedelta(
                    hours=rng.randint(10, 22), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
                )
                customer = f"C{rng.randint(1, 4000):05d}" if rng.random() > 0.15 else ""
                row = {
                    "transaction_id": f"T{txn}",
                    "transaction_ts": _messy_date(when, rng),
                    "store_code": store if rng.random() > 0.02 else f" {store.lower()}",
                    "sku": sku,
                    "quantity": str(-qty if rng.random() < 0.03 else qty),  # returns
                    "unit_price": _messy_price(list_price * (1 - discount), rng),
                    "customer_id": customer,
                    "payment_method": rng.choice(PAYMENT),
                }
                # inject data-quality problems
                r = rng.random()
                if r < 0.004:
                    row["sku"] = "P9999"  # unknown product
                elif r < 0.007:
                    row["unit_price"] = ""  # missing price
                elif r < 0.009:
                    row["transaction_ts"] = "not a date"
                rows.append(row)
                if rng.random() < 0.01:
                    rows.append(dict(row))  # exact duplicate from a double export
            day += timedelta(days=1)

        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        files.append(path)
        print(f"wrote {path.name}: {len(rows):,} rows")
    return files


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    generate(a.months, a.seed)
