"""Post-load data-quality checks. Each check returns (name, passed, detail)."""
from __future__ import annotations

import sqlite3

from .transform import TransformResult


def run_checks(conn: sqlite3.Connection, result: TransformResult, loaded: int) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    accounted = loaded + len(result.rejected) + result.duplicates
    checks.append((
        "row count reconciliation",
        accounted == result.raw_rows,
        f"raw {result.raw_rows} = loaded {loaded} + rejected {len(result.rejected)} "
        f"+ duplicates {result.duplicates}",
    ))

    reject_rate = len(result.rejected) / max(result.raw_rows, 1)
    checks.append(("reject rate below 2%", reject_rate < 0.02, f"{reject_rate:.2%}"))

    def scalar(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    orphans = scalar(
        """SELECT COUNT(*) FROM fact_sales f
           LEFT JOIN dim_store s ON f.store_key = s.store_key
           LEFT JOIN dim_product p ON f.product_key = p.product_key
           LEFT JOIN dim_date d ON f.date_key = d.date_key
           WHERE s.store_key IS NULL OR p.product_key IS NULL OR d.date_key IS NULL"""
    )
    checks.append(("referential integrity", orphans == 0, f"{orphans} orphan fact rows"))

    nulls = scalar("SELECT COUNT(*) FROM fact_sales WHERE net_amount IS NULL OR quantity IS NULL")
    checks.append(("no null measures", nulls == 0, f"{nulls} rows"))

    bad_sign = scalar(
        "SELECT COUNT(*) FROM fact_sales WHERE (is_return = 1 AND net_amount > 0) OR (is_return = 0 AND net_amount < 0)"
    )
    checks.append(("return sign consistency", bad_sign == 0, f"{bad_sign} rows"))

    outliers = scalar("SELECT COUNT(*) FROM fact_sales WHERE ABS(quantity) > 20 OR unit_price > 20000")
    checks.append(("no extreme quantities/prices", outliers == 0, f"{outliers} rows"))

    return checks
