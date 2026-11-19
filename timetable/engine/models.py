"""Plain dataclasses for college timetable entities and JSON serialization."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Year:
    year_id: str
    name: str
    level: int


@dataclass
class Division:
    division_id: str
    year_id: str
    name: str


@dataclass
class Batch:
    batch_id: str
    division_id: str
    name: str


@dataclass
class Subject:
    subject_id: str
    name: str
    year_id: str
    theory_hours: int = 0
    practical_hours: int = 0
    is_elective: bool = False
    lab_periods: int = 2


@dataclass
class Faculty:
    faculty_id: str
    name: str
    department: str = ""
    max_daily_hours: int = 4
    max_weekly_hours: int = 18
    unavailable_slots: list[str] = field(default_factory=list)


@dataclass
class Room:
    room_id: str
    name: str
    room_type: str
    capacity: int = 60


@dataclass
class Assignment:
    assignment_id: str
    subject_id: str
    faculty_id: str
    year_id: str
    division_id: str
    batch_id: str | None = None
    session_type: str = "theory"
    hours_per_week: int = 1
    preferred_room_id: str | None = None
    locked_slots: list[str] = field(default_factory=list)


@dataclass
class CollegeDataset:
    years: list[Year] = field(default_factory=list)
    divisions: list[Division] = field(default_factory=list)
    batches: list[Batch] = field(default_factory=list)
    subjects: list[Subject] = field(default_factory=list)
    faculty: list[Faculty] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    days: list[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    periods_per_day: int = 6
    lunch_after_period: int | None = 3
    include_saturday: bool = False
    rules: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary of this dataset."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollegeDataset":
        """Build a dataset from dictionaries, including each entity list."""
        return cls(
            years=[Year(**item) for item in data.get("years", [])],
            divisions=[Division(**item) for item in data.get("divisions", [])],
            batches=[Batch(**item) for item in data.get("batches", [])],
            subjects=[Subject(**item) for item in data.get("subjects", [])],
            faculty=[Faculty(**item) for item in data.get("faculty", [])],
            rooms=[Room(**item) for item in data.get("rooms", [])],
            assignments=[Assignment(**item) for item in data.get("assignments", [])],
            days=list(data.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])),
            periods_per_day=data.get("periods_per_day", 6),
            lunch_after_period=data.get("lunch_after_period", 3),
            include_saturday=data.get("include_saturday", False),
            rules=dict(data.get("rules", {})),
            metadata=dict(data.get("metadata", {})),
        )
