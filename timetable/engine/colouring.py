"""Graph colouring algorithms for timetable scheduling.

Three algorithms:
1. dsatur_colour - Main algorithm (DSATUR with constraint awareness)
2. welsh_powell_colour - Baseline (degree-ordered greedy)
3. random_greedy_colour - Baseline (random order with fixed seed)

All respect hard constraints: allowed_slots, faculty unavailability, multi-period labs,
preassigned slots, and optional slot_scorer callback for cost-based selection.
"""

import random
from typing import Callable, Optional
from dataclasses import dataclass, field

from timetable.engine.models import SessionNode, TimeSlot, TeachingAssignment, Faculty, Division, Batch
from timetable.engine.graph import ConflictGraph, ConflictType
from timetable.engine.slots import SlotGrid, resolve_allowed_slots, get_lab_block_slots


# Type alias for slot scorer callback
SlotScorer = Callable[[str, SessionNode, dict[str, str], SlotGrid], float]
# Returns a cost score (lower = better) for placing node at slot_id


@dataclass
class ColouringResult:
    """Result of a graph colouring run."""
    schedule: dict[str, str]              # session_id -> start_slot_id
    unassigned: list[str]                 # session_ids that couldn't be scheduled
    iterations: int = 0
    backtracks: int = 0


def _check_slot_availability(
    node: SessionNode,
    slot_id: str,
    schedule: dict[str, str],
    graph: ConflictGraph,
    slot_grid: SlotGrid,
    occupied_division_slots: dict[str, set[str]],
    occupied_batch_slots: dict[str, set[str]],
    occupied_faculty_slots: dict[str, set[str]],
    node_by_id: dict[str, SessionNode] = None,
) -> bool:
    """Check if a slot (or lab block) is available for a node.
    
    Verifies:
    - Slot is in node's allowed_slots
    - No faculty conflict for any period in the block
    - No division conflict for any period in the block
    - No batch conflict for any period in the block
    - For lab blocks: all periods in block are free
    """
    assignment = node.assignment
    division = assignment.division
    batch = assignment.batch
    faculty = assignment.faculty
    
    # Get the block of slots this node would occupy
    if node.duration > 1:
        block = get_lab_block_slots(slot_id, slot_grid.slots)
        if len(block) != node.duration:
            return False
    else:
        block = [slot_id]
    
    # Check all slots in block are in allowed_slots
    if not all(s in node.allowed_slots for s in block):
        return False

    # Faculty must be available for every period of a lab block.
    if any(slot in faculty.unavailable_slots for slot in block):
        return False
    
    # Check faculty occupancy
    fac_occupied = occupied_faculty_slots.get(faculty.id, set())
    if any(s in fac_occupied for s in block):
        return False
    
    # Check division occupancy
    div_occupied = occupied_division_slots.get(division.id, set())
    if any(s in div_occupied for s in block):
        return False
    
    # Check batch occupancy (for labs)
    if batch:
        batch_occupied = occupied_batch_slots.get(batch.id, set())
        if any(s in batch_occupied for s in block):
            return False
    
    # Check conflict graph neighbors already scheduled, including their full lab blocks.
    for neighbor_id in graph.neighbors(node.id):
        if neighbor_id in schedule:
            neighbor_slot = schedule[neighbor_id]
            neighbor_node = (node_by_id or {}).get(neighbor_id)
            if neighbor_node is None:
                continue
            if neighbor_node.duration > 1:
                neighbor_block = get_lab_block_slots(neighbor_slot, slot_grid.slots)
            else:
                neighbor_block = [neighbor_slot]
            if any(s in neighbor_block for s in block):
                return False
    
    return True


def _compute_saturation(
    node: SessionNode,
    schedule: dict[str, str],
    graph: ConflictGraph,
) -> int:
    """Compute DSATUR saturation degree: number of different colours used by neighbors."""
    neighbour_colours = set()
    for neighbor_id in graph.neighbors(node.id):
        if neighbor_id in schedule:
            neighbour_colours.add(schedule[neighbor_id])
    return len(neighbour_colours)


def _select_node_dsatur(
    unassigned: list[SessionNode],
    schedule: dict[str, str],
    graph: ConflictGraph,
) -> SessionNode:
    """Select next node using DSATUR heuristic: highest saturation, tie-break by degree."""
    lab_nodes = [node for node in unassigned if node.duration > 1]
    candidates = lab_nodes if lab_nodes else unassigned

    best_node = None
    best_saturation = -1
    best_degree = -1
    best_allowed = 1 << 30
    
    for node in candidates:
        sat = _compute_saturation(node, schedule, graph)
        deg = graph.degree(node.id)
        allowed_count = len(node.allowed_slots)
        
        if (sat > best_saturation
                or (sat == best_saturation and deg > best_degree)
                or (sat == best_saturation and deg == best_degree and allowed_count < best_allowed)):
            best_saturation = sat
            best_degree = deg
            best_allowed = allowed_count
            best_node = node
    
    return best_node


def _select_slot_for_node(
    node: SessionNode,
    schedule: dict[str, str],
    graph: ConflictGraph,
    slot_grid: SlotGrid,
    occupied_division_slots: dict[str, set[str]],
    occupied_batch_slots: dict[str, set[str]],
    occupied_faculty_slots: dict[str, set[str]],
    slot_scorer: Optional[SlotScorer] = None,
    node_by_id: dict[str, SessionNode] = None,
) -> Optional[str]:
    """Select the best available slot for a node.
    
    If slot_scorer provided, use it to rank allowed slots (lower score = better).
    Otherwise, use first-fit on allowed slots.
    """
    allowed = list(node.allowed_slots)
    if not allowed:
        return None
    
    # Filter to actually available slots
    available = []
    for slot_id in allowed:
        if _check_slot_availability(node, slot_id, schedule, graph, slot_grid,
                                     occupied_division_slots, occupied_batch_slots,
                                     occupied_faculty_slots, node_by_id or {}):
            available.append(slot_id)
    
    if not available:
        return None
    
    if slot_scorer:
        # Score each available slot and pick best
        scored = [(slot_scorer(slot_id, node, schedule, slot_grid), slot_id) 
                  for slot_id in available]
        scored.sort(key=lambda x: x[0])
        return scored[0][1]
    
    # First-fit: return first available
    return available[0]


def _assign_node(
    node: SessionNode,
    slot_id: str,
    schedule: dict[str, str],
    occupied_division_slots: dict[str, set[str]],
    occupied_batch_slots: dict[str, set[str]],
    occupied_faculty_slots: dict[str, set[str]],
    slot_grid: SlotGrid,
) -> None:
    """Assign a node to a slot and update occupancy maps."""
    assignment = node.assignment
    division = assignment.division
    batch = assignment.batch
    faculty = assignment.faculty
    
    if node.duration > 1:
        block = get_lab_block_slots(slot_id, slot_grid.slots)
    else:
        block = [slot_id]
    
    schedule[node.id] = slot_id
    
    # Update occupancy
    for s in block:
        occupied_division_slots.setdefault(division.id, set()).add(s)
        occupied_faculty_slots.setdefault(faculty.id, set()).add(s)
        if batch:
            occupied_batch_slots.setdefault(batch.id, set()).add(s)


def dsatur_colour(
    nodes: list[SessionNode],
    graph: ConflictGraph,
    slot_grid: SlotGrid,
    preassigned: dict[str, str] = None,
    slot_scorer: SlotScorer = None,
    max_iterations: int = 10000,
) -> ColouringResult:
    """DSATUR graph colouring with constraint awareness.
    
    Main scheduling algorithm. Respects:
    - Hard constraints: allowed_slots, faculty unavailability, lab spans
    - Preassigned/locked slots
    - Optional slot_scorer callback for cost-based slot selection
    - Division/batch/faculty occupancy tracking
    
    Args:
        nodes: List of SessionNode objects to schedule
        graph: ConflictGraph with all conflicts
        slot_grid: SlotGrid with standard slots
        preassigned: Optional dict of session_id -> slot_id (locked assignments)
        slot_scorer: Optional callback(score) for cost-based slot selection
        max_iterations: Safety limit
        
    Returns:
        ColouringResult with schedule and any unassigned nodes
    """
    schedule: dict[str, str] = {}
    unassigned: list[str] = []
    
    # Occupancy tracking
    occupied_division_slots: dict[str, set[str]] = {}
    occupied_batch_slots: dict[str, set[str]] = {}
    occupied_faculty_slots: dict[str, set[str]] = {}

    # Re-resolve allowed slots through the faculty/division constraints.
    # This is important for nodes loaded directly from JSON, whose
    # allowed_slots may not yet include faculty unavailable-slot filtering.
    resolved_nodes = []
    for node in nodes:
        allowed = resolve_allowed_slots(
            node,
            slot_grid.slots,
            node.assignment.faculty,
            node.assignment.division,
            node.assignment.batch,
        )
        resolved_nodes.append(SessionNode(
            id=node.id,
            assignment=node.assignment,
            duration=node.duration,
            is_lab_start=node.is_lab_start,
            allowed_slots=allowed,
            preassigned_slot=node.preassigned_slot,
        ))
    nodes = resolved_nodes
    
    # Apply preassigned slots first
    if preassigned:
        node_by_id = {n.id: n for n in nodes}
        for node_id, slot_id in preassigned.items():
            node = node_by_id.get(node_id)
            if node and slot_id in node.allowed_slots:
                _assign_node(node, slot_id, schedule, occupied_division_slots,
                            occupied_batch_slots, occupied_faculty_slots, slot_grid)
    
    # Remaining nodes to schedule
    remaining = [n for n in nodes if n.id not in schedule]
    iterations = 0
    
    while remaining and iterations < max_iterations:
        iterations += 1
        
        # DSATUR node selection
        node = _select_node_dsatur(remaining, schedule, graph)
        
        # Slot selection
        slot_id = _select_slot_for_node(node, schedule, graph, slot_grid,
                                         occupied_division_slots, occupied_batch_slots,
                                         occupied_faculty_slots, slot_scorer,
                                         node_by_id={n.id: n for n in nodes})
        
        if slot_id:
            _assign_node(node, slot_id, schedule, occupied_division_slots,
                        occupied_batch_slots, occupied_faculty_slots, slot_grid)
            remaining.remove(node)
        else:
            # Cannot place this node - mark unassigned and remove
            unassigned.append(node.id)
            remaining.remove(node)

    # Greedy colouring can strand nodes behind an earlier poor choice.
    # Retry stranded nodes in several bounded passes after occupancy from
    # the successful greedy pass is complete.
    node_by_id = {n.id: n for n in nodes}
    stranded = list(dict.fromkeys(unassigned))
    unassigned = []
    for _ in range(5):
        still_stranded = []
        for node_id in stranded:
            node = node_by_id[node_id]
            slot_id = _select_slot_for_node(
                node,
                schedule,
                graph,
                slot_grid,
                occupied_division_slots,
                occupied_batch_slots,
                occupied_faculty_slots,
                slot_scorer,
                node_by_id=node_by_id,
            )
            if slot_id:
                _assign_node(
                    node,
                    slot_id,
                    schedule,
                    occupied_division_slots,
                    occupied_batch_slots,
                    occupied_faculty_slots,
                    slot_grid,
                )
            else:
                still_stranded.append(node_id)
        if not still_stranded:
            break
        stranded = still_stranded
    unassigned.extend(stranded)
    
    # Any remaining nodes are unassigned
    unassigned.extend(n.id for n in remaining)
    
    return ColouringResult(
        schedule=schedule,
        unassigned=unassigned,
        iterations=iterations,
    )


def welsh_powell_colour(
    nodes: list[SessionNode],
    graph: ConflictGraph,
    slot_grid: SlotGrid,
    preassigned: dict[str, str] = None,
    slot_scorer: SlotScorer = None,
    max_iterations: int = 10000,
) -> ColouringResult:
    """Welsh-Powell baseline: order by degree descending, greedy colour.
    
    Simpler baseline algorithm for comparison.
    """
    schedule: dict[str, str] = {}
    unassigned: list[str] = []
    
    occupied_division_slots: dict[str, set[str]] = {}
    occupied_batch_slots: dict[str, set[str]] = {}
    occupied_faculty_slots: dict[str, set[str]] = {}
    
    # Apply preassigned
    if preassigned:
        node_by_id = {n.id: n for n in nodes}
        for node_id, slot_id in preassigned.items():
            node = node_by_id.get(node_id)
            if node and slot_id in node.allowed_slots:
                _assign_node(node, slot_id, schedule, occupied_division_slots,
                            occupied_batch_slots, occupied_faculty_slots, slot_grid)
    
    # Sort by degree descending (Welsh-Powell)
    remaining = [n for n in nodes if n.id not in schedule]
    remaining.sort(key=lambda n: graph.degree(n.id), reverse=True)
    
    iterations = 0
    for node in remaining:
        if iterations >= max_iterations:
            break
        iterations += 1
        
        slot_id = _select_slot_for_node(node, schedule, graph, slot_grid,
                                         occupied_division_slots, occupied_batch_slots,
                                         occupied_faculty_slots, slot_scorer)
        
        if slot_id:
            _assign_node(node, slot_id, schedule, occupied_division_slots,
                        occupied_batch_slots, occupied_faculty_slots, slot_grid)
        else:
            unassigned.append(node.id)
    
    return ColouringResult(
        schedule=schedule,
        unassigned=unassigned,
        iterations=iterations,
    )


def random_greedy_colour(
    nodes: list[SessionNode],
    graph: ConflictGraph,
    slot_grid: SlotGrid,
    preassigned: dict[str, str] = None,
    slot_scorer: SlotScorer = None,
    seed: int = 42,
    max_iterations: int = 10000,
) -> ColouringResult:
    """Random greedy baseline: random node order with fixed seed.
    
    Useful for stochastic comparison and testing.
    """
    schedule: dict[str, str] = {}
    unassigned: list[str] = []
    
    occupied_division_slots: dict[str, set[str]] = {}
    occupied_batch_slots: dict[str, set[str]] = {}
    occupied_faculty_slots: dict[str, set[str]] = {}
    
    # Apply preassigned
    if preassigned:
        node_by_id = {n.id: n for n in nodes}
        for node_id, slot_id in preassigned.items():
            node = node_by_id.get(node_id)
            if node and slot_id in node.allowed_slots:
                _assign_node(node, slot_id, schedule, occupied_division_slots,
                            occupied_batch_slots, occupied_faculty_slots, slot_grid)
    
    # Random order with fixed seed
    remaining = [n for n in nodes if n.id not in schedule]
    rng = random.Random(seed)
    rng.shuffle(remaining)
    
    iterations = 0
    for node in remaining:
        if iterations >= max_iterations:
            break
        iterations += 1
        
        slot_id = _select_slot_for_node(node, schedule, graph, slot_grid,
                                         occupied_division_slots, occupied_batch_slots,
                                         occupied_faculty_slots, slot_scorer)
        
        if slot_id:
            _assign_node(node, slot_id, schedule, occupied_division_slots,
                        occupied_batch_slots, occupied_faculty_slots, slot_grid)
        else:
            unassigned.append(node.id)
    
    return ColouringResult(
        schedule=schedule,
        unassigned=unassigned,
        iterations=iterations,
    )