"""Generate labeled teaching periods and identify adjacent lab blocks."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TimeSlot:
    slot_id: str
    day: str
    period: int
    label: str
    is_lab_eligible: bool = True
    lunch_boundary_before: bool = False


def generate_slots(
    days: list[str],
    periods_per_day: int,
    lunch_after_period: int | None = None,
    start_time: str = "09:00",
    period_minutes: int = 60,
    break_minutes: int = 15,
    lunch_minutes: int = 45,
) -> list[TimeSlot]:
    """Create one slot per teaching period, advancing the clock over breaks."""
    if periods_per_day < 0 or period_minutes <= 0 or break_minutes < 0 or lunch_minutes < 0:
        raise ValueError("Periods must be non-negative and durations must be valid.")
    try:
        first_start = datetime.strptime(start_time, "%H:%M")
    except ValueError as error:
        raise ValueError("start_time must use HH:MM format.") from error

    slots: list[TimeSlot] = []
    for day in days:
        current = first_start
        for period in range(1, periods_per_day + 1):
            end = current + timedelta(minutes=period_minutes)
            slot_id = f"{day[:3].upper()}-P{period}"
            slots.append(TimeSlot(
                slot_id,
                day,
                period,
                f"{current:%H:%M}-{end:%H:%M}",
                lunch_boundary_before=period > 1 and period - 1 == lunch_after_period,
            ))
            if period < periods_per_day:
                pause = lunch_minutes if period == lunch_after_period else break_minutes
                current = end + timedelta(minutes=pause)
    return slots


def find_consecutive_slot_pairs(
    slots: list[TimeSlot], length: int = 2
) -> list[tuple[TimeSlot, ...]]:
    """Return adjacent same-day slot blocks, excluding pairs across lunch."""
    if length < 1:
        raise ValueError("length must be at least 1.")
    by_day: dict[str, list[TimeSlot]] = {}
    for slot in slots:
        by_day.setdefault(slot.day, []).append(slot)
    pairs: list[tuple[TimeSlot, ...]] = []
    for day_slots in by_day.values():
        ordered = sorted(day_slots, key=lambda item: item.period)
        regular_gaps: list[int] = []
        for index in range(len(ordered) - 1):
            if ordered[index + 1].period == ordered[index].period + 1:
                _, end_text = ordered[index].label.split("-")
                start_text, _ = ordered[index + 1].label.split("-")
                end_time = datetime.strptime(end_text, "%H:%M")
                next_start = datetime.strptime(start_text, "%H:%M")
                regular_gaps.append(int((next_start - end_time).total_seconds() // 60))
        shortest_gap = min(regular_gaps) if regular_gaps else None
        for start in range(len(ordered) - length + 1):
            block = ordered[start:start + length]
            is_adjacent = all(
                block[index + 1].period == block[index].period + 1
                for index in range(length - 1)
            )
            crosses_lunch = any(block[index + 1].lunch_boundary_before for index in range(length - 1))
            crosses_long_break = False
            if is_adjacent and not crosses_lunch and shortest_gap is not None:
                for index in range(length - 1):
                    _, end_text = block[index].label.split("-")
                    start_text, _ = block[index + 1].label.split("-")
                    gap = int((datetime.strptime(start_text, "%H:%M") - datetime.strptime(end_text, "%H:%M")).total_seconds() // 60)
                    if gap > shortest_gap:
                        crosses_long_break = True
                        break
            if is_adjacent and not crosses_lunch and not crosses_long_break:
                pairs.append(tuple(block))
    return pairs
