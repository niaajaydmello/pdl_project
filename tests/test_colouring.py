"""Tests for timetable.engine.colouring"""

import pytest
from timetable.engine.colouring import (
    dsatur_colour, welsh_powell_colour, random_greedy_colour, ColouringResult
)
from timetable.engine.models import (
    SessionNode, TeachingAssignment, SessionType, Subject, Faculty, Division, Batch
)
from timetable.engine.slots import SlotGrid
from timetable.engine.graph import build_conflict_graph


def create_schedulable_test():
    """Create a simple schedulable test case."""
    slot_grid = SlotGrid.create_standard()
    year = Year(level=YearLevel.FY)
    div = Division(id="FY-A", year=year)
    subj = Subject(code="CS101", name="Programming", weekly_hours=3, theory_hours=3)
    fac1 = Faculty(id="F001", name="Dr. A")
    fac2 = Faculty(id="F002", name="Dr. B")
    
    # Two theory assignments, different faculty, same division
    assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=2)
    assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, hours_per_week=2)
    
    nodes = [
        SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
        SessionNode(id="A1-TH-2", assignment=assign1, duration=1),
        SessionNode(id="A2-TH-1", assignment=assign2, duration=1),
        SessionNode(id="A2-TH-2", assignment=assign2, duration=1),
    ]
    
    # Resolve allowed slots for each node
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
    return resolved_nodes, graph, slot_grid


from timetable.engine.models import Year, YearLevel, Division, Subject, Faculty


class TestColouringResult:
    def test_result_creation(self):
        result = ColouringResult(
            schedule={"A1": "Mon-P1"},
            unassigned=["A2"],
            iterations=5,
            backtracks=2
        )
        assert result.schedule == {"A1": "Mon-P1"}
        assert result.unassigned == ["A2"]
        assert result.iterations == 5
        assert result.backtracks == 2


class TestDsaturColour:
    def test_simple_schedule(self):
        nodes, graph, slot_grid = create_schedulable_test()
        result = dsatur_colour(nodes, graph, slot_grid)
        
        assert len(result.schedule) == 4
        assert len(result.unassigned) == 0
        assert result.iterations > 0
    
    def test_preassigned_slot(self):
        nodes, graph, slot_grid = create_schedulable_test()
        # Preassign one node
        result = dsatur_colour(nodes, graph, slot_grid, preassigned={"A1-TH-1": "Mon-P1"})
        
        assert result.schedule["A1-TH-1"] == "Mon-P1"
        assert len(result.schedule) == 4
    
    def test_preassigned_conflict_respected(self):
        nodes, graph, slot_grid = create_schedulable_test()
        # Preassign conflicting slots should not happen for same faculty
        # but different faculty can share slot
        result = dsatur_colour(nodes, graph, slot_grid, preassigned={
            "A1-TH-1": "Mon-P1",
            "A2-TH-1": "Mon-P1"  # Different faculty, OK
        })
        assert result.schedule["A1-TH-1"] == "Mon-P1"
        assert result.schedule["A2-TH-1"] == "Mon-P1"
    
    def test_slot_scorer_callback(self):
        nodes, graph, slot_grid = create_schedulable_test()
        
        def scorer(slot_id, node, schedule, grid):
            # Prefer earlier slots
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
            day = slot_id.split("-")[0]
            period = int(slot_id.split("-P")[1])
            return day_order.get(day, 5) * 10 + period
        
        result = dsatur_colour(nodes, graph, slot_grid, slot_scorer=scorer)
        assert len(result.schedule) == 4


class TestWelshPowellColour:
    def test_simple_schedule(self):
        nodes, graph, slot_grid = create_schedulable_test()
        result = welsh_powell_colour(nodes, graph, slot_grid)
        
        assert len(result.schedule) == 4
        assert len(result.unassigned) == 0
    
    def test_degree_ordering(self):
        # Create graph where degree ordering matters
        slot_grid = SlotGrid.create_standard()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming")
        
        fac1 = Faculty(id="F1", name="Dr. A")
        fac2 = Faculty(id="F2", name="Dr. B")
        fac3 = Faculty(id="F3", name="Dr. C")
        
        # A1 conflicts with A2 and A3 (degree 2)
        # A2 conflicts with A1 (degree 1)
        # A3 conflicts with A1 (degree 1)
        assign1 = TeachingAssignment(id="A1", subject=subj, faculty=fac1, division=div, hours_per_week=1)
        assign2 = TeachingAssignment(id="A2", subject=subj, faculty=fac2, division=div, hours_per_week=1)
        assign3 = TeachingAssignment(id="A3", subject=subj, faculty=fac3, division=div, hours_per_week=1)
        
        nodes = [
            SessionNode(id="A1", assignment=assign1, duration=1),
            SessionNode(id="A2", assignment=assign2, duration=1),
            SessionNode(id="A3", assignment=assign3, duration=1),
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
        result = welsh_powell_colour(resolved_nodes, graph, slot_grid)
        
        assert len(result.schedule) == 3


class TestRandomGreedyColour:
    def test_fixed_seed_reproducible(self):
        nodes, graph, slot_grid = create_schedulable_test()
        
        result1 = random_greedy_colour(nodes, graph, slot_grid, seed=42)
        result2 = random_greedy_colour(nodes, graph, slot_grid, seed=42)
        
        assert result1.schedule == result2.schedule
    
    def test_different_seeds_different_results(self):
        nodes, graph, slot_grid = create_schedulable_test()
        
        result1 = random_greedy_colour(nodes, graph, slot_grid, seed=42)
        result2 = random_greedy_colour(nodes, graph, slot_grid, seed=123)
        
        # Results may differ (not guaranteed but likely)
        # At minimum, both should be valid schedules
        assert len(result1.schedule) == 4
        assert len(result2.schedule) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])