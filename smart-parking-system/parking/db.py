"""SQLite persistence layer."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Slot, SlotSize, Ticket, VehicleType

SCHEMA = """
CREATE TABLE IF NOT EXISTS slots (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    level   INTEGER NOT NULL,
    number  INTEGER NOT NULL,
    size    INTEGER NOT NULL CHECK (size IN (1, 2, 3)),
    UNIQUE (level, number)
);

CREATE TABLE IF NOT EXISTS tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plate         TEXT    NOT NULL,
    vehicle_type  TEXT    NOT NULL,
    slot_id       INTEGER NOT NULL REFERENCES slots(id),
    entry_time    TEXT    NOT NULL,
    exit_time     TEXT,
    fee           REAL
);

-- A plate and a slot can each have at most one open ticket.
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_plate ON tickets(plate) WHERE exit_time IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_slot  ON tickets(slot_id) WHERE exit_time IS NULL;
CREATE INDEX IF NOT EXISTS ix_tickets_exit ON tickets(exit_time);
"""


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    # ---- slots -----------------------------------------------------------
    def add_slot(self, level: int, number: int, size: SlotSize) -> None:
        self.conn.execute(
            "INSERT INTO slots(level, number, size) VALUES (?, ?, ?)", (level, number, int(size))
        )

    def slot_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0]

    def free_slots(self, min_size: SlotSize) -> list[Slot]:
        """Free slots big enough, best fit first: smallest size, lowest level, lowest number."""
        rows = self.conn.execute(
            """
            SELECT s.* FROM slots s
            WHERE s.size >= ?
              AND NOT EXISTS (SELECT 1 FROM tickets t WHERE t.slot_id = s.id AND t.exit_time IS NULL)
            ORDER BY s.size, s.level, s.number
            """,
            (int(min_size),),
        ).fetchall()
        return [Slot(r["id"], r["level"], r["number"], SlotSize(r["size"])) for r in rows]

    def get_slot(self, slot_id: int) -> Slot:
        r = self.conn.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
        return Slot(r["id"], r["level"], r["number"], SlotSize(r["size"]))

    # ---- tickets ---------------------------------------------------------
    def open_ticket(self, plate: str, vehicle: VehicleType, slot_id: int, entry: datetime) -> int:
        cur = self.conn.execute(
            "INSERT INTO tickets(plate, vehicle_type, slot_id, entry_time) VALUES (?, ?, ?, ?)",
            (plate, vehicle.value, slot_id, entry.isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def close_ticket(self, ticket_id: int, exit_: datetime, fee: float) -> None:
        self.conn.execute(
            "UPDATE tickets SET exit_time = ?, fee = ? WHERE id = ?",
            (exit_.isoformat(), fee, ticket_id),
        )
        self.conn.commit()

    def active_ticket_by_plate(self, plate: str) -> Ticket | None:
        r = self.conn.execute(
            "SELECT * FROM tickets WHERE plate = ? AND exit_time IS NULL", (plate,)
        ).fetchone()
        return self._ticket(r) if r else None

    def get_ticket(self, ticket_id: int) -> Ticket | None:
        r = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._ticket(r) if r else None

    def active_tickets(self) -> list[Ticket]:
        rows = self.conn.execute(
            "SELECT * FROM tickets WHERE exit_time IS NULL ORDER BY entry_time"
        ).fetchall()
        return [self._ticket(r) for r in rows]

    def _ticket(self, r: sqlite3.Row) -> Ticket:
        return Ticket(
            id=r["id"],
            plate=r["plate"],
            vehicle_type=VehicleType(r["vehicle_type"]),
            slot_id=r["slot_id"],
            slot_label=self.get_slot(r["slot_id"]).label,
            entry_time=datetime.fromisoformat(r["entry_time"]),
            exit_time=datetime.fromisoformat(r["exit_time"]) if r["exit_time"] else None,
            fee=r["fee"],
        )

    # ---- reporting -------------------------------------------------------
    def occupancy_by_size(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT s.size,
                   COUNT(*) AS total,
                   SUM(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) AS occupied
            FROM slots s
            LEFT JOIN tickets t ON t.slot_id = s.id AND t.exit_time IS NULL
            GROUP BY s.size ORDER BY s.size
            """
        ).fetchall()

    def revenue(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT vehicle_type,
                   COUNT(*)              AS visits,
                   ROUND(SUM(fee), 2)    AS revenue,
                   ROUND(AVG((julianday(exit_time) - julianday(entry_time)) * 24), 2) AS avg_hours
            FROM tickets
            WHERE exit_time IS NOT NULL AND exit_time >= ? AND exit_time < ?
            GROUP BY vehicle_type ORDER BY revenue DESC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
