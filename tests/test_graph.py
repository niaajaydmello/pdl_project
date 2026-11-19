"""Tests for timetable.engine.graph"""

import pytest
from timetable.engine.graph import ConflictGraph, ConflictType, build_conflict_graph, build_student_conflict_maps
from timetable.engine.models import (
    SessionNode, TeachingAssignment, SessionType, Subject, Faculty, Division, Batch, StudentEnrollment
)
from timetable.engine.slots import SlotGrid


def create_test_nodes():
    """Create test session nodes with known conflicts."""
    slot_grid = SlotGrid.create_standard()
    year = Year(level=YearLevel.FY)
    div_a = Division(id="FY-A", year=year)
    div_b = Division(id="FY-B", year=year)
    batch_a1 = Batch(id="FY-A-B1", division=div_a, size=20)
    batch_a2 = Batch(id="FY-A-B2", division=div_a, size=20)
    
    subj1 = Subject(code="CS101", name="Programming")
    subj2 = Subject(code="MA101", name="Math")
    
    fac1 = Faculty(id="F001", name="Dr. A")
    fac2 = Faculty(id="F002", name="Dr. B")
    
    # Theory nodes for FY-A (same division, same faculty -> conflict)
    assign1 = TeachingAssignment(id="A1", subject=subj1, faculty=fac1, division=div_a, hours_per_week=2)
    assign2 = TeachingAssignment(id="A2", subject=subj2, faculty=fac1, division=div_a, hours_per_week=2)
    assign3 = TeachingAssignment(id="A3", subject=subj1, faculty=fac2, division=div_b, hours_per_week=2)
    
    # Lab nodes for FY-A batches
    assign4 = TeachingAssignment(id="A4", subject=subj1, faculty=fac1, division=div_a, batch=batch_a1,
                                  session_type=SessionType.PRACTICAL, hours_per_week=2)
    assign5 = TeachingAssignment(id="A5", subject=subj1, faculty=fac2, division=div_a, batch=batch_a2,
                                  session_type=SessionType.PRACTICAL, hours_per_week=2)
    
    nodes = [
        SessionNode(id="A1-TH-1", assignment=assign1, duration=1),
        SessionNode(id="A1-TH-2", assignment=assign1, duration=1),
        SessionNode(id="A2-TH-1", assignment=assign2, duration=1),
        SessionNode(id="A3-TH-1", assignment=assign3, duration=1),
        SessionNode(id="A4-LAB-1", assignment=assign4, duration=2, is_lab_start=True),
        SessionNode(id="A5-LAB-1", assignment=assign5, duration=2, is_lab_start=True),
    ]
    return nodes


from timetable.engine.models import Year, YearLevel, Division, Batch, Subject, Faculty


class TestConflictGraph:
    def test_add_node_and_edge(self):
        graph = ConflictGraph()
        graph.add_node("A")
        graph.add_node("B")
        graph.add_edge("A", "B", ConflictType.FACULTY, "Same faculty")
        
        assert "A" in graph
        assert "B" in graph
        assert graph.has_edge("A", "B")
        assert graph.degree("A") == 1
        assert graph.degree("B") == 1
        assert graph.neighbors("A") == {"B"}
    
    def test_no_duplicate_edges(self):
        graph = ConflictGraph()
        graph.add_edge("A", "B", ConflictType.FACULTY, "First")
        graph.add_edge("A", "B", ConflictType.DIVISION, "Second")
        
        # Only first edge type kept
        edge = graph.get_edge("A", "B")
        assert edge.conflict_type == ConflictType.FACULTY
    
    def test_self_edge_ignored(self):
        graph = ConflictGraph()
        graph.add_edge("A", "A", ConflictType.FACULTY, "Self")
        assert not graph.has_edge("A", "A")


class TestBuildConflictGraph:
    def test_faculty_conflict(self):
        nodes = create_test_nodes()
        graph = build_conflict_graph(nodes)
        
        # A1-TH-1 and A1-TH-2 share faculty F001 -> conflict
        # A1-TH-1 and A2-TH-1 share faculty F001 -> conflict
        assert graph.has_edge("A1-TH-1", "A1-TH-2")
        assert graph.has_edge("A1-TH-1", "A2-TH-1")
        edge = graph.get_edge("A1-TH-1", "A2-TH-1")
        assert edge.conflict_type == ConflictType.FACULTY
    
    def test_division_conflict(self):
        nodes = create_test_nodes()
        graph = build_conflict_graph(nodes)
        
        # A1-TH-1 and A2-TH-1 are both FY-A theory -> division conflict
        assert graph.has_edge("A1-TH-1", "A2-TH-1")
        edge = graph.get_edge("A1-TH-1", "A2-TH-1")
        assert edge.conflict_type == ConflictType.FACULTY  # Faculty conflict takes precedence (added first)
    
    def test_batch_division_conflict(self):
        nodes = create_test_nodes()
        graph = build_conflict_graph(nodes)
        
        # A4-LAB-1 (FY-A-B1 lab) conflicts with A1-TH-1 (FY-A theory)
        assert graph.has_edge("A4-LAB-1", "A1-TH-1")
        edge = graph.get_edge("A4-LAB-1", "A1-TH-1")
        # Conflict type is FACULTY because same faculty (F001) teaches both
        # (FACULTY edge added first in build_conflict_graph)
        assert edge.conflict_type == ConflictType.FACULTY
    
    def test_no_parallel_batch_conflict(self):
        nodes = create_test_nodes()
        graph = build_conflict_graph(nodes)
        
        # A4-LAB-1 (FY-A-B1) and A5-LAB-1 (FY-A-B2) are parallel batches -> NO conflict
        assert not graph.has_edge("A4-LAB-1", "A5-LAB-1")
    
    def test_no_cross_division_conflict(self):
        nodes = create_test_nodes()
        graph = build_conflict_graph(nodes)
        
        # A3-TH-1 (FY-B) and A1-TH-1 (FY-A) different divisions, different faculty -> no conflict
        assert not graph.has_edge("A3-TH-1", "A1-TH-1")


class TestBuildStudentConflictMaps:
    def test_elective_map(self):
        nodes = create_test_nodes()
        enrollments = [
            StudentEnrollment(student_id="S1", elective_subjects=frozenset(["CS101"])),
            StudentEnrollment(student_id="S2", elective_subjects=frozenset(["MA101"])),
        ]
        elective_map, backlog_map = build_student_conflict_maps(enrollments, nodes)
        
        assert "CS101" in elective_map
        assert "S1" in elective_map["CS101"]
        assert "MA101" in elective_map
        assert "S2" in elective_map["MA101"]
        assert len(backlog_map) == 0
    
    def test_backlog_map(self):
        nodes = create_test_nodes()
        enrollments = [
            StudentEnrollment(student_id="S1", backlog_subjects=frozenset(["CS101"])),
        ]
        elective_map, backlog_map = build_student_conflict_maps(enrollments, nodes)
        
        assert "CS101" in backlog_map
        assert "S1" in backlog_map["CS101"]
        assert len(elective_map) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])