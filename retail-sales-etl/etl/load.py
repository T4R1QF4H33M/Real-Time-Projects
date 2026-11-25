"""Load: write a star schema into SQLite.

Loads are idempotent: re-running the pipeline on the same files replaces the
same transactions instead of double counting them (upsert on transaction_id).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DDL = """
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY, full_date TEXT, year INTEGER, quarter INTEGER,
    month INTEGER, month_name TEXT, day_of_week TEXT, is_weekend INTEGER
);
CREATE TABLE IF NOT EXISTS dim_store (
    store_key INTEGER PRIMARY KEY AUTOINCREMENT,
    store_code TEXT UNIQUE NOT NULL, store_name TEXT, emirate TEXT, channel TEXT
);
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL, product_name TEXT, category TEXT, list_price_aed REAL
);
CREATE TABLE IF NOT EXISTS fact_sales (
    transaction_id TEXT PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    store_key      INTEGER NOT NULL REFERENCES dim_store(store_key),
    product_key    INTEGER NOT NULL REFERENCES dim_product(product_key),
    transaction_ts TEXT NOT NULL,
    customer_id    TEXT,
    payment_method TEXT,
    quantity       INTEGER NOT NULL,
    unit_price     REAL NOT NULL,
    discount_pct   REAL,
    net_amount     REAL NOT NULL,
    is_return      INTEGER NOT NULL,
    source_file    TEXT
);
CREATE INDEX IF NOT EXISTS ix_fact_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_store ON fact_sales(store_key);
CREATE TABLE IF NOT EXISTS quarantine_sales (
    transaction_id TEXT, transaction_ts TEXT, store_code TEXT, sku TEXT, quantity TEXT,
    unit_price TEXT, customer_id TEXT, payment_method TEXT, source_file TEXT,
    reject_reason TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT,
    status TEXT, raw_rows INTEGER, duplicates INTEGER, rejected INTEGER, loaded INTEGER,
    checks_passed INTEGER, checks_failed INTEGER, message TEXT
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    return conn


def upsert_dimensions(conn, stores: pd.DataFrame, products: pd.DataFrame, dim_date: pd.DataFrame) -> None:
    conn.executemany(
        """INSERT INTO dim_store(store_code, store_name, emirate, channel) VALUES (?,?,?,?)
           ON CONFLICT(store_code) DO UPDATE SET store_name=excluded.store_name,
           emirate=excluded.emirate, channel=excluded.channel""",
        stores[["store_code", "store_name", "emirate", "channel"]].itertuples(index=False),
    )
    conn.executemany(
        """INSERT INTO dim_product(sku, product_name, category, list_price_aed) VALUES (?,?,?,?)
           ON CONFLICT(sku) DO UPDATE SET product_name=excluded.product_name,
           category=excluded.category, list_price_aed=excluded.list_price_aed""",
        products[["sku", "product_name", "category", "list_price_aed"]].itertuples(index=False),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO dim_date VALUES (?,?,?,?,?,?,?,?)",
        dim_date.itertuples(index=False),
    )


def load_facts(conn, clean: pd.DataFrame) -> int:
    store_keys = dict(conn.execute("SELECT store_code, store_key FROM dim_store"))
    product_keys = dict(conn.execute("SELECT sku, product_key FROM dim_product"))
    rows = [
        (
            r.transaction_id,
            int(r.transaction_ts.strftime("%Y%m%d")),
            store_keys[r.store_code],
            product_keys[r.sku],
            r.transaction_ts.isoformat(sep=" "),
            r.customer_id,
            r.payment_method,
            int(r.quantity),
            float(r.unit_price),
            float(r.discount_pct),
            float(r.net_amount),
            int(r.is_return),
            r.source_file,
        )
        for r in clean.itertuples(index=False)
    ]
    conn.executemany(
        """INSERT INTO fact_sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(transaction_id) DO UPDATE SET
             date_key=excluded.date_key, store_key=excluded.store_key, product_key=excluded.product_key,
             transaction_ts=excluded.transaction_ts, customer_id=excluded.customer_id,
             payment_method=excluded.payment_method, quantity=excluded.quantity,
             unit_price=excluded.unit_price, discount_pct=excluded.discount_pct,
             net_amount=excluded.net_amount, is_return=excluded.is_return, source_file=excluded.source_file""",
        rows,
    )
    return len(rows)


def load_quarantine(conn, rejected: pd.DataFrame, run_id: int) -> None:
    cols = ["transaction_id", "transaction_ts", "store_code", "sku", "quantity", "unit_price",
            "customer_id", "payment_method", "source_file", "reject_reason"]
    # Replace earlier rejects from the same files so re-runs stay idempotent
    for f in rejected["source_file"].unique():
        conn.execute("DELETE FROM quarantine_sales WHERE source_file = ?", (f,))
    conn.executemany(
        f"INSERT INTO quarantine_sales({', '.join(cols)}, run_id) VALUES ({', '.join('?' * (len(cols) + 1))})",
        [(*row, run_id) for row in rejected[cols].itertuples(index=False)],
    )
