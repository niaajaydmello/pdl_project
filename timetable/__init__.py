"""Public package for college timetable data, slot, and file utilities."""

from timetable.engine.models import (
    Assignment, Batch, CollegeDataset, Division, Faculty, Room, Subject, Year,
)
from timetable.engine.slots import TimeSlot, find_consecutive_slot_pairs, generate_slots

__all__ = [
    "Assignment", "Batch", "CollegeDataset", "Division", "Faculty", "Room",
    "Subject", "TimeSlot", "Year", "find_consecutive_slot_pairs", "generate_slots",
]
