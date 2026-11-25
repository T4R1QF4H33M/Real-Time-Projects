"""Fee calculation.

Rules:
* First 15 minutes are free (drop-offs, wrong turns).
* After that, every started hour is charged at the vehicle's hourly rate.
* Each 24-hour block is capped at the vehicle's daily maximum.
"""
from __future__ import annotations

import math
from datetime import datetime

from .models import VehicleType

GRACE_MINUTES = 15
HOURLY_RATE_AED = {
    VehicleType.MOTORCYCLE: 5.0,
    VehicleType.CAR: 10.0,
    VehicleType.TRUCK: 20.0,
}
DAILY_CAP_AED = {
    VehicleType.MOTORCYCLE: 40.0,
    VehicleType.CAR: 80.0,
    VehicleType.TRUCK: 150.0,
}


def calculate_fee(vehicle: VehicleType, entry: datetime, exit_: datetime) -> float:
    if exit_ < entry:
        raise ValueError("exit time is before entry time")
    minutes = (exit_ - entry).total_seconds() / 60
    if minutes <= GRACE_MINUTES:
        return 0.0

    full_days, remainder_min = divmod(minutes, 24 * 60)
    cap = DAILY_CAP_AED[vehicle]
    rate = HOURLY_RATE_AED[vehicle]
    partial_day_fee = min(math.ceil(remainder_min / 60) * rate, cap)
    return round(full_days * cap + partial_day_fee, 2)
