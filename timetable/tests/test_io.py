"""Check JSON, CSV, XLSX, and HTML timetable file operations."""

import csv
import json
from pathlib import Path

import pytest

from timetable.engine.models import Assignment, CollegeDataset, Year
from timetable.io.exporters import export_schedule_csv, export_schedule_html, export_schedule_xlsx, save_to_json
from timetable.io.loaders import load_assignments_from_csv, load_assignments_from_xlsx, load_from_json


def test_json_round_trip_and_sample_dataset(tmp_path):
    dataset = CollegeDataset(years=[Year("Y1", "FY", 1)])
    path = tmp_path / "project.json"
    save_to_json(dataset, path, [{"Course": "Math"}])
    assert load_from_json(path) == dataset
    assert json.loads(path.read_text(encoding="utf-8"))["schedule"] == [{"Course": "Math"}]
    sample = load_from_json(Path(__file__).parents[1] / "data" / "sample_college.json")
    assert len(sample.years) == 3
    assert len(sample.divisions) == 6
    assert len(sample.batches) == 18
    assert len(sample.faculty) >= 16
    assert any(subject.is_elective for subject in sample.subjects)


def test_csv_loader_and_export(tmp_path):
    source = tmp_path / "assignments.csv"
    source.write_text("assignment_id,subject_id,faculty_id,year_id,division_id,hours_per_week\nA1,S1,F1,Y1,D1,3\n", encoding="utf-8")
    assert load_assignments_from_csv(source) == [Assignment("A1", "S1", "F1", "Y1", "D1", hours_per_week=3)]
    output = tmp_path / "schedule.csv"
    export_schedule_csv([{"Course": "Math", "Slot": "Mon P1"}], output)
    with output.open(encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file))[0]["Course"] == "Math"


def test_xlsx_load_and_export(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    source = tmp_path / "assignments.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["assignment_id", "subject_id", "faculty_id", "year_id", "division_id", "hours_per_week"])
    sheet.append(["A1", "S1", "F1", "Y1", "D1", 2])
    workbook.save(source)
    assert load_assignments_from_xlsx(source)[0].hours_per_week == 2
    output = tmp_path / "schedule.xlsx"
    export_schedule_xlsx([{"Course": "Math", "Slot": "Mon P1"}], output)
    assert openpyxl.load_workbook(output, read_only=True).active["A2"].value == "Math"


def test_html_export_escapes_values(tmp_path):
    output = tmp_path / "schedule.html"
    export_schedule_html([{"Course": "<Math>"}], output, title="Week")
    html = output.read_text(encoding="utf-8")
    assert "&lt;Math&gt;" in html
    assert "<title>Week</title>" in html


def test_csv_loader_reports_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("subject_id,faculty_id\nS1,F1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_assignments_from_csv(path)
