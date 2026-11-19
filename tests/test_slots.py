"""Tests for timetable.engine.slots"""

import pytest
from timetable.engine.slots import (
    generate_standard_slots, get_next_slot_id, is_lab_start, 
    get_lab_block_slots, resolve_allowed_slots, SlotGrid
)
from timetable.engine.models import (
    TimeSlot, TeachingAssignment, SessionNode, Faculty, Division, Batch, SessionType
)


class TestGenerateStandardSlots:
    def test_slot_count(self):
        slots = generate_standard_slots()
        # 5 days * 7 periods = 35 slots
        assert len(slots) == 35
    
    def test_slot_ids(self):
        slots = generate_standard_slots()
        ids = {s.id for s in slots}
        assert "Mon-P1" in ids
        assert "Mon-P7" in ids
        assert "Fri-P7" in ids
        assert "Mon-P8" not in ids
    
    def test_no_lunch_slots(self):
        slots = generate_standard_slots()
        for s in slots:
            assert not s.is_lunch
            assert s.period >= 1 and s.period <= 7


class TestGetNextSlotId:
    def test_next_slot_same_day(self):
        slots = generate_standard_slots()
        assert get_next_slot_id("Mon-P1", slots) == "Mon-P2"
        assert get_next_slot_id("Mon-P3", slots) == "Mon-P4"
    
    def test_no_next_after_p7(self):
        slots = generate_standard_slots()
        assert get_next_slot_id("Mon-P7", slots) is None
    
    def test_no_cross_lunch(self):
        slots = generate_standard_slots()
        # P4 -> P5 crosses lunch
        assert get_next_slot_id("Mon-P4", slots) is None
    
    def test_invalid_slot(self):
        slots = generate_standard_slots()
        assert get_next_slot_id("Invalid-P1", slots) is None


class TestIsLabStart:
    def test_valid_lab_starts(self):
        slots = generate_standard_slots()
        # P1-P3 can start 2-period labs (P1->P2, P2->P3, P3->P4)
        # P5-P6 can start labs after lunch (P5->P6, P6->P7)
        assert is_lab_start("Mon-P1", slots)
        assert is_lab_start("Mon-P2", slots)
        assert is_lab_start("Mon-P3", slots)
        assert is_lab_start("Mon-P5", slots)
        assert is_lab_start("Mon-P6", slots)
    
    def test_invalid_lab_starts(self):
        slots = generate_standard_slots()
        # P4 crosses lunch, P7 is last period
        assert not is_lab_start("Mon-P4", slots)
        assert not is_lab_start("Mon-P7", slots)


class TestGetLabBlockSlots:
    def test_valid_block(self):
        slots = generate_standard_slots()
        block = get_lab_block_slots("Mon-P1", slots)
        assert block == ["Mon-P1", "Mon-P2"]
    
    def test_invalid_start_returns_empty(self):
        slots = generate_standard_slots()
        assert get_lab_block_slots("Mon-P4", slots) == []
        assert get_lab_block_slots("Mon-P7", slots) == []


class TestResolveAllowedSlots:
    def test_base_allowed_slots(self):
        slots = generate_standard_slots()
        slot_ids = {s.id for s in slots}
        
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        fac = Faculty(id="F001", name="Dr. Smith", unavailable_slots=frozenset(["Mon-P1"]))
        assign = TeachingAssignment(id="A001", subject=subj, faculty=fac, division=div, hours_per_week=3)
        node = SessionNode(id="A001-TH-1", assignment=assign, duration=1)
        
        allowed = resolve_allowed_slots(node, slots, fac, div)
        assert "Mon-P1" not in allowed  # Faculty unavailable
        assert "Mon-P2" in allowed
    
    def test_preassigned_slot_only(self):
        slots = generate_standard_slots()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        fac = Faculty(id="F001", name="Dr. Smith")
        assign = TeachingAssignment(id="A001", subject=subj, faculty=fac, division=div, hours_per_week=3)
        node = SessionNode(id="A001-TH-1", assignment=assign, duration=1, preassigned_slot="Mon-P3")
        
        allowed = resolve_allowed_slots(node, slots, fac, div)
        assert allowed == frozenset(["Mon-P3"])
    
    def test_lab_only_allowed_lab_starts(self):
        slots = generate_standard_slots()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101L", name="Programming Lab")
        fac = Faculty(id="F001", name="Dr. Smith")
        assign = TeachingAssignment(id="A002", subject=subj, faculty=fac, division=div, 
                                     session_type=SessionType.PRACTICAL, hours_per_week=2)
        node = SessionNode(id="A002-LAB-1", assignment=assign, duration=2, is_lab_start=True)
        
        allowed = resolve_allowed_slots(node, slots, fac, div)
        # Only lab start slots allowed
        for slot_id in allowed:
            assert is_lab_start(slot_id, slots)


class TestSlotGrid:
    def test_create_standard(self):
        grid = SlotGrid.create_standard()
        assert len(grid.slots) == 35
        assert len(grid.slot_by_id) == 35
        assert len(grid.lab_start_slots) == 25  # 5 days * 5 valid starts (P1, P2, P3, P5, P6)
    
    def test_next_slot(self):
        grid = SlotGrid.create_standard()
        assert grid.next_slot("Mon-P1") == "Mon-P2"
        assert grid.next_slot("Mon-P4") is None
    
    def test_lab_block(self):
        grid = SlotGrid.create_standard()
        assert grid.lab_block("Mon-P1") == ["Mon-P1", "Mon-P2"]
        assert grid.lab_block("Mon-P4") == []


# Need to import Year, Division, Subject, Faculty, TeachingAssignment, SessionNode, SessionType
from timetable.engine.models import Year, YearLevel, Division, Subject, Faculty, TeachingAssignment, SessionNode, SessionType


if __name__ == "__main__":
    pytest.main([__file__, "-v"])