"""Command-line interface.

    python -m parking.cli init --levels 3 --small 10 --medium 30 --large 5
    python -m parking.cli park "DXB A 12345" car
    python -m parking.cli find "DXB A 12345"
    python -m parking.cli leave "DXB A 12345"
    python -m parking.cli status
    python -m parking.cli report --days 7
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

from .db import Database
from .lot import ParkingLot
from .models import ParkingError, VehicleType

DB_PATH = os.environ.get("PARKING_DB", "parking.db")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="parking", description="Smart Parking Management System")
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="create the slot layout")
    init.add_argument("--levels", type=int, default=3)
    init.add_argument("--small", type=int, default=10)
    init.add_argument("--medium", type=int, default=30)
    init.add_argument("--large", type=int, default=5)

    park = sub.add_parser("park", help="register a vehicle entering")
    park.add_argument("plate")
    park.add_argument("vehicle", choices=[v.value for v in VehicleType])

    for name, help_ in (("leave", "register a vehicle exiting"), ("find", "locate a parked vehicle")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("plate")

    sub.add_parser("status", help="occupancy by slot size")
    rep = sub.add_parser("report", help="revenue report")
    rep.add_argument("--days", type=int, default=1)

    args = p.parse_args(argv)
    lot = ParkingLot(Database(DB_PATH))

    try:
        if args.cmd == "init":
            lot.build_layout(args.levels, args.small, args.medium, args.large)
            print(f"Created {lot.db.slot_count()} slots across {args.levels} levels.")
        elif args.cmd == "park":
            t = lot.park(args.plate, VehicleType(args.vehicle))
            print(f"Ticket #{t.id}: {t.plate} -> slot {t.slot_label} at {t.entry_time:%H:%M}")
        elif args.cmd == "leave":
            r = lot.leave(args.plate)
            print(f"Ticket #{r.ticket_id}: {r.plate} left {r.slot_label} after "
                  f"{r.duration_minutes} min. Fee: AED {r.fee:.2f}")
        elif args.cmd == "find":
            t = lot.find(args.plate)
            print(f"{t.plate} is in slot {t.slot_label} since {t.entry_time:%Y-%m-%d %H:%M}"
                  if t else "Not parked here.")
        elif args.cmd == "status":
            print(f"{'size':<8}{'total':>7}{'occupied':>10}{'free':>7}")
            for size, s in lot.occupancy().items():
                print(f"{size:<8}{s['total']:>7}{s['occupied']:>10}{s['free']:>7}")
        elif args.cmd == "report":
            end = datetime.now()
            rows = lot.revenue_report(end - timedelta(days=args.days), end)
            print(f"Revenue, last {args.days} day(s)")
            print(f"{'vehicle':<12}{'visits':>7}{'AED':>10}{'avg hrs':>9}")
            for r in rows:
                print(f"{r['vehicle_type']:<12}{r['visits']:>7}{r['revenue']:>10.2f}{r['avg_hours']:>9.2f}")
            if not rows:
                print("(no completed visits)")
    except ParkingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
