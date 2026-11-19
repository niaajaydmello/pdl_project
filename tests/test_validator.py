"""Tests for timetable.engine.validator"""

import pytest
from timetable.engine.validator import validate_schedule, Violation, ValidationReport
from timetable.engine.models import (
    SessionNode, TeachingAssignment, SessionType, Subject, Faculty, Division, Batch, StudentEnrollment
)
from timetable.engine.slots import SlotGrid, generate_standard_slots
from timetable.engine.graph import build_conflict_graph
from timetable.engine.colouring import dsatur_colour


def create_valid_schedule():
    """Create a simple valid schedule for testing."""
    slot_grid = SlotGrid.create_standard()
    year = Year(level=YearLevel.FY)
    div = Division(id="FY-A", year=year)
    subj = Subject(code="CS101", name="Programming", weekly_hours=3, theory_hours=3)
    fac1 = Faculty(id="F001", name="Dr. A")
    fac2 = Faculty(id="F002", name="Dr. B")
    
    assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=2)
    assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, hours_per_week=2)
    
    nodes = [
        SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
        SessionNode(id="A1-TH-2", assignment=assign1, duration=1),
        SessionNode(id="A2-TH-1", assignment=assign2, duration=1),
        SessionNode(id="A2-TH-2", assignment=assign2, duration=1),
    ]
    
    # Resolve allowed slots
    from timetable.engine.slots import resolve_allowed_slots
    resolved_nodes = []
    for node in nodes:
        allowed = resolve_allowed_slots(node, slot_grid.slots, node.assignment.faculty, node.assignment.division)
        resolved_nodes.append(SessionNode(
            id=node.id,
            assignment=node.assignment,
            duration=node.duration,
            is_lab_start=node.is_lab_start,
            allowed_slots=allowed,
            preassigned_slot=node.preassigned_slot
        ))
    
    graph = build_conflict_graph(resolved_nodes)
    result = dsatur_colour(resolved_nodes, graph, slot_grid)
    
    return resolved_nodes, slot_grid, result.schedule, []


from timetable.engine.models import Year, YearLevel, Division, Subject, Faculty


class TestValidationReport:
    def test_report_creation(self):
        report = ValidationReport(is_valid=True)
        assert report.is_valid
        assert len(report.violations) == 0
    
    def test_add_hard_violation(self):
        report = ValidationReport(is_valid=True)
        v = Violation(code="TEST", message="Test violation", severity="hard")
        report.add_violation(v)
        assert not report.is_valid
        assert len(report.violations) == 1
    
    def test_add_soft_violation(self):
        report = ValidationReport(is_valid=True)
        v = Violation(code="TEST", message="Test violation", severity="soft")
        report.add_violation(v)
        assert report.is_valid  # Soft violations don't invalidate
        assert len(report.violations) == 1
    
    def test_to_json(self):
        report = ValidationReport(is_valid=False)
        report.add_violation(Violation(code="ERR", message="Error", severity="hard"))
        json_data = report.to_json()
        assert json_data["is_valid"] is False
        assert len(json_data["violations"]) == 1
        assert json_data["violations"][0]["code"] == "ERR"


class TestValidateSchedule:
    def test_valid_schedule_passes(self):
        nodes, slot_grid, schedule, enrollments = create_valid_schedule()
        report = validate_schedule(schedule, nodes, slot_grid, enrollments)
        
        assert report.is_valid
        assert report.stats["hard_violations"] == 0
        assert report.stats["scheduled_sessions"] == 4
    
    def test_unscheduled_session(self):
        nodes, slot_grid, schedule, enrollments = create_valid_schedule()
        # Remove one session from schedule
        incomplete_schedule = {k: v for k, v in schedule.items() if k != "A1-TH-1"}
        
        report = validate_schedule(incomplete_schedule, nodes, slot_grid, enrollments)
        
        assert not report.is_valid
        unscheduled = [v for v in report.violations if v.code == "UNSCHEDULED_SESSION"]
        assert len(unscheduled) == 1
        assert unscheduled[0].session_ids == ["A1-TH-1"]
    
    def test_invalid_slot(self):
        nodes, slot_grid, schedule, enrollments = create_valid_schedule()
        # Assign to non-existent slot
        bad_schedule = schedule.copy()
        bad_schedule["A1-TH-1"] = "Invalid-Slot"
        
        report = validate_schedule(bad_schedule, nodes, slot_grid, enrollments)
        
        assert not report.is_valid
        invalid = [v for v in report.violations if v.code == "INVALID_SLOT"]
        assert len(invalid) >= 1
    
    def test_lab_crossing_lunch(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        batch = Batch(id="FY-A-B1", division=div, size=20)
        subj = Subject(code="CS101L", name="Lab", weekly_hours=2, practical_hours=2)
        fac = Faculty(id="F001", name="Dr. A")
        
        assign = TeachingAssignment(id="A1", subject=subj, faculty=fac, division=div, batch=batch,
                                     session_type=SessionType.PRACTICAL, hours_per_week=2)
        node = SessionNode(id="A1-LAB-1", assignment=assign, duration=2, is_lab_start=True)
        
        # P4 -> crosses lunch
        schedule = {"A1-LAB-1": "Mon-P4"}
        
        report = validate_schedule(schedule, [node], slot_grid, [])
        
        assert not report.is_valid
        invalid_span = [v for v in report.violations if v.code == "INVALID_LAB_SPAN"]
        assert len(invalid_span) == 1
    
    def test_faculty_unavailable(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        fac = Faculty(id="F001", name="Dr. A", unavailable_slots=frozenset(["Mon-P1"]))
        
        assign = TeachingAssignment(id="A1", subject=subj, faculty=fac, division=div, hours_per_week=1)
        node = SessionNode(id="A1-TH-1", assignment=assign, duration=1)
        
        schedule = {"A1-TH-1": "Mon-P1"}
        
        report = validate_schedule(schedule, [node], slot_grid, [])
        
        assert not report.is_valid
        unavail = [v for v in report.violations if v.code == "FACULTY_UNAVAILABLE"]
        assert len(unavail) == 1
    
    def test_faculty_clash(self):
        nodes, slot_grid, schedule, enrollments = create_valid_schedule()
        # Force two sessions of same faculty to same slot
        bad_schedule = schedule.copy()
        bad_schedule["A1-TH-2"] = schedule["A1-TH-1"]  # Same faculty, same slot
        
        report = validate_schedule(bad_schedule, nodes, slot_grid, enrollments)
        
        assert not report.is_valid
        clash = [v for v in report.violations if v.code == "FACULTY_CLASH"]
        assert len(clash) >= 1
    
    def test_division_clash(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        
        fac1 = Faculty(id="F1", name="Dr. A")
        fac2 = Faculty(id="F2", name="Dr. B")
        
        assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=1)
        assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, hours_per_week=1)
        
        nodes = [
            SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
            SessionNode(id="A2-TH-1", assignment=assign2, duration=1),
        ]
        
        # Both at same slot -> division clash
        schedule = {"A1-TH-1": "Mon-P1", "A2-TH-1": "Mon-P1"}
        
        report = validate_schedule(schedule, nodes, slot_grid, [])
        
        assert not report.is_valid
        clash = [v for v in report.violations if v.code == "DIVISION_CLASH"]
        assert len(clash) == 1
    
    def test_batch_division_clash(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        batch = Batch(id="FY-A-B1", division=div, size=20)
        subj = Subject(code="CS101", name="Programming")
        
        fac1 = Faculty(id="F1", name="Dr. A")
        fac2 = Faculty(id="F2", name="Dr. B")
        
        # Theory for division
        assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=1)
        # Lab for batch
        assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, batch=batch,
                                      session_type=SessionType.PRACTICAL, hours_per_week=2)
        
        nodes = [
            SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
            SessionNode(id="A2-LAB-1", assignment=assign2, duration=2, is_lab_start=True),
        ]
        
        # Lab starts at Mon-P1 (uses P1,P2), theory at Mon-P1 -> clash
        schedule = {"A1-TH-1": "Mon-P1", "A2-LAB-1": "Mon-P1"}
        
        report = validate_schedule(schedule, nodes, slot_grid, [])
        
        assert not report.is_valid
        clash = [v for v in report.violations if v.code == "BATCH_DIVISION_CLASH"]
        assert len(clash) == 1
    
    def test_student_clash(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.TY)
        div = Division(id="TY-A", year=year)
        subj = Subject(code="CS401", name="Elective")
        
        fac1 = Faculty(id="F1", name="Dr. A")
        fac2 = Faculty(id="F2", name="Dr. B")
        
        assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=1)
        assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, hours_per_week=1)
        
        nodes = [
            SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
            SessionNode(id="A2-TH-1", assignment=assign2, duration=1),
        ]
        
        enrollments = [
            StudentEnrollment(student_id="S1", elective_subjects=frozenset(["CS401"])),
        ]
        
        # Both electives at same slot -> student clash
        schedule = {"A1-TH-1": "Mon-P1", "A2-TH-1": "Mon-P1"}
        
        report = validate_schedule(schedule, nodes, slot_grid, enrollments)
        
        assert not report.is_valid
        clash = [v for v in report.violations if v.code == "STUDENT_CLASH"]
        assert len(clash) == 1
    
    def test_faculty_daily_cap(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        fac = Faculty(id="F1", name="Dr. A", max_daily_hours=2)
        
        # Create 3 sessions for same faculty on same day
        assigns = [TeachingAssignment(id=f"A{i}", subject=subj, faculty=fac, division=div, hours_per_week=1) for i in range(3)]
        nodes = [SessionNode(id=f"A{i}-TH-1", assignment=a, duration=1) for i, a in enumerate(assigns)]
        
        # Schedule all on Mon (Mon-P1, Mon-P2, Mon-P3) -> 3 hours > cap of 2
        schedule = {"A0-TH-1": "Mon-P1", "A1-TH-1": "Mon-P2", "A2-TH-1": "Mon-P3"}
        
        report = validate_schedule(schedule, nodes, slot_grid, [])
        
        assert not report.is_valid
        cap = [v for v in report.violations if v.code == "FACULTY_DAILY_CAP_EXCEEDED"]
        assert len(cap) == 1
        assert cap[0].details["hours"] == 3
        assert cap[0].details["cap"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])