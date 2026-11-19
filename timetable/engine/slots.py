"""Time slot grid generation and slot resolution utilities.

Provides the Mon-Fri, 7-periods-per-day grid with lunch break between P4 and P5.
Handles lab block linking (is_lab_start, next_slot_id) and per-node allowed_slots
resolution incorporating faculty unavailability, lab-only blocks, and fixed slots.
"""

from dataclasses import dataclass
from typing import Optional
from timetable.engine.models import (
    TimeSlot, TeachingAssignment, SessionNode, Faculty, Division, Batch, SessionType
)


# Constants for the standard timetable grid
DAYS = 5           # Mon-Fri
PERIODS_PER_DAY = 7  # P1..P7
LUNCH_AFTER_PERIOD = 4  # Lunch between P4 and P5


def generate_standard_slots() -> list[TimeSlot]:
    """Generate the standard Mon-Fri × 7-period grid with lunch break excluded.
    
    Returns:
        List of TimeSlot objects for all teaching periods (35 slots).
        Lunch slots are NOT included in the returned list.
    """
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    slots = []
    
    for day in range(DAYS):
        for period in range(1, PERIODS_PER_DAY + 1):
            # Skip lunch "period" - we don't create a slot for lunch
            # Periods 1-4 are morning, 5-7 are afternoon
            slot_id = f"{day_names[day]}-P{period}"
            label = f"{day_names[day]} P{period}"
            slots.append(TimeSlot(
                id=slot_id,
                day=day,
                period=period,
                label=label,
                is_lunch=False
            ))
    
    return slots


def get_next_slot_id(slot_id: str, slots: list[TimeSlot]) -> Optional[str]:
    """Get the next contiguous slot ID in the same day.
    
    Args:
        slot_id: Current slot ID (e.g., "MON-P1")
        slots: List of all TimeSlot objects
        
    Returns:
        Next slot ID in same day, or None if at end of day or lunch break.
    """
    slot_map = {s.id: s for s in slots}
    current = slot_map.get(slot_id)
    if not current:
        return None
    
    # Can't cross lunch boundary (P4 -> P5 is lunch break)
    if current.period == LUNCH_AFTER_PERIOD:
        return None
    
    # Can't go past last period
    if current.period >= PERIODS_PER_DAY:
        return None
    
    next_period = current.period + 1
    next_id = f"{slot_id.split('-P')[0]}-P{next_period}"
    return next_id if next_id in slot_map else None


def is_lab_start(slot_id: str, slots: list[TimeSlot]) -> bool:
    """Check if a slot can start a 2-period lab block.
    
    A lab block needs two contiguous periods in the same day,
    not crossing the lunch break.
    
    Args:
        slot_id: Slot ID to check
        slots: List of all TimeSlot objects
        
    Returns:
        True if this slot can start a 2-period lab block.
    """
    next_slot = get_next_slot_id(slot_id, slots)
    return next_slot is not None


def get_lab_block_slots(slot_id: str, slots: list[TimeSlot]) -> list[str]:
    """Get both slot IDs for a 2-period lab block starting at slot_id.
    
    Args:
        slot_id: Starting slot ID
        slots: List of all TimeSlot objects
        
    Returns:
        List of 2 slot IDs if valid lab start, empty list otherwise.
    """
    if not is_lab_start(slot_id, slots):
        return []
    next_slot = get_next_slot_id(slot_id, slots)
    return [slot_id, next_slot]


def resolve_allowed_slots(
    node: SessionNode,
    slots: list[TimeSlot],
    faculty: Faculty,
    division: Division,
    batch: Optional[Batch] = None,
    division_slots: Optional[dict[str, set[str]]] = None,
    batch_slots: Optional[dict[str, set[str]]] = None,
) -> frozenset[str]:
    """Resolve the allowed slots for a SessionNode considering all constraints.
    
    Combines:
    - Node's own allowed_slots (from assignment.fixed_slot or assignment.allowed_slots)
    - Faculty unavailable_slots
    - Lab-only constraint (2-period blocks only on valid lab-start slots)
    - Division/batch already-occupied slots (optional, for progressive scheduling)
    
    Args:
        node: SessionNode to resolve slots for
        slots: All available TimeSlot objects
        faculty: Faculty member teaching this session
        division: Division this session belongs to
        batch: Batch if practical, None for theory
        division_slots: Optional map of division_id -> occupied slot IDs
        batch_slots: Optional map of batch_id -> occupied slot IDs
        
    Returns:
        Frozen set of allowed slot IDs for this node.
    """
    slot_ids = {s.id for s in slots}
    allowed = set(slot_ids)
    
    # 1. Start with node's explicitly allowed slots (if any)
    if node.allowed_slots:
        allowed &= node.allowed_slots
    
    # 2. Remove faculty unavailable slots
    allowed -= faculty.unavailable_slots
    
    # 3. If preassigned, only that slot is allowed
    if node.preassigned_slot:
        if node.preassigned_slot in allowed:
            return frozenset([node.preassigned_slot])
        return frozenset()  # Preassigned slot not available
    
    # 4. Lab sessions: only allow slots that can start a 2-period block
    if node.duration > 1:
        lab_starts = {s.id for s in slots if is_lab_start(s.id, slots)}
        allowed &= lab_starts
    
    # 5. Remove slots already occupied by division (theory) or batch (lab)
    if division_slots and division.id in division_slots:
        allowed -= division_slots[division.id]
    if batch and batch_slots and batch.id in batch_slots:
        allowed -= batch_slots[batch.id]
    
    return frozenset(allowed)


@dataclass
class SlotGrid:
    """Convenience container for the slot grid and derived mappings."""
    slots: list[TimeSlot]
    slot_by_id: dict[str, TimeSlot]
    lab_start_slots: frozenset[str]
    slots_by_day: dict[int, list[str]]
    
    @classmethod
    def create_standard(cls) -> 'SlotGrid':
        slots = generate_standard_slots()
        slot_by_id = {s.id: s for s in slots}
        lab_starts = frozenset(s.id for s in slots if is_lab_start(s.id, slots))
        
        slots_by_day = {}
        for day in range(DAYS):
            day_slots = [s.id for s in slots if s.day == day]
            slots_by_day[day] = day_slots
        
        return cls(
            slots=slots,
            slot_by_id=slot_by_id,
            lab_start_slots=lab_starts,
            slots_by_day=slots_by_day
        )
    
    def get_slot(self, slot_id: str) -> Optional[TimeSlot]:
        return self.slot_by_id.get(slot_id)
    
    def next_slot(self, slot_id: str) -> Optional[str]:
        return get_next_slot_id(slot_id, self.slots)
    
    def lab_block(self, slot_id: str) -> list[str]:
        return get_lab_block_slots(slot_id, self.slots)