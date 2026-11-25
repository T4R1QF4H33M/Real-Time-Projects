"""Run the analytics queries against the warehouse and write a markdown report + chart.

    python report.py      # -> reports/sales_report.md, reports/monthly_revenue.png
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
SQL_FILE = ROOT / "sql" / "analytics.sql"
OUT = ROOT / "reports"


def load_queries(path: Path) -> dict[str, str]:
    """Split a .sql file into named queries using `-- name: xyz` markers."""
    parts = re.split(r"^-- name:\s*(\w+)\s*$", path.read_text(), flags=re.M)
    return {name: sql.strip() for name, sql in zip(parts[1::2], parts[2::2])}


def _fmt(v) -> str:
    if isinstance(v, float):
        return "—" if pd.isna(v) else f"{v:,.2f}"
    return str(v)


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_fmt(v) for v in row) + " |")
    return "\n".join(lines)


def main(db_path: Path = ROOT / "warehouse.db") -> None:
    OUT.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    results = {name: pd.read_sql_query(sql, conn) for name, sql in load_queries(SQL_FILE).items()}
    run = pd.read_sql_query("SELECT * FROM etl_run_log ORDER BY run_id DESC LIMIT 1", conn).iloc[0]

    monthly = results["monthly_revenue"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(monthly["month_name"].str[:3], monthly["net_revenue"] / 1e6, color="#2b6cb0")
    for i, v in enumerate(monthly["net_revenue"] / 1e6):
        ax.text(i, v + 0.02, f"{v:.2f}M", ha="center", fontsize=9)
    ax.set_ylabel("Net revenue (AED millions)")
    ax.set_title("Monthly net revenue")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "monthly_revenue.png", dpi=150)

    titles = {
        "monthly_revenue": "Monthly revenue and growth",
        "revenue_by_emirate": "Revenue by emirate and channel",
        "store_ranking": "Store ranking",
        "category_performance": "Category performance",
        "top_products_per_category": "Top product per category",
        "weekend_vs_weekday": "Weekend vs weekday",
        "payment_mix": "Payment mix",
        "data_quality_summary": "Rows quarantined by the pipeline",
    }
    md = [
        "# Sales Report (synthetic data)",
        "",
        f"Generated from `warehouse.db`. Latest ETL run #{run['run_id']}: **{run['status']}**, "
        f"{run['raw_rows']:,} raw rows → {run['loaded']:,} loaded, {run['rejected']} quarantined, "
        f"{run['duplicates']} duplicates removed; {run['checks_passed']}/{run['checks_passed'] + run['checks_failed']} "
        "quality checks passed.",
        "",
        "![Monthly revenue](monthly_revenue.png)",
    ]
    for name, title in titles.items():
        md += ["", f"## {title}", "", to_markdown(results[name])]
    (OUT / "sales_report.md").write_text("\n".join(md) + "\n")
    print(f"Report written to {OUT / 'sales_report.md'}")


if __name__ == "__main__":
    main()
