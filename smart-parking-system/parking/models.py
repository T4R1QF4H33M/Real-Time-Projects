"""Domain objects for the parking system."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VehicleType(str, Enum):
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    TRUCK = "truck"


class SlotSize(int, Enum):
    """Ordered so a vehicle can use its own size or anything larger."""
    SMALL = 1
    MEDIUM = 2
    LARGE = 3


# Smallest slot each vehicle type needs.
REQUIRED_SIZE = {
    VehicleType.MOTORCYCLE: SlotSize.SMALL,
    VehicleType.CAR: SlotSize.MEDIUM,
    VehicleType.TRUCK: SlotSize.LARGE,
}


@dataclass(frozen=True)
class Slot:
    id: int
    level: int
    number: int
    size: SlotSize

    @property
    def label(self) -> str:
        return f"L{self.level}-{self.number:03d}"

    def fits(self, vehicle: VehicleType) -> bool:
        return self.size >= REQUIRED_SIZE[vehicle]


@dataclass
class Ticket:
    id: int
    plate: str
    vehicle_type: VehicleType
    slot_id: int
    slot_label: str
    entry_time: datetime
    exit_time: datetime | None = None
    fee: float | None = None

    @property
    def is_active(self) -> bool:
        return self.exit_time is None


class ParkingError(Exception):
    """Raised for business-rule violations (lot full, duplicate plate, ...)."""
