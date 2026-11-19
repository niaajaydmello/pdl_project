"""Independent schedule validator.

100% independent - shares ZERO helper functions with graph.py or colouring.py.
Validates: unscheduled sessions, invalid/lunch-crossing multi-period spans,
disallowed slots, faculty unavailability, faculty clashes, division clashes,
batch clashes, batch<->division clashes, student clashes, optional room clashes,
faculty daily/weekly hour caps. Returns JSON-serialisable report.
"""

from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
from timetable.engine.models import (
    SessionNode, TimeSlot, TeachingAssignment, Faculty, Division, Batch,
    Room, StudentEnrollment, SessionType, RoomType
)
from timetable.engine.slots import generate_standard_slots, get_lab_block_slots


@dataclass
class Violation:
    """A single schedule violation."""
    code: str                    # Machine-readable code
    message: str                 # Human-readable description
    severity: str = "hard"       # "hard" or "soft"
    session_ids: list[str] = field(default_factory=list)
    slot_ids: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report."""
    is_valid: bool
    violations: list[Violation] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    
    def add_violation(self, violation: Violation) -> None:
        self.violations.append(violation)
        if violation.severity == "hard":
            self.is_valid = False
    
    def to_json(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "violations": [
                {
                    "code": v.code,
                    "message": v.message,
                    "severity": v.severity,
                    "session_ids": v.session_ids,
                    "slot_ids": v.slot_ids,
                    "details": v.details,
                }
                for v in self.violations
            ],
            "stats": self.stats,
        }


def validate_schedule(
    schedule: dict[str, str],
    nodes: list[SessionNode],
    slot_grid: 'SlotGrid',
    student_enrollments: list[StudentEnrollment] = None,
    rooms: dict[str, Room] = None,           # session_id -> Room (if assigned)
    check_room_conflicts: bool = False,
    check_room_capacity: bool = False,
    check_room_type: bool = False,
    check_room_tags: bool = False,
) -> ValidationReport:
    """Validate a complete schedule independently.
    
    Args:
        schedule: session_id -> start_slot_id mapping
        nodes: All SessionNode objects
        slot_grid: SlotGrid with standard slots
        student_enrollments: Optional student enrollments for elective/backlog checks
        rooms: Optional session_id -> Room mapping for room checks
        check_room_conflicts: Enable room double-booking check
        check_room_capacity: Enable room capacity check
        check_room_type: Enable room type match check (lab needs lab room)
        check_room_tags: Enable room tags check
        
    Returns:
        ValidationReport with all violations
    """
    report = ValidationReport(is_valid=True)
    node_by_id = {n.id: n for n in nodes}
    slot_by_id = {s.id: s for s in slot_grid.slots}
    
    # Precompute standard slots for reference
    standard_slots = set(slot_by_id.keys())
    
    # Track occupancy for clash detection
    faculty_occupancy: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    # faculty_id -> slot_id -> [session_ids]
    division_occupancy: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    batch_occupancy: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    room_occupancy: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    student_occupancy: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    # student_id -> slot_id -> [session_ids]
    
    # Build student -> subjects map for elective/backlog conflicts
    student_subjects: dict[str, set[str]] = defaultdict(set)
    if student_enrollments:
        for enroll in student_enrollments:
            for subj in enroll.elective_subjects:
                student_subjects[enroll.student_id].add(subj)
            for subj in enroll.backlog_subjects:
                student_subjects[enroll.student_id].add(subj)
    
    # Stats
    total_sessions = len(nodes)
    scheduled_sessions = 0
    total_hours = 0
    
    # --- Pass 1: Basic checks per session ---
    for node in nodes:
        node_id = node.id
        assignment = node.assignment
        
        if node_id not in schedule:
            report.add_violation(Violation(
                code="UNSCHEDULED_SESSION",
                message=f"Session {node_id} is not scheduled",
                severity="hard",
                session_ids=[node_id],
            ))
            continue
        
        scheduled_sessions += 1
        start_slot_id = schedule[node_id]
        
        # Check slot exists
        if start_slot_id not in slot_by_id:
            report.add_violation(Violation(
                code="INVALID_SLOT",
                message=f"Session {node_id} assigned to non-existent slot {start_slot_id}",
                severity="hard",
                session_ids=[node_id],
                slot_ids=[start_slot_id],
            ))
            continue
        
        # Get occupied block
        if node.duration > 1:
            block = get_lab_block_slots(start_slot_id, slot_grid.slots)
            if len(block) != node.duration:
                report.add_violation(Violation(
                    code="INVALID_LAB_SPAN",
                    message=f"Lab session {node_id} at {start_slot_id} crosses day boundary or lunch",
                    severity="hard",
                    session_ids=[node_id],
                    slot_ids=[start_slot_id] + block[1:],
                ))
                continue
        else:
            block = [start_slot_id]
        
        # Check all slots in block are valid teaching slots (not lunch)
        for slot_id in block:
            if slot_id not in standard_slots:
                report.add_violation(Violation(
                    code="LUNCH_CROSSING",
                    message=f"Session {node_id} occupies lunch/non-teaching slot {slot_id}",
                    severity="hard",
                    session_ids=[node_id],
                    slot_ids=[slot_id],
                ))
        
        # Check disallowed slots
        for slot_id in block:
            if slot_id not in node.allowed_slots:
                report.add_violation(Violation(
                    code="DISALLOWED_SLOT",
                    message=f"Session {node_id} placed in disallowed slot {slot_id}",
                    severity="hard",
                    session_ids=[node_id],
                    slot_ids=[slot_id],
                    details={"allowed_slots": list(node.allowed_slots)},
                ))
        
        # Check faculty unavailability
        faculty = assignment.faculty
        for slot_id in block:
            if slot_id in faculty.unavailable_slots:
                report.add_violation(Violation(
                    code="FACULTY_UNAVAILABLE",
                    message=f"Faculty {faculty.id} unavailable at {slot_id} for session {node_id}",
                    severity="hard",
                    session_ids=[node_id],
                    slot_ids=[slot_id],
                    details={"faculty_id": faculty.id, "faculty_name": faculty.name},
                ))
        
        # Track occupancy for clash detection
        for slot_id in block:
            faculty_occupancy[faculty.id][slot_id].append(node_id)
            division_occupancy[assignment.division.id][slot_id].append(node_id)
            if assignment.batch:
                batch_occupancy[assignment.batch.id][slot_id].append(node_id)
            
            # Student occupancy for electives/backlogs
            if student_enrollments:
                subject_code = assignment.subject.code
                for student_id, subjects in student_subjects.items():
                    if subject_code in subjects:
                        student_occupancy[student_id][slot_id].append(node_id)
        
        # Room checks
        if rooms and node_id in rooms:
            room = rooms[node_id]
            for slot_id in block:
                room_occupancy[room.id][slot_id].append(node_id)
            
            # Room capacity
            if check_room_capacity:
                expected_students = assignment.batch.size if assignment.batch else assignment.division.size
                # Division size would need to be computed from batches
                if hasattr(assignment.division, 'size') and assignment.division.size > room.capacity:
                    report.add_violation(Violation(
                        code="ROOM_CAPACITY_EXCEEDED",
                        message=f"Room {room.id} capacity {room.capacity} < division size {assignment.division.size}",
                        severity="soft",
                        session_ids=[node_id],
                        details={"room_id": room.id, "capacity": room.capacity},
                    ))
                elif assignment.batch and assignment.batch.size > room.capacity:
                    report.add_violation(Violation(
                        code="ROOM_CAPACITY_EXCEEDED",
                        message=f"Room {room.id} capacity {room.capacity} < batch size {assignment.batch.size}",
                        severity="soft",
                        session_ids=[node_id],
                        details={"room_id": room.id, "capacity": room.capacity},
                    ))
            
            # Room type match
            if check_room_type and node.duration > 1 and room.room_type != RoomType.LAB:
                report.add_violation(Violation(
                    code="ROOM_TYPE_MISMATCH",
                    message=f"Lab session {node_id} assigned to non-lab room {room.id}",
                    severity="hard",
                    session_ids=[node_id],
                    details={"room_id": room.id, "room_type": room.room_type.value},
                ))
            
            # Room tags (placeholder for specific requirements)
            if check_room_tags:
                pass  # Could check for required tags like "projector", "ac", etc.
        
        # Track hours for faculty caps
        total_hours += node.duration
    
    # --- Pass 2: Clash detection from occupancy maps ---
    
    # Faculty clashes
    for faculty_id, slots in faculty_occupancy.items():
        for slot_id, sessions in slots.items():
            if len(sessions) > 1:
                report.add_violation(Violation(
                    code="FACULTY_CLASH",
                    message=f"Faculty {faculty_id} double-booked at {slot_id}: {sessions}",
                    severity="hard",
                    session_ids=sessions,
                    slot_ids=[slot_id],
                    details={"faculty_id": faculty_id},
                ))
    
    # Division clashes (theory vs theory)
    for div_id, slots in division_occupancy.items():
        for slot_id, sessions in slots.items():
            if len(sessions) > 1:
                # Check if all are division-level (no batch) - those conflict
                div_sessions = [s for s in sessions if node_by_id[s].assignment.batch is None]
                if len(div_sessions) > 1:
                    report.add_violation(Violation(
                        code="DIVISION_CLASH",
                        message=f"Division {div_id} double-booked at {slot_id}: {div_sessions}",
                        severity="hard",
                        session_ids=div_sessions,
                        slot_ids=[slot_id],
                        details={"division_id": div_id},
                    ))
    
    # Batch clashes (parallel batches should not clash, but same batch double-booked)
    for batch_id, slots in batch_occupancy.items():
        for slot_id, sessions in slots.items():
            if len(sessions) > 1:
                report.add_violation(Violation(
                    code="BATCH_CLASH",
                    message=f"Batch {batch_id} double-booked at {slot_id}: {sessions}",
                    severity="hard",
                    session_ids=sessions,
                    slot_ids=[slot_id],
                    details={"batch_id": batch_id},
                ))
    
    # Batch-Division clashes (batch lab vs division theory)
    for div_id, div_slots in division_occupancy.items():
        div_theory_sessions = {
            slot_id: [s for s in sessions if node_by_id[s].assignment.batch is None]
            for slot_id, sessions in div_slots.items()
        }
        # Check batch occupancy for this division's batches
        for batch_id, batch_slots in batch_occupancy.items():
            # Get first session to find the batch object
            first_slot_sessions = next(iter(batch_slots.values())) if batch_slots else []
            batch = node_by_id[first_slot_sessions[0]].assignment.batch if first_slot_sessions else None
            if batch and batch.division.id == div_id:
                for slot_id, batch_sessions in batch_slots.items():
                    div_sessions = div_theory_sessions.get(slot_id, [])
                    if div_sessions and batch_sessions:
                        report.add_violation(Violation(
                            code="BATCH_DIVISION_CLASH",
                            message=f"Batch {batch_id} lab clashes with division {div_id} theory at {slot_id}",
                            severity="hard",
                            session_ids=batch_sessions + div_sessions,
                            slot_ids=[slot_id],
                            details={"division_id": div_id, "batch_id": batch_id},
                        ))
    
    # Student clashes (electives/backlogs)
    for student_id, slots in student_occupancy.items():
        for slot_id, sessions in slots.items():
            if len(sessions) > 1:
                report.add_violation(Violation(
                    code="STUDENT_CLASH",
                    message=f"Student {student_id} has conflicting sessions at {slot_id}: {sessions}",
                    severity="hard",
                    session_ids=sessions,
                    slot_ids=[slot_id],
                    details={"student_id": student_id},
                ))
    
    # Room clashes
    if check_room_conflicts:
        for room_id, slots in room_occupancy.items():
            for slot_id, sessions in slots.items():
                if len(sessions) > 1:
                    report.add_violation(Violation(
                        code="ROOM_CLASH",
                        message=f"Room {room_id} double-booked at {slot_id}: {sessions}",
                        severity="hard",
                        session_ids=sessions,
                        slot_ids=[slot_id],
                        details={"room_id": room_id},
                    ))
    
    # --- Pass 3: Faculty daily/weekly hour caps ---
    faculty_daily_hours: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    faculty_weekly_hours: dict[str, int] = defaultdict(int)
    
    for node in nodes:
        if node.id not in schedule:
            continue
        start_slot_id = schedule[node.id]
        if node.duration > 1:
            block = get_lab_block_slots(start_slot_id, slot_grid.slots)
        else:
            block = [start_slot_id]
        
        faculty = node.assignment.faculty
        for slot_id in block:
            if slot_id not in slot_by_id:
                continue  # Skip invalid slots (shouldn't happen if schedule is valid)
            slot = slot_by_id[slot_id]
            faculty_daily_hours[faculty.id][slot.day] += 1
            faculty_weekly_hours[faculty.id] += 1
    
    for faculty_id, daily in faculty_daily_hours.items():
        faculty = next((n.assignment.faculty for n in nodes if n.assignment.faculty.id == faculty_id), None)
        if faculty:
            for day, hours in daily.items():
                if hours > faculty.max_daily_hours:
                    report.add_violation(Violation(
                        code="FACULTY_DAILY_CAP_EXCEEDED",
                        message=f"Faculty {faculty_id} exceeds daily cap on day {day}: {hours} > {faculty.max_daily_hours}",
                        severity="hard",
                        details={"faculty_id": faculty_id, "day": day, "hours": hours, "cap": faculty.max_daily_hours},
                    ))
            weekly = faculty_weekly_hours[faculty_id]
            if weekly > faculty.max_weekly_hours:
                report.add_violation(Violation(
                    code="FACULTY_WEEKLY_CAP_EXCEEDED",
                    message=f"Faculty {faculty_id} exceeds weekly cap: {weekly} > {faculty.max_weekly_hours}",
                    severity="hard",
                    details={"faculty_id": faculty_id, "hours": weekly, "cap": faculty.max_weekly_hours},
                ))
    
    # Stats
    report.stats = {
        "total_sessions": total_sessions,
        "scheduled_sessions": scheduled_sessions,
        "unscheduled_sessions": total_sessions - scheduled_sessions,
        "total_hours": total_hours,
        "hard_violations": sum(1 for v in report.violations if v.severity == "hard"),
        "soft_violations": sum(1 for v in report.violations if v.severity == "soft"),
    }
    
    return report