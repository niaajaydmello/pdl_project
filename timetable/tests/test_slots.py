"""Check teaching period generation and same-day consecutive lab blocks."""

from timetable.engine.slots import find_consecutive_slot_pairs, generate_slots


def test_generation_creates_day_period_grid_and_lunch_gap():
    slots = generate_slots(["Monday"], 4, lunch_after_period=2)
    assert len(slots) == 4
    assert slots[0].label == "09:00-10:00"
    assert slots[2].label.startswith("12:00")


def test_lab_pairs_are_adjacent_and_do_not_cross_lunch():
    slots = generate_slots(["Monday"], 4, lunch_after_period=2)
    pairs = find_consecutive_slot_pairs(slots)
    assert [(pair[0].period, pair[1].period) for pair in pairs] == [(1, 2), (3, 4)]


def test_lunch_boundary_is_respected_on_a_two_period_grid():
    slots = generate_slots(["Monday"], 2, lunch_after_period=1)
    assert find_consecutive_slot_pairs(slots) == []
