"""Run the ETL pipeline end to end.

    python pipeline.py                       # data/raw -> warehouse.db
    python pipeline.py --raw data/raw --db warehouse.db
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from etl.extract import extract_sales, read_csv
from etl.load import connect, load_facts, load_quarantine, upsert_dimensions
from etl.quality import run_checks
from etl.transform import build_dim_date, clean_products, clean_stores, transform_sales

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("etl")


def run(raw_dir: Path, db_path: Path) -> bool:
    started = datetime.now()
    conn = connect(db_path)
    run_id = conn.execute(
        "INSERT INTO etl_run_log(started_at, status) VALUES (?, 'running')", (started.isoformat(),)
    ).lastrowid
    conn.commit()

    try:
        # Extract
        stores = clean_stores(read_csv(raw_dir / "stores.csv"))
        products = clean_products(read_csv(raw_dir / "products.csv"))
        raw_sales = extract_sales(raw_dir)
        log.info("extracted %s sales rows from %s files", f"{len(raw_sales):,}", raw_sales["source_file"].nunique())

        # Transform
        result = transform_sales(raw_sales, products, stores)
        log.info("transform: %s clean, %s rejected, %s duplicates",
                 f"{len(result.clean):,}", len(result.rejected), result.duplicates)
        for reason, n in result.rejected["reject_reason"].value_counts().items():
            log.info("   rejected %-26s %d", reason, n)

        # Load (single transaction: all or nothing)
        with conn:
            upsert_dimensions(conn, stores, products, build_dim_date(result.clean["transaction_ts"]))
            loaded = load_facts(conn, result.clean)
            load_quarantine(conn, result.rejected, run_id)
        log.info("loaded %s fact rows into %s", f"{loaded:,}", db_path.name)

        # Quality checks
        checks = run_checks(conn, result, loaded)
        for name, ok, detail in checks:
            log.info("   [%s] %-30s %s", "PASS" if ok else "FAIL", name, detail)
        failed = sum(not ok for _, ok, _ in checks)
        status = "success" if failed == 0 else "completed_with_warnings"

        conn.execute(
            """UPDATE etl_run_log SET finished_at=?, status=?, raw_rows=?, duplicates=?, rejected=?,
               loaded=?, checks_passed=?, checks_failed=? WHERE run_id=?""",
            (datetime.now().isoformat(), status, result.raw_rows, result.duplicates,
             len(result.rejected), loaded, len(checks) - failed, failed, run_id),
        )
        conn.commit()
        log.info("run %d finished: %s in %.1fs", run_id, status, (datetime.now() - started).total_seconds())
        return failed == 0
    except Exception as exc:
        conn.rollback()
        conn.execute(
            "UPDATE etl_run_log SET finished_at=?, status='failed', message=? WHERE run_id=?",
            (datetime.now().isoformat(), str(exc)[:500], run_id),
        )
        conn.commit()
        log.exception("run %d failed", run_id)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--db", type=Path, default=ROOT / "warehouse.db")
    args = ap.parse_args()
    raise SystemExit(0 if run(args.raw, args.db) else 1)
