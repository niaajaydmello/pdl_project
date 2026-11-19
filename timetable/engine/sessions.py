"""Session node expansion from teaching assignments.

Expands TeachingAssignment objects into SessionNode objects:
- Theory: 1-hour sessions -> N single-period nodes
- Practical: 2-hour sessions -> N/2 double-period lab nodes (each duration=2)
- Tutorial: 1-hour sessions -> N single-period nodes
"""

from typing import Optional
from timetable.engine.models import (
    TeachingAssignment, SessionNode, SessionType, Subject
)
from timetable.engine.slots import SlotGrid


def expand_assignments_to_nodes(
    assignments: list[TeachingAssignment],
    slot_grid: SlotGrid,
) -> list[SessionNode]:
    """Expand all teaching assignments into session nodes.
    
    Args:
        assignments: List of TeachingAssignment objects
        slot_grid: SlotGrid with standard slots and lab-start info
        
    Returns:
        List of SessionNode objects ready for scheduling
    """
    nodes = []
    for assignment in assignments:
        nodes.extend(expand_assignment(assignment, slot_grid))
    return nodes


def expand_assignment(
    assignment: TeachingAssignment,
    slot_grid: SlotGrid,
) -> list[SessionNode]:
    """Expand a single teaching assignment into session nodes.
    
    Theory/Tutorial: Creates `hours_per_week` single-period nodes (duration=1)
    Practical: Creates `hours_per_week // 2` double-period nodes (duration=2, is_lab_start=True)
    
    Args:
        assignment: TeachingAssignment to expand
        slot_grid: SlotGrid for allowed slot resolution
        
    Returns:
        List of SessionNode objects
    """
    nodes = []
    hours = assignment.hours_per_week
    
    if hours <= 0:
        return nodes
    
    # Determine base allowed slots from assignment
    base_allowed = set(assignment.allowed_slots) if assignment.allowed_slots else set(slot_grid.slot_by_id.keys())
    
    # If fixed slot, only that slot is allowed
    fixed_slot = assignment.fixed_slot
    
    if assignment.session_type == SessionType.PRACTICAL:
        # Practical: 2-period blocks
        num_blocks = hours // 2
        for i in range(num_blocks):
            node_id = f"{assignment.id}-LAB-{i+1}"
            # Lab nodes can only start at valid lab-start slots
            lab_allowed = base_allowed & slot_grid.lab_start_slots
            node = SessionNode(
                id=node_id,
                assignment=assignment,
                duration=2,
                is_lab_start=True,
                allowed_slots=frozenset(lab_allowed),
                preassigned_slot=fixed_slot if fixed_slot and fixed_slot in lab_allowed else None
            )
            nodes.append(node)
    else:
        # Theory/Tutorial: single-period nodes
        for i in range(hours):
            node_id = f"{assignment.id}-TH-{i+1}"
            node = SessionNode(
                id=node_id,
                assignment=assignment,
                duration=1,
                is_lab_start=False,
                allowed_slots=frozenset(base_allowed),
                preassigned_slot=fixed_slot if fixed_slot and fixed_slot in base_allowed else None
            )
            nodes.append(node)
    
    return nodes


def compute_node_allowed_slots(
    node: SessionNode,
    slot_grid: SlotGrid,
    occupied_division_slots: dict[str, set[str]],
    occupied_batch_slots: dict[str, set[str]],
    occupied_faculty_slots: dict[str, set[str]],
    occupied_room_slots: dict[str, set[str]] = None,
) -> frozenset[str]:
    """Compute allowed slots for a node given current occupancy state.
    
    This is used during progressive scheduling (e.g., DSATUR) to dynamically
    filter slots based on what's already scheduled.
    
    Args:
        node: SessionNode to compute slots for
        slot_grid: SlotGrid reference
        occupied_division_slots: division_id -> set of occupied slot IDs
        occupied_batch_slots: batch_id -> set of occupied slot IDs
        occupied_faculty_slots: faculty_id -> set of occupied slot IDs
        occupied_room_slots: room_id -> set of occupied slot IDs (optional)
        
    Returns:
        Frozen set of currently allowed slot IDs
    """
    from timetable.engine.slots import resolve_allowed_slots
    
    assignment = node.assignment
    division = assignment.division
    batch = assignment.batch
    faculty = assignment.faculty
    
    # Start with node's base allowed slots
    allowed = set(node.allowed_slots)
    
    # Remove faculty occupied slots (for all periods of this node)
    faculty_occupied = occupied_faculty_slots.get(faculty.id, set())
    allowed -= faculty_occupied
    
    # For multi-period nodes, also remove slots where subsequent periods would conflict
    if node.duration > 1:
        # Filter to only lab-start slots where the full block is free
        valid_starts = set()
        for slot_id in allowed:
            block = slot_grid.lab_block(slot_id)
            if len(block) == node.duration:
                # Check all periods in block are free for faculty
                if not any(p in faculty_occupied for p in block):
                    # Check division/batch occupancy for all periods
                    div_occ = occupied_division_slots.get(division.id, set())
                    batch_occ = occupied_batch_slots.get(batch.id, set()) if batch else set()
                    if not any(p in div_occ or p in batch_occ for p in block):
                        valid_starts.add(slot_id)
        allowed = valid_starts
    else:
        # Single period: check division/batch occupancy
        div_occ = occupied_division_slots.get(division.id, set())
        allowed -= div_occ
        if batch:
            batch_occ = occupied_batch_slots.get(batch.id, set())
            allowed -= batch_occ
    
    # Room occupancy (if room assigned and tracking enabled)
    if occupied_room_slots:
        # Room assignment would need to be known; for now skip
        pass
    
    # If preassigned, only allow that slot (if still free)
    if node.preassigned_slot:
        if node.preassigned_slot in allowed:
            return frozenset([node.preassigned_slot])
        return frozenset()
    
    return frozenset(allowed)