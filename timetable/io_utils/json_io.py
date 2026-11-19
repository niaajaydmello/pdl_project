"""JSON serialisation for project data and schedule snapshots.

Provides save/load for the full project definition (ProjectData) and
schedule snapshots (session_id -> slot_id mapping).
"""

import json
from dataclasses import asdict, is_dataclass, fields
from enum import Enum
from typing import Any, Optional
from pathlib import Path

from timetable.engine.models import (
    ProjectData, Year, Division, Batch, Subject, Faculty, Room,
    TeachingAssignment, TimeSlot, SessionNode, StudentEnrollment,
    YearLevel, SessionType, RoomType
)
from timetable.engine.slots import SlotGrid, generate_standard_slots


# Type markers for JSON serialisation
TYPE_FIELD = "__type__"


def _dataclass_to_dict(obj: Any) -> dict:
    """Convert a dataclass instance to a dict with type marker."""
    if not is_dataclass(obj):
        return obj
    
    result = {TYPE_FIELD: obj.__class__.__name__}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if is_dataclass(value):
            result[f.name] = _dataclass_to_dict(value)
        elif isinstance(value, list):
            result[f.name] = [_dataclass_to_dict(v) for v in value]
        elif isinstance(value, set):
            result[f.name] = list(value)
        elif isinstance(value, frozenset):
            result[f.name] = list(value)
        elif isinstance(value, dict):
            result[f.name] = {k: _dataclass_to_dict(v) for k, v in value.items()}
        elif isinstance(value, Enum):
            result[f.name] = value.value
        else:
            result[f.name] = value
    return result


def _dict_to_dataclass(data: dict, cls: type) -> Any:
    """Convert a dict with type marker back to a dataclass instance."""
    if not isinstance(data, dict) or TYPE_FIELD not in data:
        return data
    
    type_name = data[TYPE_FIELD]
    
    # Map type names to classes
    type_map = {
        "Year": Year,
        "Division": Division,
        "Batch": Batch,
        "Subject": Subject,
        "Faculty": Faculty,
        "Room": Room,
        "TeachingAssignment": TeachingAssignment,
        "TimeSlot": TimeSlot,
        "SessionNode": SessionNode,
        "StudentEnrollment": StudentEnrollment,
        "ProjectData": ProjectData,
        "YearLevel": YearLevel,
        "SessionType": SessionType,
        "RoomType": RoomType,
    }
    
    target_cls = type_map.get(type_name)
    if not target_cls:
        raise ValueError(f"Unknown type: {type_name}")
    
    # Special handling for enums
    if target_cls in (YearLevel, SessionType, RoomType):
        return target_cls(data.get("value", data.get("name", "")))
    
    # Prepare field values
    field_values = {}
    for f in fields(target_cls):
        if f.name in data:
            value = data[f.name]
            # Handle enum fields
            if hasattr(f.type, '__bases__') and issubclass(f.type, Enum):
                field_values[f.name] = f.type(value)
            elif is_dataclass(target_cls) and f.name in {"year", "division", "batch", "subject", "faculty", "room", "assignment"}:
                # Nested dataclass reference
                field_values[f.name] = _dict_to_dataclass(value, f.type)
            elif isinstance(value, list) and f.name in {"years", "divisions", "batches", "subjects", "faculty", "rooms", "teaching_assignments", "time_slots", "student_enrollments"}:
                # List of dataclasses
                item_type = f.type.__args__[0] if hasattr(f.type, '__args__') else None
                if item_type:
                    field_values[f.name] = [_dict_to_dataclass(v, item_type) for v in value]
                else:
                    field_values[f.name] = value
            elif isinstance(value, list):
                field_values[f.name] = value
            elif isinstance(value, dict):
                field_values[f.name] = value
            else:
                field_values[f.name] = value
    
    return target_cls(**field_values)


def _serialize_enum(value: Any) -> Any:
    """Serialize enum to its value."""
    if isinstance(value, Enum):
        return value.value
    return value


def project_to_json(project: ProjectData) -> dict:
    """Convert ProjectData to JSON-serialisable dict."""
    # Build a clean dict without internal lookup maps
    data = {
        TYPE_FIELD: "ProjectData",
        "years": [_dataclass_to_dict(y) for y in project.years],
        "divisions": [_dataclass_to_dict(d) for d in project.divisions],
        "batches": [_dataclass_to_dict(b) for b in project.batches],
        "subjects": [_dataclass_to_dict(s) for s in project.subjects],
        "faculty": [_dataclass_to_dict(f) for f in project.faculty],
        "rooms": [_dataclass_to_dict(r) for r in project.rooms],
        "teaching_assignments": [_dataclass_to_dict(a) for a in project.teaching_assignments],
        "time_slots": [_dataclass_to_dict(s) for s in project.time_slots],
        "student_enrollments": [_dataclass_to_dict(e) for e in project.student_enrollments],
    }
    return data


def json_to_project(data: dict) -> ProjectData:
    """Reconstruct ProjectData from JSON dict."""
    if not isinstance(data, dict) or data.get(TYPE_FIELD) != "ProjectData":
        raise ValueError("Invalid project data format")
    
    project = ProjectData()
    
    # Type map for reconstruction
    type_map = {
        "Year": Year,
        "Division": Division,
        "Batch": Batch,
        "Subject": Subject,
        "Faculty": Faculty,
        "Room": Room,
        "TeachingAssignment": TeachingAssignment,
        "TimeSlot": TimeSlot,
        "SessionNode": SessionNode,
        "StudentEnrollment": StudentEnrollment,
    }
    
    # Helper to reconstruct objects with references
    def reconstruct_list(items: list, cls: type) -> list:
        result = []
        for item in items:
            if isinstance(item, dict) and TYPE_FIELD in item:
                obj = _dict_to_dataclass(item, cls)
                result.append(obj)
            else:
                result.append(item)
        return result
    
    project.years = reconstruct_list(data.get("years", []), Year)
    project.divisions = reconstruct_list(data.get("divisions", []), Division)
    project.batches = reconstruct_list(data.get("batches", []), Batch)
    project.subjects = reconstruct_list(data.get("subjects", []), Subject)
    project.faculty = reconstruct_list(data.get("faculty", []), Faculty)
    project.rooms = reconstruct_list(data.get("rooms", []), Room)
    project.teaching_assignments = reconstruct_list(data.get("teaching_assignments", []), TeachingAssignment)
    project.time_slots = reconstruct_list(data.get("time_slots", []), TimeSlot)
    project.student_enrollments = reconstruct_list(data.get("student_enrollments", []), StudentEnrollment)
    
    # Rebuild lookups
    project.build_lookups()
    
    # Post-process: fix references in TeachingAssignment
    # The JSON stores nested objects, but we need to reference the canonical ones
    faculty_by_id = {f.id: f for f in project.faculty}
    room_by_id = {r.id: r for r in project.rooms}
    subject_by_code = {s.code: s for s in project.subjects}
    division_by_id = {d.id: d for d in project.divisions}
    batch_by_id = {b.id: b for b in project.batches}
    
    for assignment in project.teaching_assignments:
        if assignment.faculty.id in faculty_by_id:
            assignment.faculty = faculty_by_id[assignment.faculty.id]
        if assignment.subject.code in subject_by_code:
            assignment.subject = subject_by_code[assignment.subject.code]
        if assignment.division.id in division_by_id:
            assignment.division = division_by_id[assignment.division.id]
        if assignment.batch and assignment.batch.id in batch_by_id:
            assignment.batch = batch_by_id[assignment.batch.id]
    
    return project


def save_project(project: ProjectData, filepath: str | Path) -> None:
    """Save ProjectData to JSON file."""
    data = project_to_json(project)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_project(filepath: str | Path) -> ProjectData:
    """Load ProjectData from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json_to_project(data)


def save_schedule(schedule: dict[str, str], filepath: str | Path) -> None:
    """Save schedule (session_id -> slot_id) to JSON file."""
    data = {
        "schedule": schedule,
        "metadata": {
            "session_count": len(schedule),
            "slots_used": len(set(schedule.values())),
        }
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_schedule(filepath: str | Path) -> dict[str, str]:
    """Load schedule from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("schedule", {})


def save_colouring_result(result: 'ColouringResult', filepath: str | Path) -> None:
    """Save ColouringResult to JSON file."""
    from timetable.engine.colouring import ColouringResult
    data = {
        "schedule": result.schedule,
        "unassigned": result.unassigned,
        "iterations": result.iterations,
        "backtracks": result.backtracks,
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_colouring_result(filepath: str | Path) -> 'ColouringResult':
    """Load ColouringResult from JSON file."""
    from timetable.engine.colouring import ColouringResult
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return ColouringResult(
        schedule=data.get("schedule", {}),
        unassigned=data.get("unassigned", []),
        iterations=data.get("iterations", 0),
        backtracks=data.get("backtracks", 0),
    )