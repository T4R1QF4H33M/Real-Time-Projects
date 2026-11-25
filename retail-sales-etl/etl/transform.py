"""Transform: clean, standardise and validate raw data.

Every raw sales row ends up in exactly one place:
  * clean  -> loaded into fact_sales
  * duplicate -> dropped (counted)
  * rejected  -> written to the quarantine table with a reason
so the row counts always reconcile.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%b-%Y %H:%M"]
PAYMENT_MAP = {"card": "Card", "cash": "Cash", "apple pay": "Apple Pay", "tabby": "Tabby (BNPL)"}


@dataclass
class TransformResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame
    duplicates: int
    raw_rows: int


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["sku"] = out["sku"].str.strip().str.upper()
    out["product_name"] = out["product_name"].str.strip()
    out["category"] = out["category"].str.strip().str.title()
    out["list_price_aed"] = pd.to_numeric(out["list_price_aed"])
    return out.drop(columns=["source_file"], errors="ignore")


def clean_stores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].str.strip()
    out["store_code"] = out["store_code"].str.upper()
    return out.drop(columns=["source_file"], errors="ignore")


def parse_timestamp(s: pd.Series) -> pd.Series:
    """Try each known format; anything left unparsed becomes NaT."""
    result = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        missing = result.isna()
        if not missing.any():
            break
        result[missing] = pd.to_datetime(s[missing], format=fmt, errors="coerce")
    return result


def parse_price(s: pd.Series) -> pd.Series:
    cleaned = s.str.upper().str.replace("AED", "", regex=False).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned.replace("", np.nan), errors="coerce")


def transform_sales(raw: pd.DataFrame, products: pd.DataFrame, stores: pd.DataFrame) -> TransformResult:
    raw_rows = len(raw)
    df = raw.drop_duplicates(subset=[c for c in raw.columns if c != "source_file"]).copy()
    duplicates = raw_rows - len(df)

    df["transaction_id"] = df["transaction_id"].str.strip()
    df["store_code"] = df["store_code"].str.strip().str.upper()
    df["sku"] = df["sku"].str.strip().str.upper()
    df["transaction_ts"] = parse_timestamp(df["transaction_ts"].str.strip())
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
    df["unit_price"] = parse_price(df["unit_price"])
    df["customer_id"] = df["customer_id"].str.strip().replace("", None)
    df["payment_method"] = df["payment_method"].str.strip().str.lower().map(PAYMENT_MAP).fillna("Other")

    # Validation rules -> first failing rule becomes the reject reason
    rules = [
        ("invalid timestamp", df["transaction_ts"].isna()),
        ("missing or invalid price", df["unit_price"].isna() | (df["unit_price"] < 0)),
        ("invalid quantity", df["quantity"].isna() | (df["quantity"] == 0)),
        ("unknown product", ~df["sku"].isin(products["sku"])),
        ("unknown store", ~df["store_code"].isin(stores["store_code"])),
        ("duplicate transaction_id", df["transaction_id"].duplicated(keep="first")),
    ]
    reason = pd.Series(None, index=df.index, dtype="object")
    for name, mask in rules:
        reason = reason.where(~(mask & reason.isna()), name)

    rejected = raw.loc[reason.dropna().index].copy()
    rejected["reject_reason"] = reason.dropna()

    clean = df[reason.isna()].copy()
    clean["quantity"] = clean["quantity"].astype(int)
    clean["is_return"] = clean["quantity"] < 0
    clean["net_amount"] = (clean["quantity"] * clean["unit_price"]).round(2)
    clean = clean.merge(products[["sku", "list_price_aed"]], on="sku", how="left")
    clean["discount_pct"] = (1 - clean["unit_price"] / clean["list_price_aed"]).clip(lower=0).round(3)
    clean = clean.drop(columns=["list_price_aed"])

    return TransformResult(clean=clean, rejected=rejected, duplicates=duplicates, raw_rows=raw_rows)


def build_dim_date(ts: pd.Series) -> pd.DataFrame:
    days = pd.date_range(ts.min().normalize(), ts.max().normalize(), freq="D")
    return pd.DataFrame(
        {
            "date_key": days.strftime("%Y%m%d").astype(int),
            "full_date": days.strftime("%Y-%m-%d"),
            "year": days.year,
            "quarter": days.quarter,
            "month": days.month,
            "month_name": days.strftime("%B"),
            "day_of_week": days.strftime("%A"),
            "is_weekend": days.dayofweek.isin([5, 6]).astype(int),  # UAE weekend: Sat-Sun
        }
    )
