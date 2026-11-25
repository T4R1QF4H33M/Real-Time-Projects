"""Simulate one day of traffic through the lot and chart the results.

    python simulate.py            # writes results/occupancy.png and prints a summary

Arrivals follow a simple weekday pattern (morning and evening peaks); each
vehicle stays for a random, roughly log-normal duration.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates
import matplotlib.pyplot as plt

from parking import Database, ParkingError, ParkingLot, VehicleType

SEED = 7
DAY = datetime(2026, 3, 2)  # a Monday
# Expected arrivals per hour, 00:00 → 23:00
ARRIVALS_PER_HOUR = [2, 1, 1, 1, 2, 6, 18, 40, 55, 35, 25, 22,
                     28, 26, 20, 18, 22, 30, 34, 24, 14, 9, 5, 3]
VEHICLE_MIX = [(VehicleType.CAR, 0.80), (VehicleType.MOTORCYCLE, 0.12), (VehicleType.TRUCK, 0.08)]


class SimClock:
    def __init__(self) -> None:
        self.now = DAY

    def __call__(self) -> datetime:
        return self.now


def main() -> None:
    rng = random.Random(SEED)
    clock = SimClock()
    lot = ParkingLot(Database(":memory:"), clock=clock)
    lot.build_layout(levels=3, small=10, medium=30, large=5)  # 135 slots

    # Build the event list: (time, kind, plate, vehicle)
    events = []
    for hour, rate in enumerate(ARRIVALS_PER_HOUR):
        for i in range(rng.randint(int(rate * 0.8), int(rate * 1.2))):
            arrive = DAY + timedelta(hours=hour, minutes=rng.randint(0, 59))
            stay = timedelta(minutes=max(5, int(rng.lognormvariate(4.6, 0.8))))  # median ≈ 100 min
            vehicle = rng.choices([v for v, _ in VEHICLE_MIX], [w for _, w in VEHICLE_MIX])[0]
            plate = f"DXB {rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')} {rng.randint(10000, 99999)}"
            events.append((arrive, "in", plate, vehicle))
            events.append((arrive + stay, "out", plate, vehicle))
    events.sort(key=lambda e: (e[0], e[1] == "in"))  # exits before entries at the same minute

    parked: set[str] = set()
    turned_away = {v: 0 for v in VehicleType}
    timeline = []
    for when, kind, plate, vehicle in events:
        if when >= DAY + timedelta(days=1):
            break
        clock.now = when
        if kind == "in":
            try:
                lot.park(plate, vehicle)
                parked.add(plate)
            except ParkingError:
                turned_away[vehicle] += 1
        elif plate in parked:
            lot.leave(plate)
            parked.discard(plate)
        occ = lot.occupancy()
        timeline.append((when, {k: v["occupied"] / v["total"] for k, v in occ.items()}))

    # Chart occupancy by slot size
    Path("results").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    for size in ("small", "medium", "large"):
        ax.step([t for t, _ in timeline], [o[size] * 100 for _, o in timeline], where="post", label=size)
    ax.set_ylabel("Occupancy %")
    ax.set_ylim(0, 105)
    ax.set_title("Simulated weekday occupancy by slot size (135 slots)")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("results/occupancy.png", dpi=150)

    report = lot.revenue_report(DAY, DAY + timedelta(days=1))
    total_visits = sum(r["visits"] for r in report)
    print(f"Completed visits: {total_visits}")
    for r in report:
        print(f"  {r['vehicle_type']:<11} {r['visits']:>4} visits  AED {r['revenue']:>8.2f}  "
              f"avg {r['avg_hours']:.2f} h")
    print(f"Total revenue: AED {sum(r['revenue'] for r in report):.2f}")
    peak_time, peak = max(timeline, key=lambda x: x[1]["medium"])
    print(f"Peak medium-slot occupancy: {peak['medium']:.0%} at {peak_time:%H:%M}")
    print("Turned away (lot full):", {k.value: v for k, v in turned_away.items()})
    print("Chart saved to results/occupancy.png")


if __name__ == "__main__":
    main()
