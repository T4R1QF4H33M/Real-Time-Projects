import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parking import Database, ParkingError, ParkingLot, VehicleType  # noqa: E402
from parking.pricing import calculate_fee  # noqa: E402

T0 = datetime(2026, 1, 1, 9, 0)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


@pytest.fixture
def clock():
    return FakeClock(T0)


@pytest.fixture
def lot(clock):
    lot = ParkingLot(Database(":memory:"), clock=clock)
    lot.build_layout(levels=2, small=1, medium=2, large=1)  # 8 slots
    return lot


# ---- allocation ------------------------------------------------------------
def test_car_gets_medium_slot_on_lowest_level(lot):
    t = lot.park("DXB A 111", VehicleType.CAR)
    assert t.slot_label == "L1-002"


def test_motorcycle_prefers_small_slot(lot):
    assert lot.park("M1", VehicleType.MOTORCYCLE).slot_label == "L1-001"


def test_truck_only_fits_large(lot):
    assert lot.park("T1", VehicleType.TRUCK).slot_label == "L1-004"
    assert lot.park("T2", VehicleType.TRUCK).slot_label == "L2-004"
    with pytest.raises(ParkingError, match="no free slot"):
        lot.park("T3", VehicleType.TRUCK)


def test_car_overflows_into_large_slot_when_mediums_full(lot):
    for i in range(4):
        lot.park(f"C{i}", VehicleType.CAR)
    t = lot.park("C9", VehicleType.CAR)
    assert t.slot_label == "L1-004"


def test_same_plate_cannot_park_twice(lot):
    lot.park("dxb  a 111", VehicleType.CAR)
    with pytest.raises(ParkingError, match="already parked"):
        lot.park("DXB A 111", VehicleType.CAR)


def test_invalid_plate_rejected(lot):
    with pytest.raises(ParkingError, match="invalid plate"):
        lot.park("!!", VehicleType.CAR)


def test_slot_is_freed_after_leaving(lot, clock):
    first = lot.park("A1", VehicleType.CAR)
    clock.advance(hours=1)
    lot.leave("A1")
    assert lot.park("A2", VehicleType.CAR).slot_label == first.slot_label


def test_leave_without_ticket_fails(lot):
    with pytest.raises(ParkingError, match="no active ticket"):
        lot.leave("NOPE1")


def test_find_and_occupancy(lot):
    lot.park("A1", VehicleType.CAR)
    assert lot.find("a1").slot_label == "L1-002"
    occ = lot.occupancy()
    assert occ["medium"] == {"total": 4, "occupied": 1, "free": 3}
    assert occ["small"]["occupied"] == 0


# ---- pricing ---------------------------------------------------------------
@pytest.mark.parametrize(
    "minutes, expected",
    [
        (10, 0.0),         # grace period
        (15, 0.0),         # boundary of grace period
        (16, 10.0),        # first started hour
        (60, 10.0),
        (61, 20.0),
        (7 * 60, 70.0),
        (12 * 60, 80.0),   # capped at daily max
        (24 * 60 + 30, 90.0),  # one full day + one started hour
    ],
)
def test_car_pricing(minutes, expected):
    assert calculate_fee(VehicleType.CAR, T0, T0 + timedelta(minutes=minutes)) == expected


def test_truck_and_motorcycle_rates():
    two_h = T0 + timedelta(hours=2)
    assert calculate_fee(VehicleType.TRUCK, T0, two_h) == 40.0
    assert calculate_fee(VehicleType.MOTORCYCLE, T0, two_h) == 10.0


def test_exit_before_entry_rejected():
    with pytest.raises(ValueError):
        calculate_fee(VehicleType.CAR, T0, T0 - timedelta(minutes=1))


# ---- end to end ------------------------------------------------------------
def test_receipt_and_revenue_report(lot, clock):
    lot.park("A1", VehicleType.CAR)
    lot.park("T1", VehicleType.TRUCK)
    clock.advance(hours=2, minutes=30)
    r1 = lot.leave("A1")
    r2 = lot.leave("T1")
    assert (r1.fee, r1.duration_minutes) == (30.0, 150)
    assert r2.fee == 60.0

    report = {row["vehicle_type"]: row for row in lot.revenue_report(T0, T0 + timedelta(days=1))}
    assert report["truck"]["revenue"] == 60.0
    assert report["car"]["visits"] == 1
    assert report["car"]["avg_hours"] == 2.5


def test_build_layout_twice_fails(lot):
    with pytest.raises(ParkingError):
        lot.build_layout(1, 1, 1, 1)
