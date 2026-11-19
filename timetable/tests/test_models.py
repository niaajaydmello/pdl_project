"""Check the timetable dataclasses and their plain dictionary conversion."""

from timetable.engine.models import Assignment, CollegeDataset, Faculty, Year


def test_dataclass_defaults_are_independent():
    first = Faculty("F1", "A. Rao")
    second = Faculty("F2", "B. Shah")
    first.unavailable_slots.append("MON-P1")
    assert second.unavailable_slots == []


def test_dataset_dict_round_trip():
    dataset = CollegeDataset(years=[Year("Y1", "FY", 1)], assignments=[Assignment("A1", "S1", "F1", "Y1", "D1")])
    restored = CollegeDataset.from_dict(dataset.to_dict())
    assert restored == dataset
