"""Core data models for the timetable scheduling engine.

Defines plain dataclasses for all domain entities: Year, Division, Batch, Subject,
Faculty, Room, TeachingAssignment, TimeSlot, SessionNode, and StudentEnrollment.
All classes use only the Python standard library and are free of ORM or metaclass logic.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class YearLevel(Enum):
    """Academic year levels in an Indian engineering college."""
    FY = "FY"   # First Year
    SY = "SY"   # Second Year
    TY = "TY"   # Third Year
    BTECH = "BTECH"  # Final Year (B.Tech)


class SessionType(Enum):
    """Type of teaching session."""
    THEORY = "theory"
    PRACTICAL = "practical"
    TUTORIAL = "tutorial"


class RoomType(Enum):
    """Type of room."""
    CLASSROOM = "classroom"
    LAB = "lab"
    SEMINAR_HALL = "seminar_hall"


@dataclass(frozen=True)
class Year:
    """Academic year (e.g., FY, SY, TY)."""
    level: YearLevel
    name: str = ""  # e.g., "First Year", "Second Year"
    
    def __post_init__(self):
        if not self.name:
            object.__setattr__(self, 'name', self.level.name)


@dataclass(frozen=True)
class Division:
    """A division within a year (e.g., FY-A, FY-B)."""
    id: str              # Unique identifier, e.g., "FY-A"
    year: Year
    name: str = ""       # Human-readable name, e.g., "FY Division A"
    
    def __post_init__(self):
        if not self.name:
            object.__setattr__(self, 'name', self.id)


@dataclass(frozen=True)
class Batch:
    """A lab batch within a division (e.g., FY-A-B1, FY-A-B2, FY-A-B3)."""
    id: str              # Unique identifier, e.g., "FY-A-B1"
    division: Division
    name: str = ""       # Human-readable name
    size: int = 0        # Number of students in this batch
    
    def __post_init__(self):
        if not self.name:
            object.__setattr__(self, 'name', self.id)


@dataclass(frozen=True)
class Subject:
    """Academic subject/course."""
    code: str            # Unique code, e.g., "CS101"
    name: str            # Full name, e.g., "Data Structures"
    credits: int = 0
    is_lab: bool = False
    weekly_hours: int = 0  # Total hours per week (theory + practical)
    theory_hours: int = 0
    practical_hours: int = 0
    tutorial_hours: int = 0


@dataclass(frozen=True)
class Faculty:
    """Faculty member with availability constraints."""
    id: str              # Unique identifier, e.g., "F001"
    name: str
    email: str = ""
    max_daily_hours: int = 6
    max_weekly_hours: int = 18
    unavailable_slots: frozenset[str] = field(default_factory=frozenset)  # Slot IDs where faculty cannot teach
    preferred_slots: frozenset[str] = field(default_factory=frozenset)    # Preferred slot IDs (soft constraint)
    
    def __post_init__(self):
        if isinstance(self.unavailable_slots, set):
            object.__setattr__(self, 'unavailable_slots', frozenset(self.unavailable_slots))
        if isinstance(self.preferred_slots, set):
            object.__setattr__(self, 'preferred_slots', frozenset(self.preferred_slots))


@dataclass(frozen=True)
class Room:
    """Physical room with type, capacity, and tags."""
    id: str              # Unique identifier, e.g., "R101", "LAB-CS-01"
    name: str
    room_type: RoomType = RoomType.CLASSROOM
    capacity: int = 60
    tags: frozenset[str] = field(default_factory=frozenset)  # e.g., {"projector", "ac", "linux"}
    
    def __post_init__(self):
        if isinstance(self.tags, set):
            object.__setattr__(self, 'tags', frozenset(self.tags))


@dataclass
class TeachingAssignment:
    """A faculty member assigned to teach a subject to a division/batch."""
    id: str                      # Unique assignment ID
    subject: Subject
    faculty: Faculty
    division: Division
    batch: Optional[Batch] = None  # None = whole division (theory); set = specific batch (lab)
    session_type: SessionType = SessionType.THEORY
    hours_per_week: int = 0      # Derived from subject, but can override
    fixed_slot: Optional[str] = None  # If pre-assigned to a specific slot ID
    allowed_slots: frozenset[str] = field(default_factory=frozenset)  # If restricted to specific slots
    
    def __post_init__(self):
        if isinstance(self.allowed_slots, set):
            object.__setattr__(self, 'allowed_slots', frozenset(self.allowed_slots))
        # Default hours_per_week from subject if not set
        if self.hours_per_week == 0:
            if self.session_type == SessionType.PRACTICAL:
                object.__setattr__(self, 'hours_per_week', self.subject.practical_hours)
            elif self.session_type == SessionType.TUTORIAL:
                object.__setattr__(self, 'hours_per_week', self.subject.tutorial_hours)
            else:
                object.__setattr__(self, 'hours_per_week', self.subject.theory_hours)


@dataclass(frozen=True)
class TimeSlot:
    """A single time slot in the weekly grid."""
    id: str                    # Unique ID, e.g., "MON-P1", "TUE-P3"
    day: int                   # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
    period: int                # 1-7 (P1..P7), lunch is between P4 and P5
    label: str = ""            # Human-readable, e.g., "Mon 09:00-10:00"
    is_lunch: bool = False
    
    def __post_init__(self):
        if not self.label:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            if self.is_lunch:
                object.__setattr__(self, 'label', f"{day_names[self.day]} Lunch")
            else:
                object.__setattr__(self, 'label', f"{day_names[self.day]}-P{self.period}")


@dataclass(frozen=True)
class SessionNode:
    """A single schedulable session node (expanded from TeachingAssignment)."""
    id: str                    # Unique node ID, e.g., "ASSIGN-001-P1"
    assignment: TeachingAssignment
    duration: int = 1          # Number of contiguous periods (1 for theory, 2 for lab)
    is_lab_start: bool = False # True if this node starts a 2-period lab block
    allowed_slots: frozenset[str] = field(default_factory=frozenset)  # Resolved allowed slots
    preassigned_slot: Optional[str] = None  # Locked slot if fixed
    
    def __post_init__(self):
        if isinstance(self.allowed_slots, set):
            object.__setattr__(self, 'allowed_slots', frozenset(self.allowed_slots))


@dataclass(frozen=True)
class StudentEnrollment:
    """Links a student (or backlog group) to divisions/batches for elective/backlog tracking."""
    student_id: str
    student_name: str = ""
    division: Optional[Division] = None
    batch: Optional[Batch] = None
    elective_subjects: frozenset[str] = field(default_factory=frozenset)  # Subject codes
    backlog_subjects: frozenset[str] = field(default_factory=frozenset)   # Subject codes
    
    def __post_init__(self):
        if isinstance(self.elective_subjects, set):
            object.__setattr__(self, 'elective_subjects', frozenset(self.elective_subjects))
        if isinstance(self.backlog_subjects, set):
            object.__setattr__(self, 'backlog_subjects', frozenset(self.backlog_subjects))


@dataclass
class ProjectData:
    """Complete project definition container for serialization."""
    years: list[Year] = field(default_factory=list)
    divisions: list[Division] = field(default_factory=list)
    batches: list[Batch] = field(default_factory=list)
    subjects: list[Subject] = field(default_factory=list)
    faculty: list[Faculty] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    teaching_assignments: list[TeachingAssignment] = field(default_factory=list)
    time_slots: list[TimeSlot] = field(default_factory=list)
    student_enrollments: list[StudentEnrollment] = field(default_factory=list)
    
    # Lookup maps (built after loading)
    _slot_by_id: dict[str, TimeSlot] = field(default_factory=dict, init=False, repr=False)
    _faculty_by_id: dict[str, Faculty] = field(default_factory=dict, init=False, repr=False)
    _room_by_id: dict[str, Room] = field(default_factory=dict, init=False, repr=False)
    _subject_by_code: dict[str, Subject] = field(default_factory=dict, init=False, repr=False)
    _division_by_id: dict[str, Division] = field(default_factory=dict, init=False, repr=False)
    _batch_by_id: dict[str, Batch] = field(default_factory=dict, init=False, repr=False)
    _assignment_by_id: dict[str, TeachingAssignment] = field(default_factory=dict, init=False, repr=False)
    
    def build_lookups(self) -> None:
        """Build internal lookup dictionaries for fast access."""
        self._slot_by_id = {s.id: s for s in self.time_slots}
        self._faculty_by_id = {f.id: f for f in self.faculty}
        self._room_by_id = {r.id: r for r in self.rooms}
        self._subject_by_code = {s.code: s for s in self.subjects}
        self._division_by_id = {d.id: d for d in self.divisions}
        self._batch_by_id = {b.id: b for b in self.batches}
        self._assignment_by_id = {a.id: a for a in self.teaching_assignments}
    
    def get_slot(self, slot_id: str) -> Optional[TimeSlot]:
        return self._slot_by_id.get(slot_id)
    
    def get_year(self, level: YearLevel) -> Optional[Year]:
        for y in self.years:
            if y.level == level:
                return y
        return None
    
    def get_faculty(self, faculty_id: str) -> Optional[Faculty]:
        return self._faculty_by_id.get(faculty_id)
    
    def get_room(self, room_id: str) -> Optional[Room]:
        return self._room_by_id.get(room_id)
    
    def get_subject(self, code: str) -> Optional[Subject]:
        return self._subject_by_code.get(code)
    
    def get_division(self, div_id: str) -> Optional[Division]:
        return self._division_by_id.get(div_id)
    
    def get_batch(self, batch_id: str) -> Optional[Batch]:
        return self._batch_by_id.get(batch_id)
    
    def get_assignment(self, assign_id: str) -> Optional[TeachingAssignment]:
        return self._assignment_by_id.get(assign_id)