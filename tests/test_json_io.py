"""Tests for timetable.io_utils.json_io"""

import pytest
import json
import tempfile
from pathlib import Path
from timetable.io_utils.json_io import (
    save_project, load_project, save_schedule, load_schedule,
    save_colouring_result, load_colouring_result, project_to_json, json_to_project
)
from timetable.engine.models import (
    ProjectData, Year, Division, Batch, Subject, Faculty, Room,
    TeachingAssignment, TimeSlot, SessionNode, StudentEnrollment,
    YearLevel, SessionType, RoomType
)
from timetable.engine.colouring import ColouringResult
from timetable.engine.slots import SlotGrid


def create_minimal_project() -> ProjectData:
    """Create a minimal project for testing serialization."""
    project = ProjectData()
    
    year = Year(level=YearLevel.FY, name="First Year")
    div = Division(id="FY-A", year=year, name="FY Division A")
    batch = Batch(id="FY-A-B1", division=div, name="FY-A Batch 1", size=20)
    
    subj = Subject(code="CS101", name="Programming", credits=4, weekly_hours=3, theory_hours=3)
    fac = Faculty(id="F001", name="Dr. Smith", email="smith@college.edu")
    room = Room(id="R101", name="Room 101", room_type=RoomType.CLASSROOM, capacity=70)
    
    assign = TeachingAssignment(
        id="A001", subject=subj, faculty=fac, division=div,
        session_type=SessionType.THEORY, hours_per_week=3
    )
    
    slot = TimeSlot(id="Mon-P1", day=0, period=1, label="Mon P1")
    enroll = StudentEnrollment(student_id="S001", student_name="John", division=div)
    
    project.years = [year]
    project.divisions = [div]
    project.batches = [batch]
    project.subjects = [subj]
    project.faculty = [fac]
    project.rooms = [room]
    project.teaching_assignments = [assign]
    project.time_slots = [slot]
    project.student_enrollments = [enroll]
    project.build_lookups()
    
    return project


class TestProjectToJson:
    def test_serializes_all_fields(self):
        project = create_minimal_project()
        data = project_to_json(project)
        
        assert data["__type__"] == "ProjectData"
        assert len(data["years"]) == 1
        assert len(data["divisions"]) == 1
        assert len(data["batches"]) == 1
        assert len(data["subjects"]) == 1
        assert len(data["faculty"]) == 1
        assert len(data["rooms"]) == 1
        assert len(data["teaching_assignments"]) == 1
        assert len(data["time_slots"]) == 1
        assert len(data["student_enrollments"]) == 1
    
    def test_enum_serialization(self):
        project = create_minimal_project()
        data = project_to_json(project)
        
        # YearLevel enum should be serialized as value
        year_data = data["years"][0]
        assert year_data["level"] == "FY"  # YearLevel.FY.value
        
        # SessionType enum
        assign_data = data["teaching_assignments"][0]
        assert assign_data["session_type"] == "theory"
        
        # RoomType enum
        room_data = data["rooms"][0]
        assert room_data["room_type"] == "classroom"


class TestJsonToProject:
    def test_deserializes_all_fields(self):
        project = create_minimal_project()
        data = project_to_json(project)
        loaded = json_to_project(data)
        
        assert len(loaded.years) == 1
        assert loaded.years[0].level == YearLevel.FY
        assert loaded.divisions[0].id == "FY-A"
        assert loaded.batches[0].id == "FY-A-B1"
        assert loaded.subjects[0].code == "CS101"
        assert loaded.faculty[0].id == "F001"
        assert loaded.rooms[0].id == "R101"
        assert loaded.teaching_assignments[0].id == "A001"
        assert loaded.time_slots[0].id == "Mon-P1"
        assert loaded.student_enrollments[0].student_id == "S001"
    
    def test_lookups_rebuilt(self):
        project = create_minimal_project()
        data = project_to_json(project)
        loaded = json_to_project(data)
        
        # Lookups should work
        assert loaded.get_division("FY-A") is not None
        assert loaded.get_faculty("F001") is not None
        assert loaded.get_subject("CS101") is not None


class TestSaveLoadProject:
    def test_roundtrip(self):
        project = create_minimal_project()
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            save_project(project, temp_path)
            loaded = load_project(temp_path)
            
            assert len(loaded.years) == 1
            assert loaded.get_division("FY-A") is not None
            assert loaded.get_subject("CS101") is not None
        finally:
            temp_path.unlink()
    
    def test_preserves_references(self):
        """Test that object references are preserved after load."""
        project = create_minimal_project()
        original_assign = project.teaching_assignments[0]
        original_faculty = original_assign.faculty
        original_subject = original_assign.subject
        original_division = original_assign.division
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            save_project(project, temp_path)
            loaded = load_project(temp_path)
            
            loaded_assign = loaded.teaching_assignments[0]
            # References should point to canonical objects in loaded project
            assert loaded_assign.faculty is loaded.get_faculty("F001")
            assert loaded_assign.subject is loaded.get_subject("CS101")
            assert loaded_assign.division is loaded.get_division("FY-A")
        finally:
            temp_path.unlink()


class TestSaveLoadSchedule:
    def test_roundtrip(self):
        schedule = {"A1-TH-1": "Mon-P1", "A1-TH-2": "Mon-P2"}
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            save_schedule(schedule, temp_path)
            loaded = load_schedule(temp_path)
            
            assert loaded == schedule
        finally:
            temp_path.unlink()


class TestSaveLoadColouringResult:
    def test_roundtrip(self):
        result = ColouringResult(
            schedule={"A1": "Mon-P1"},
            unassigned=["A2"],
            iterations=10,
            backtracks=2
        )
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            save_colouring_result(result, temp_path)
            loaded = load_colouring_result(temp_path)
            
            assert loaded.schedule == result.schedule
            assert loaded.unassigned == result.unassigned
            assert loaded.iterations == result.iterations
            assert loaded.backtracks == result.backtracks
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])