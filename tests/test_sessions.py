"""Tests for timetable.engine.sessions"""

import pytest
from timetable.engine.sessions import expand_assignments_to_nodes, expand_assignment
from timetable.engine.models import (
    TeachingAssignment, SessionNode, SessionType, Subject, Faculty, Division, Batch
)
from timetable.engine.slots import SlotGrid


def create_test_setup():
    """Create basic test fixtures."""
    slot_grid = SlotGrid.create_standard()
    year = Year(level=YearLevel.FY)
    div = Division(id="FY-A", year=year)
    batch = Batch(id="FY-A-B1", division=div, size=20)
    subj_theory = Subject(code="CS101", name="Programming", weekly_hours=3, theory_hours=3)
    subj_lab = Subject(code="CS101L", name="Programming Lab", weekly_hours=2, practical_hours=2)
    fac = Faculty(id="F001", name="Dr. Smith")
    return slot_grid, year, div, batch, subj_theory, subj_lab, fac


from timetable.engine.models import Year, YearLevel, Division, Batch, Subject, Faculty


class TestExpandAssignment:
    def test_theory_expansion(self):
        slot_grid, year, div, batch, subj_theory, subj_lab, fac = create_test_setup()
        
        assign = TeachingAssignment(
            id="A001", subject=subj_theory, faculty=fac, division=div,
            session_type=SessionType.THEORY, hours_per_week=3
        )
        nodes = expand_assignment(assign, slot_grid)
        
        assert len(nodes) == 3
        for node in nodes:
            assert node.duration == 1
            assert not node.is_lab_start
            assert node.assignment == assign
    
    def test_lab_expansion(self):
        slot_grid, year, div, batch, subj_theory, subj_lab, fac = create_test_setup()
        
        assign = TeachingAssignment(
            id="A002", subject=subj_lab, faculty=fac, division=div, batch=batch,
            session_type=SessionType.PRACTICAL, hours_per_week=2
        )
        nodes = expand_assignment(assign, slot_grid)
        
        assert len(nodes) == 1  # 2 hours = 1 two-period block
        assert nodes[0].duration == 2
        assert nodes[0].is_lab_start
    
    def test_lab_4_hours(self):
        slot_grid, year, div, batch, subj_theory, subj_lab, fac = create_test_setup()
        
        subj_lab4 = Subject(code="CS101L", name="Programming Lab", weekly_hours=4, practical_hours=4)
        assign = TeachingAssignment(
            id="A003", subject=subj_lab4, faculty=fac, division=div, batch=batch,
            session_type=SessionType.PRACTICAL, hours_per_week=4
        )
        nodes = expand_assignment(assign, slot_grid)
        
        assert len(nodes) == 2  # 4 hours = 2 two-period blocks
        for node in nodes:
            assert node.duration == 2
            assert node.is_lab_start
    
    def test_zero_hours_defaults_from_subject(self):
        slot_grid, year, div, batch, subj_theory, subj_lab, fac = create_test_setup()
        
        # Subject has theory_hours=3, so hours_per_week=0 should default to 3
        assign = TeachingAssignment(
            id="A004", subject=subj_theory, faculty=fac, division=div,
            session_type=SessionType.THEORY, hours_per_week=0
        )
        nodes = expand_assignment(assign, slot_grid)
        
        # Should create 3 nodes (defaulted from subject.theory_hours)
        assert len(nodes) == 3
        for node in nodes:
            assert node.duration == 1
            assert not node.is_lab_start
    
    def test_fixed_slot_propagates(self):
        slot_grid, year, div, batch, subj_theory, subj_lab, fac = create_test_setup()
        
        assign = TeachingAssignment(
            id="A005", subject=subj_theory, faculty=fac, division=div,
            session_type=SessionType.THEORY, hours_per_week=2,
            fixed_slot="Mon-P1"
        )
        nodes = expand_assignment(assign, slot_grid)
        
        assert len(nodes) == 2
        # First node gets preassigned, second doesn't (fixed_slot is per assignment)
        assert nodes[0].preassigned_slot == "Mon-P1"


class TestExpandAssignmentsToNodes:
    def test_multiple_assignments(self):
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming", weekly_hours=3, theory_hours=3)
        fac = Faculty(id="F001", name="Dr. Smith")
        
        assigns = [
            TeachingAssignment(id="A001", subject=subj, faculty=fac, division=div, hours_per_week=2),
            TeachingAssignment(id="A002", subject=subj, faculty=fac, division=div, hours_per_week=1),
        ]
        
        nodes = expand_assignments_to_nodes(assigns, slot_grid)
        assert len(nodes) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])