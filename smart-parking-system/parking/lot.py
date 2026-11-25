"""ParkingLot: the service layer that applies the business rules."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .db import Database
from .models import REQUIRED_SIZE, ParkingError, SlotSize, Ticket, VehicleType
from .pricing import calculate_fee

_PLATE = re.compile(r"^[A-Z0-9 -]{2,12}$")


@dataclass
class Receipt:
    ticket_id: int
    plate: str
    slot_label: str
    entry_time: datetime
    exit_time: datetime
    fee: float

    @property
    def duration_minutes(self) -> int:
        return int((self.exit_time - self.entry_time).total_seconds() // 60)


class ParkingLot:
    def __init__(self, db: Database, clock: Callable[[], datetime] = datetime.now) -> None:
        self.db = db
        self.clock = clock  # injectable so tests can control time

    # ---- setup -----------------------------------------------------------
    def build_layout(self, levels: int, small: int, medium: int, large: int) -> None:
        """Create the same mix of slots on every level."""
        if self.db.slot_count():
            raise ParkingError("layout already exists")
        for level in range(1, levels + 1):
            number = 1
            for size, count in ((SlotSize.SMALL, small), (SlotSize.MEDIUM, medium), (SlotSize.LARGE, large)):
                for _ in range(count):
                    self.db.add_slot(level, number, size)
                    number += 1
        self.db.conn.commit()

    # ---- operations ------------------------------------------------------
    @staticmethod
    def normalise_plate(plate: str) -> str:
        plate = " ".join(plate.upper().split())
        if not _PLATE.match(plate):
            raise ParkingError(f"invalid plate number: {plate!r}")
        return plate

    def park(self, plate: str, vehicle: VehicleType) -> Ticket:
        plate = self.normalise_plate(plate)
        if self.db.active_ticket_by_plate(plate):
            raise ParkingError(f"{plate} is already parked")
        candidates = self.db.free_slots(REQUIRED_SIZE[vehicle])
        if not candidates:
            raise ParkingError(f"no free slot for a {vehicle.value}")
        slot = candidates[0]  # best fit: keeps large slots free for trucks
        ticket_id = self.db.open_ticket(plate, vehicle, slot.id, self.clock())
        return self.db.get_ticket(ticket_id)

    def leave(self, plate: str) -> Receipt:
        plate = self.normalise_plate(plate)
        ticket = self.db.active_ticket_by_plate(plate)
        if not ticket:
            raise ParkingError(f"no active ticket for {plate}")
        exit_time = self.clock()
        fee = calculate_fee(ticket.vehicle_type, ticket.entry_time, exit_time)
        self.db.close_ticket(ticket.id, exit_time, fee)
        return Receipt(ticket.id, plate, ticket.slot_label, ticket.entry_time, exit_time, fee)

    # ---- queries ---------------------------------------------------------
    def find(self, plate: str) -> Ticket | None:
        return self.db.active_ticket_by_plate(self.normalise_plate(plate))

    def occupancy(self) -> dict[str, dict[str, int]]:
        out = {}
        for row in self.db.occupancy_by_size():
            name = SlotSize(row["size"]).name.lower()
            out[name] = {"total": row["total"], "occupied": row["occupied"],
                         "free": row["total"] - row["occupied"]}
        return out

    def revenue_report(self, start: datetime, end: datetime) -> list[dict]:
        return [dict(r) for r in self.db.revenue(start, end)]
