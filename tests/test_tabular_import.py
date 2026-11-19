"""Tests for timetable.io_utils.tabular_import"""

import pytest
import csv
import tempfile
from pathlib import Path
from timetable.io_utils.tabular_import import (
    import_faculty_csv, import_subjects_csv, read_csv_rows,
    import_faculty_excel, import_subjects_excel, import_divisions_batches_excel,
    ImportResult
)
from timetable.engine.models import Faculty, Subject, Year, Division, Batch, YearLevel


class TestReadCsvRows:
    def test_reads_csv_with_headers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            f.write("id,name,value\n")
            f.write("1,Alice,100\n")
            f.write("2,Bob,200\n")
            temp_path = Path(f.name)
        
        try:
            rows = read_csv_rows(temp_path)
            assert len(rows) == 2
            assert rows[0]["id"] == "1"
            assert rows[0]["name"] == "Alice"
            assert rows[1]["id"] == "2"
        finally:
            temp_path.unlink()
    
    def test_empty_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            f.write("id,name\n")
            temp_path = Path(f.name)
        
        try:
            rows = read_csv_rows(temp_path)
            assert len(rows) == 0
        finally:
            temp_path.unlink()


class TestImportFacultyCsv:
    def test_imports_faculty_with_unavailable_slots(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "email", "max_daily_hours", "max_weekly_hours", 
                            "unavailable_slots", "preferred_slots"])
            writer.writerow(["F001", "Dr. A", "a@college.edu", "6", "18", "Mon-P1;Mon-P2", "Tue-P3"])
            writer.writerow(["F002", "Dr. B", "b@college.edu", "5", "16", "", ""])
            temp_path = Path(f.name)
        
        try:
            result = import_faculty_csv(temp_path)
            
            assert len(result.errors) == 0
            assert len(result.faculty) == 2
            
            fac1 = result.faculty[0]
            assert fac1.id == "F001"
            assert fac1.name == "Dr. A"
            assert fac1.unavailable_slots == frozenset(["Mon-P1", "Mon-P2"])
            assert fac1.preferred_slots == frozenset(["Tue-P3"])
            
            fac2 = result.faculty[1]
            assert fac2.unavailable_slots == frozenset()
            assert fac2.preferred_slots == frozenset()
        finally:
            temp_path.unlink()
    
    def test_handles_invalid_rows(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "email", "max_daily_hours", "max_weekly_hours",
                            "unavailable_slots", "preferred_slots"])
            writer.writerow(["F001", "Dr. A", "a@college.edu", "6", "18", "", ""])
            writer.writerow(["", "Dr. B", "b@college.edu", "5", "16", "", ""])  # Missing id
            temp_path = Path(f.name)
        
        try:
            result = import_faculty_csv(temp_path)
            
            # Both rows are imported (empty id becomes empty string)
            assert len(result.faculty) == 2
            assert result.faculty[0].id == "F001"
            assert result.faculty[1].id == ""
        finally:
            temp_path.unlink()


class TestImportSubjectsCsv:
    def test_imports_subjects(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["code", "name", "credits", "is_lab", "weekly_hours", 
                            "theory_hours", "practical_hours", "tutorial_hours"])
            writer.writerow(["CS101", "Programming", "4", "false", "4", "3", "0", "1"])
            writer.writerow(["CS101L", "Programming Lab", "2", "true", "2", "0", "2", "0"])
            temp_path = Path(f.name)
        
        try:
            result = import_subjects_csv(temp_path)
            
            assert len(result.errors) == 0
            assert len(result.subjects) == 2
            
            subj1 = result.subjects[0]
            assert subj1.code == "CS101"
            assert subj1.theory_hours == 3
            assert not subj1.is_lab
            
            subj2 = result.subjects[1]
            assert subj2.code == "CS101L"
            assert subj2.is_lab
            assert subj2.practical_hours == 2
        finally:
            temp_path.unlink()


class TestImportFacultyExcel:
    def test_imports_from_excel(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Faculty"
        ws.append(["id", "name", "email", "max_daily_hours", "max_weekly_hours",
                  "unavailable_slots", "preferred_slots"])
        ws.append(["F001", "Dr. A", "a@college.edu", 6, 18, "Mon-P1", "Tue-P3"])
        ws.append(["F002", "Dr. B", "b@college.edu", 5, 16, "", ""])
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            wb.save(temp_path)
            result = import_faculty_excel(temp_path, "Faculty")
            
            assert len(result.errors) == 0
            assert len(result.faculty) == 2
            assert result.faculty[0].unavailable_slots == frozenset(["Mon-P1"])
        finally:
            temp_path.unlink()


class TestImportSubjectsExcel:
    def test_imports_from_excel(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Subjects"
        ws.append(["code", "name", "credits", "is_lab", "weekly_hours",
                  "theory_hours", "practical_hours", "tutorial_hours"])
        ws.append(["CS101", "Programming", 4, "false", 4, 3, 0, 1])
        ws.append(["CS101L", "Lab", 2, "true", 2, 0, 2, 0])
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            wb.save(temp_path)
            result = import_subjects_excel(temp_path, "Subjects")
            
            assert len(result.errors) == 0
            assert len(result.subjects) == 2
            assert result.subjects[1].is_lab
        finally:
            temp_path.unlink()


class TestImportDivisionsBatchesExcel:
    def test_imports_divisions_and_batches(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Divisions"
        ws.append(["year", "division_id", "division_name", "batch_id", "batch_name", "batch_size"])
        ws.append(["FY", "FY-A", "FY Division A", "FY-A-B1", "FY-A Batch 1", 20])
        ws.append(["FY", "FY-A", "FY Division A", "FY-A-B2", "FY-A Batch 2", 20])
        ws.append(["SY", "SY-A", "SY Division A", "SY-A-B1", "SY-A Batch 1", 25])
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            wb.save(temp_path)
            result = import_divisions_batches_excel(temp_path, "Divisions")
            
            assert len(result.errors) == 0
            assert len(result.years) == 2  # FY and SY
            assert len(result.divisions) == 2  # FY-A and SY-A
            assert len(result.batches) == 3
            
            # Check year levels
            year_levels = {y.level for y in result.years}
            assert YearLevel.FY in year_levels
            assert YearLevel.SY in year_levels
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])