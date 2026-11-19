"""Tests for timetable.engine.models"""

import pytest
from timetable.engine.models import (
    Year, Division, Batch, Subject, Faculty, Room,
    TeachingAssignment, TimeSlot, SessionNode, StudentEnrollment,
    YearLevel, SessionType, RoomType, ProjectData
)


class TestYear:
    def test_year_creation(self):
        fy = Year(level=YearLevel.FY, name="First Year")
        assert fy.level == YearLevel.FY
        assert fy.name == "First Year"
    
    def test_year_default_name(self):
        sy = Year(level=YearLevel.SY)
        assert sy.name == "SY"


class TestDivision:
    def test_division_creation(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year, name="FY Division A")
        assert div.id == "FY-A"
        assert div.year == year
        assert div.name == "FY Division A"
    
    def test_division_default_name(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-B", year=year)
        assert div.name == "FY-B"


class TestBatch:
    def test_batch_creation(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        batch = Batch(id="FY-A-B1", division=div, name="FY-A Batch 1", size=25)
        assert batch.id == "FY-A-B1"
        assert batch.division == div
        assert batch.size == 25


class TestSubject:
    def test_subject_creation(self):
        subj = Subject(code="CS101", name="Programming", credits=4, 
                       weekly_hours=4, theory_hours=3, practical_hours=2)
        assert subj.code == "CS101"
        assert subj.theory_hours == 3
        assert subj.practical_hours == 2
    
    def test_lab_subject(self):
        subj = Subject(code="CS101L", name="Programming Lab", credits=2,
                       weekly_hours=2, practical_hours=2, is_lab=True)
        assert subj.is_lab


class TestFaculty:
    def test_faculty_creation(self):
        fac = Faculty(id="F001", name="Dr. Smith", email="smith@college.edu",
                      max_daily_hours=6, max_weekly_hours=18)
        assert fac.id == "F001"
        assert fac.max_daily_hours == 6
    
    def test_faculty_unavailable_slots(self):
        fac = Faculty(id="F001", name="Dr. Smith", 
                      unavailable_slots=frozenset(["MON-P1", "TUE-P2"]))
        assert "MON-P1" in fac.unavailable_slots
        assert "TUE-P2" in fac.unavailable_slots


class TestRoom:
    def test_room_creation(self):
        room = Room(id="R101", name="Room 101", room_type=RoomType.CLASSROOM, capacity=70,
                    tags=frozenset(["projector", "ac"]))
        assert room.room_type == RoomType.CLASSROOM
        assert room.capacity == 70
        assert "projector" in room.tags
    
    def test_lab_room(self):
        room = Room(id="LAB1", name="Lab 1", room_type=RoomType.LAB, capacity=30)
        assert room.room_type == RoomType.LAB


class TestTeachingAssignment:
    def test_theory_assignment(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming", weekly_hours=3, theory_hours=3)
        fac = Faculty(id="F001", name="Dr. Smith")
        
        assign = TeachingAssignment(
            id="A001", subject=subj, faculty=fac, division=div,
            session_type=SessionType.THEORY, hours_per_week=3
        )
        assert assign.session_type == SessionType.THEORY
        assert assign.hours_per_week == 3
        assert assign.batch is None
    
    def test_lab_assignment(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        batch = Batch(id="FY-A-B1", division=div, size=20)
        subj = Subject(code="CS101L", name="Programming Lab", weekly_hours=2, practical_hours=2)
        fac = Faculty(id="F001", name="Dr. Smith")
        
        assign = TeachingAssignment(
            id="A002", subject=subj, faculty=fac, division=div, batch=batch,
            session_type=SessionType.PRACTICAL, hours_per_week=2
        )
        assert assign.batch == batch
        assert assign.session_type == SessionType.PRACTICAL


class TestTimeSlot:
    def test_slot_creation(self):
        slot = TimeSlot(id="MON-P1", day=0, period=1, label="Mon P1")
        assert slot.id == "MON-P1"
        assert slot.day == 0
        assert slot.period == 1
        assert not slot.is_lunch


class TestSessionNode:
    def test_theory_node(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        subj = Subject(code="CS101", name="Programming", weekly_hours=3)
        fac = Faculty(id="F001", name="Dr. Smith")
        assign = TeachingAssignment(id="A001", subject=subj, faculty=fac, division=div, hours_per_week=3)
        
        node = SessionNode(id="A001-TH-1", assignment=assign, duration=1)
        assert node.duration == 1
        assert not node.is_lab_start
    
    def test_lab_node(self):
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        batch = Batch(id="FY-A-B1", division=div)
        subj = Subject(code="CS101L", name="Programming Lab", weekly_hours=2)
        fac = Faculty(id="F001", name="Dr. Smith")
        assign = TeachingAssignment(id="A002", subject=subj, faculty=fac, division=div, batch=batch, 
                                     session_type=SessionType.PRACTICAL, hours_per_week=2)
        
        node = SessionNode(id="A002-LAB-1", assignment=assign, duration=2, is_lab_start=True)
        assert node.duration == 2
        assert node.is_lab_start


class TestStudentEnrollment:
    def test_enrollment_creation(self):
        year = Year(level=YearLevel.TY)
        div = Division(id="TY-A", year=year)
        enroll = StudentEnrollment(
            student_id="S001", student_name="John",
            division=div,
            elective_subjects=frozenset(["CS401"]),
            backlog_subjects=frozenset(["CS201"])
        )
        assert enroll.student_id == "S001"
        assert "CS401" in enroll.elective_subjects
        assert "CS201" in enroll.backlog_subjects


class TestProjectData:
    def test_project_build_lookups(self):
        project = ProjectData()
        year = Year(level=YearLevel.FY)
        div = Division(id="FY-A", year=year)
        project.years = [year]
        project.divisions = [div]
        
        project.build_lookups()
        assert project.get_division("FY-A") == div
        assert project.get_year(YearLevel.FY) == year


if __name__ == "__main__":
    pytest.main([__file__, "-v"])