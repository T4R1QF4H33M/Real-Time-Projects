import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.transform import (  # noqa: E402
    build_dim_date, clean_products, clean_stores, parse_price, parse_timestamp, transform_sales,
)


@pytest.fixture
def products():
    return clean_products(pd.DataFrame({
        "sku": ["p1001 ", "P2001"], "product_name": [" Phone ", "Laptop"],
        "category": ["PHONES", "laptops"], "list_price_aed": ["1000", "4000"],
    }))


@pytest.fixture
def stores():
    return clean_stores(pd.DataFrame({
        "store_code": ["st01"], "store_name": ["Dubai Mall"], "emirate": ["Dubai"], "channel": ["Mall"],
    }))


def sales(**overrides):
    row = {"transaction_id": "T1", "transaction_ts": "2026-01-05 10:00:00", "store_code": "ST01",
           "sku": "P1001", "quantity": "1", "unit_price": "1000.00", "customer_id": "C00001",
           "payment_method": "card", "source_file": "sales_2026_01.csv"}
    row.update(overrides)
    return row


def test_master_data_cleaning(products):
    assert products["sku"].tolist() == ["P1001", "P2001"]
    assert products["product_name"].tolist() == ["Phone", "Laptop"]
    assert products["category"].tolist() == ["Phones", "Laptops"]


def test_parse_price_handles_currency_and_commas():
    out = parse_price(pd.Series(["AED 1,299.00", "1,299.00", "49.50", "", "abc"]))
    assert out.tolist()[:3] == [1299.0, 1299.0, 49.5]
    assert out.isna().tolist()[3:] == [True, True]


def test_parse_timestamp_handles_mixed_formats():
    out = parse_timestamp(pd.Series(["2026-03-01 14:05:00", "01/03/2026 14:05", "01-Mar-2026 14:05", "nope"]))
    assert out[:3].dt.strftime("%Y-%m-%d %H:%M").tolist() == ["2026-03-01 14:05"] * 3
    assert pd.isna(out[3])


def test_transform_rejects_and_reconciles(products, stores):
    raw = pd.DataFrame([
        sales(),
        sales(),                                               # exact duplicate
        sales(transaction_id="T2", sku="P9999"),               # unknown product
        sales(transaction_id="T3", unit_price=""),             # missing price
        sales(transaction_id="T4", transaction_ts="garbage"),  # bad date
        sales(transaction_id="T5", quantity="0"),              # invalid qty
        sales(transaction_id="T6", store_code=" st01", quantity="-1"),  # return, messy store code
        sales(transaction_id="T1", unit_price="999"),          # re-used transaction id
    ])
    r = transform_sales(raw, products, stores)
    assert r.duplicates == 1
    assert sorted(r.clean["transaction_id"]) == ["T1", "T6"]
    assert dict(zip(r.rejected["transaction_id"], r.rejected["reject_reason"])) == {
        "T2": "unknown product", "T3": "missing or invalid price",
        "T4": "invalid timestamp", "T5": "invalid quantity",
        "T1": "duplicate transaction_id",
    }
    assert len(r.clean) + len(r.rejected) + r.duplicates == r.raw_rows

    ret = r.clean.set_index("transaction_id").loc["T6"]
    assert ret["is_return"] and ret["net_amount"] == -1000.0
    assert r.clean.set_index("transaction_id").loc["T1", "payment_method"] == "Card"


def test_discount_is_derived_from_list_price(products, stores):
    r = transform_sales(pd.DataFrame([sales(unit_price="AED 900.00")]), products, stores)
    assert r.clean["discount_pct"].iloc[0] == pytest.approx(0.1)


def test_dim_date_marks_uae_weekend():
    d = build_dim_date(pd.Series(pd.to_datetime(["2026-01-02", "2026-01-04"])))  # Fri .. Sun
    assert d.set_index("full_date")["is_weekend"].to_dict() == {
        "2026-01-02": 0, "2026-01-03": 1, "2026-01-04": 1,
    }


def test_full_pipeline_is_idempotent(tmp_path, monkeypatch):
    import generate_data
    import pipeline

    monkeypatch.setattr(generate_data, "RAW", tmp_path / "raw")
    generate_data.generate(months=2, seed=1)
    db = tmp_path / "wh.db"

    assert pipeline.run(tmp_path / "raw", db)
    conn = sqlite3.connect(db)
    first = conn.execute("SELECT COUNT(*), ROUND(SUM(net_amount), 2) FROM fact_sales").fetchone()
    conn.close()

    assert pipeline.run(tmp_path / "raw", db)  # second run must not double count
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*), ROUND(SUM(net_amount), 2) FROM fact_sales").fetchone() == first
    assert conn.execute("SELECT COUNT(*) FROM etl_run_log WHERE status = 'success'").fetchone()[0] == 2
    conn.close()
