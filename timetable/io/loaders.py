"""Read timetable datasets and faculty assignment sheets from common formats."""

import csv
import json
from pathlib import Path
from typing import Any

from timetable.engine.models import Assignment, CollegeDataset


def load_from_json(path: str | Path) -> CollegeDataset:
    """Load a structured college dataset JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Dataset JSON must contain an object at its top level.")
    return CollegeDataset.from_dict(data)


def _assignment_from_row(row: dict[str, Any], row_number: int) -> Assignment:
    required = ("assignment_id", "subject_id", "faculty_id", "year_id", "division_id")
    missing = [name for name in required if not str(row.get(name, "")).strip()]
    if missing:
        raise ValueError(f"Row {row_number} is missing required values: {', '.join(missing)}.")
    try:
        hours = int(row.get("hours_per_week", 1))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Row {row_number} has an invalid hours_per_week value.") from error
    if hours < 0:
        raise ValueError(f"Row {row_number} has a negative hours_per_week value.")
    batch = row.get("batch_id") or None
    room = row.get("preferred_room_id") or None
    locked = row.get("locked_slots", "")
    return Assignment(
        assignment_id=str(row["assignment_id"]).strip(),
        subject_id=str(row["subject_id"]).strip(),
        faculty_id=str(row["faculty_id"]).strip(),
        year_id=str(row["year_id"]).strip(),
        division_id=str(row["division_id"]).strip(),
        batch_id=str(batch).strip() if batch else None,
        session_type=str(row.get("session_type") or "theory").strip(),
        hours_per_week=hours,
        preferred_room_id=str(room).strip() if room else None,
        locked_slots=[part.strip() for part in str(locked).split(";") if part.strip()],
    )


def _load_assignment_rows(headers: list[str], rows: list[dict[str, Any]]) -> list[Assignment]:
    required = {"assignment_id", "subject_id", "faculty_id", "year_id", "division_id"}
    missing = sorted(required.difference(headers))
    if missing:
        raise ValueError(f"Assignment sheet is missing columns: {', '.join(missing)}.")
    return [_assignment_from_row(row, index) for index, row in enumerate(rows, start=2)]


def load_assignments_from_csv(path: str | Path) -> list[Assignment]:
    """Load assignments from a CSV sheet with named columns."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = [name.strip() for name in (reader.fieldnames or [])]
        rows = [{(key or "").strip(): value for key, value in row.items()} for row in reader]
    return _load_assignment_rows(headers, rows)


def load_assignments_from_xlsx(
    path: str | Path, sheet_name: str | None = None
) -> list[Assignment]:
    """Load assignments from the first row of an XLSX worksheet."""
    try:
        from openpyxl import load_workbook
    except ImportError as error:
        raise ImportError("XLSX support requires openpyxl>=3.1.0.") from error
    workbook = load_workbook(Path(path), read_only=True, data_only=True)
    try:
        if sheet_name is None:
            worksheet = workbook.active
        elif sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
        else:
            raise ValueError(f"Worksheet '{sheet_name}' was not found.")
        values = worksheet.iter_rows(values_only=True)
        headers = [str(value).strip() if value is not None else "" for value in next(values, ())]
        rows = []
        for values_row in values:
            rows.append({headers[index]: value for index, value in enumerate(values_row) if index < len(headers) and headers[index]})
        return _load_assignment_rows(headers, rows)
    finally:
        workbook.close()
