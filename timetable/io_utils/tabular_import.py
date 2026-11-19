"""Import faculty load sheets and subject lists from CSV and Excel.

Uses stdlib `csv` and `openpyxl` for .xlsx files.
"""

import csv
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from timetable.engine.models import (
    Faculty, Subject, Division, Batch, Year, YearLevel,
    TeachingAssignment, SessionType, Room, RoomType,
    StudentEnrollment, ProjectData
)


@dataclass
class ImportResult:
    """Result of an import operation."""
    faculty: list[Faculty] = None
    subjects: list[Subject] = None
    divisions: list[Division] = None
    batches: list[Batch] = None
    assignments: list[TeachingAssignment] = None
    rooms: list[Room] = None
    enrollments: list[StudentEnrollment] = None
    errors: list[str] = None
    warnings: list[str] = None
    
    def __post_init__(self):
        if self.faculty is None: self.faculty = []
        if self.subjects is None: self.subjects = []
        if self.divisions is None: self.divisions = []
        if self.batches is None: self.batches = []
        if self.assignments is None: self.assignments = []
        if self.rooms is None: self.rooms = []
        if self.enrollments is None: self.enrollments = []
        if self.errors is None: self.errors = []
        if self.warnings is None: self.warnings = []


# ---------- CSV Import ----------

def read_csv_rows(filepath: str | Path, encoding: str = 'utf-8') -> list[dict]:
    """Read CSV file as list of dicts (header row as keys)."""
    with open(filepath, 'r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f)
        return list(reader)


def import_faculty_csv(filepath: str | Path) -> ImportResult:
    """Import faculty from CSV.
    
    Expected columns:
    - id, name, email, max_daily_hours, max_weekly_hours
    - unavailable_slots (semicolon-separated, e.g., "MON-P1;MON-P2")
    - preferred_slots (semicolon-separated)
    """
    result = ImportResult()
    rows = read_csv_rows(filepath)
    
    for row in rows:
        try:
            unavailable = set()
            if row.get('unavailable_slots'):
                unavailable = set(s.strip() for s in row['unavailable_slots'].split(';') if s.strip())
            
            preferred = set()
            if row.get('preferred_slots'):
                preferred = set(s.strip() for s in row['preferred_slots'].split(';') if s.strip())
            
            faculty = Faculty(
                id=row['id'].strip(),
                name=row['name'].strip(),
                email=row.get('email', '').strip(),
                max_daily_hours=int(row.get('max_daily_hours', 6)),
                max_weekly_hours=int(row.get('max_weekly_hours', 18)),
                unavailable_slots=frozenset(unavailable),
                preferred_slots=frozenset(preferred),
            )
            result.faculty.append(faculty)
        except Exception as e:
            result.errors.append(f"Faculty row {row}: {e}")
    
    return result


def import_subjects_csv(filepath: str | Path) -> ImportResult:
    """Import subjects from CSV.
    
    Expected columns:
    - code, name, credits, is_lab, weekly_hours, theory_hours, practical_hours, tutorial_hours
    """
    result = ImportResult()
    rows = read_csv_rows(filepath)
    
    for row in rows:
        try:
            subject = Subject(
                code=row['code'].strip(),
                name=row['name'].strip(),
                credits=int(row.get('credits', 0)),
                is_lab=row.get('is_lab', '').lower() in ('true', '1', 'yes'),
                weekly_hours=int(row.get('weekly_hours', 0)),
                theory_hours=int(row.get('theory_hours', 0)),
                practical_hours=int(row.get('practical_hours', 0)),
                tutorial_hours=int(row.get('tutorial_hours', 0)),
            )
            result.subjects.append(subject)
        except Exception as e:
            result.errors.append(f"Subject row {row}: {e}")
    
    return result


# ---------- Excel Import ----------

def read_excel_sheet(filepath: str | Path, sheet_name: str = None) -> list[dict]:
    """Read Excel sheet as list of dicts."""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active
    
    rows = []
    headers = None
    
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c).strip() if c is not None else f"col_{j}" for j, c in enumerate(row)]
        else:
            if headers:
                rows.append({headers[j]: (str(c).strip() if c is not None else "") for j, c in enumerate(row)})
    
    return rows


def import_faculty_excel(filepath: str | Path, sheet_name: str = "Faculty") -> ImportResult:
    """Import faculty from Excel sheet."""
    result = ImportResult()
    rows = read_excel_sheet(filepath, sheet_name)
    
    for row in rows:
        try:
            unavailable = set()
            if row.get('unavailable_slots'):
                unavailable = set(s.strip() for s in str(row['unavailable_slots']).split(';') if s.strip())
            
            preferred = set()
            if row.get('preferred_slots'):
                preferred = set(s.strip() for s in str(row['preferred_slots']).split(';') if s.strip())
            
            faculty = Faculty(
                id=str(row['id']).strip(),
                name=str(row['name']).strip(),
                email=str(row.get('email', '')).strip(),
                max_daily_hours=int(row.get('max_daily_hours', 6)),
                max_weekly_hours=int(row.get('max_weekly_hours', 18)),
                unavailable_slots=frozenset(unavailable),
                preferred_slots=frozenset(preferred),
            )
            result.faculty.append(faculty)
        except Exception as e:
            result.errors.append(f"Faculty row {row}: {e}")
    
    return result


def import_subjects_excel(filepath: str | Path, sheet_name: str = "Subjects") -> ImportResult:
    """Import subjects from Excel sheet."""
    result = ImportResult()
    rows = read_excel_sheet(filepath, sheet_name)
    
    for row in rows:
        try:
            subject = Subject(
                code=str(row['code']).strip(),
                name=str(row['name']).strip(),
                credits=int(row.get('credits', 0)),
                is_lab=str(row.get('is_lab', '')).lower() in ('true', '1', 'yes'),
                weekly_hours=int(row.get('weekly_hours', 0)),
                theory_hours=int(row.get('theory_hours', 0)),
                practical_hours=int(row.get('practical_hours', 0)),
                tutorial_hours=int(row.get('tutorial_hours', 0)),
            )
            result.subjects.append(subject)
        except Exception as e:
            result.errors.append(f"Subject row {row}: {e}")
    
    return result


def import_divisions_batches_excel(filepath: str | Path, sheet_name: str = "Divisions") -> ImportResult:
    """Import divisions and batches from Excel.
    
    Expected columns:
    - year, division_id, division_name, batch_id, batch_name, batch_size
    """
    result = ImportResult()
    rows = read_excel_sheet(filepath, sheet_name)
    
    year_map = {}
    division_map = {}
    
    for row in rows:
        try:
            year_level_str = str(row.get('year', 'FY')).upper()
            year_level = YearLevel[year_level_str] if year_level_str in YearLevel.__members__ else YearLevel.FY
            
            # Get or create year
            year_key = year_level
            if year_key not in year_map:
                year_map[year_key] = Year(level=year_level)
            
            year = year_map[year_key]
            
            # Division
            div_id = str(row['division_id']).strip()
            if div_id not in division_map:
                division = Division(
                    id=div_id,
                    year=year,
                    name=str(row.get('division_name', div_id)).strip(),
                )
                division_map[div_id] = division
                result.divisions.append(division)
            
            division = division_map[div_id]
            
            # Batch (optional)
            batch_id = str(row.get('batch_id', '')).strip()
            if batch_id:
                batch = Batch(
                    id=batch_id,
                    division=division,
                    name=str(row.get('batch_name', batch_id)).strip(),
                    size=int(row.get('batch_size', 0)),
                )
                result.batches.append(batch)
                
        except Exception as e:
            result.errors.append(f"Division/Batch row {row}: {e}")
    
    result.years = list(year_map.values())
    return result


# ---------- Generic Project Import ----------

def import_project_from_excel(filepath: str | Path) -> ProjectData:
    """Import complete project from multi-sheet Excel workbook.
    
    Expected sheets:
    - Years: level, name
    - Divisions: id, year, name
    - Batches: id, division, name, size
    - Subjects: code, name, credits, is_lab, weekly_hours, theory_hours, practical_hours, tutorial_hours
    - Faculty: id, name, email, max_daily_hours, max_weekly_hours, unavailable_slots, preferred_slots
    - Rooms: id, name, room_type, capacity, tags
    - Assignments: id, subject, faculty, division, batch, session_type, hours_per_week, fixed_slot, allowed_slots
    - Enrollments: student_id, student_name, division, batch, elective_subjects, backlog_subjects
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    project = ProjectData()
    
    # Helper to get sheet or return empty list
    def get_sheet(name: str) -> list[dict]:
        if name not in wb.sheetnames:
            return []
        ws = wb[name]
        rows = []
        headers = None
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c).strip() if c else f"col_{j}" for j, c in enumerate(row)]
            else:
                if headers:
                    rows.append({headers[j]: (str(c).strip() if c else "") for j, c in enumerate(row)})
        return rows
    
    # Years
    for row in get_sheet("Years"):
        try:
            level = YearLevel[row['level'].upper()]
            project.years.append(Year(level=level, name=row.get('name', level.name)))
        except Exception as e:
            pass  # Silently skip for now
    
    year_by_level = {y.level: y for y in project.years}
    
    # Divisions
    for row in get_sheet("Divisions"):
        try:
            level = YearLevel[row['year'].upper()]
            year = year_by_level.get(level)
            if year:
                project.divisions.append(Division(
                    id=row['id'],
                    year=year,
                    name=row.get('name', row['id']),
                ))
        except Exception:
            pass
    
    div_by_id = {d.id: d for d in project.divisions}
    
    # Batches
    for row in get_sheet("Batches"):
        try:
            div = div_by_id.get(row['division'])
            if div:
                project.batches.append(Batch(
                    id=row['id'],
                    division=div,
                    name=row.get('name', row['id']),
                    size=int(row.get('size', 0)),
                ))
        except Exception:
            pass
    
    batch_by_id = {b.id: b for b in project.batches}
    
    # Subjects
    for row in get_sheet("Subjects"):
        try:
            project.subjects.append(Subject(
                code=row['code'],
                name=row['name'],
                credits=int(row.get('credits', 0)),
                is_lab=row.get('is_lab', '').lower() in ('true', '1', 'yes'),
                weekly_hours=int(row.get('weekly_hours', 0)),
                theory_hours=int(row.get('theory_hours', 0)),
                practical_hours=int(row.get('practical_hours', 0)),
                tutorial_hours=int(row.get('tutorial_hours', 0)),
            ))
        except Exception:
            pass
    
    subj_by_code = {s.code: s for s in project.subjects}
    
    # Faculty
    for row in get_sheet("Faculty"):
        try:
            unavailable = set(s.strip() for s in row.get('unavailable_slots', '').split(';') if s.strip())
            preferred = set(s.strip() for s in row.get('preferred_slots', '').split(';') if s.strip())
            project.faculty.append(Faculty(
                id=row['id'],
                name=row['name'],
                email=row.get('email', ''),
                max_daily_hours=int(row.get('max_daily_hours', 6)),
                max_weekly_hours=int(row.get('max_weekly_hours', 18)),
                unavailable_slots=frozenset(unavailable),
                preferred_slots=frozenset(preferred),
            ))
        except Exception:
            pass
    
    fac_by_id = {f.id: f for f in project.faculty}
    
    # Rooms
    for row in get_sheet("Rooms"):
        try:
            room_type = RoomType[row.get('room_type', 'CLASSROOM').upper()]
            tags = set(s.strip() for s in row.get('tags', '').split(';') if s.strip())
            project.rooms.append(Room(
                id=row['id'],
                name=row['name'],
                room_type=room_type,
                capacity=int(row.get('capacity', 60)),
                tags=frozenset(tags),
            ))
        except Exception:
            pass
    
    # Assignments
    for row in get_sheet("Assignments"):
        try:
            subject = subj_by_code.get(row['subject'])
            faculty = fac_by_id.get(row['faculty'])
            division = div_by_id.get(row['division'])
            batch = batch_by_id.get(row['batch']) if row.get('batch') else None
            
            if subject and faculty and division:
                session_type = SessionType[row.get('session_type', 'THEORY').upper()]
                allowed = set(s.strip() for s in row.get('allowed_slots', '').split(';') if s.strip())
                
                project.teaching_assignments.append(TeachingAssignment(
                    id=row['id'],
                    subject=subject,
                    faculty=faculty,
                    division=division,
                    batch=batch,
                    session_type=session_type,
                    hours_per_week=int(row.get('hours_per_week', 0)),
                    fixed_slot=row.get('fixed_slot') or None,
                    allowed_slots=frozenset(allowed) if allowed else frozenset(),
                ))
        except Exception:
            pass
    
    # Enrollments
    for row in get_sheet("Enrollments"):
        try:
            division = div_by_id.get(row.get('division'))
            batch = batch_by_id.get(row.get('batch')) if row.get('batch') else None
            electives = set(s.strip() for s in row.get('elective_subjects', '').split(';') if s.strip())
            backlogs = set(s.strip() for s in row.get('backlog_subjects', '').split(';') if s.strip())
            
            project.student_enrollments.append(StudentEnrollment(
                student_id=row['student_id'],
                student_name=row.get('student_name', ''),
                division=division,
                batch=batch,
                elective_subjects=frozenset(electives),
                backlog_subjects=frozenset(backlogs),
            ))
        except Exception:
            pass
    
    # Generate standard slots if not provided
    if not project.time_slots:
        project.time_slots = generate_standard_slots()
    
    project.build_lookups()
    return project