"""Pure-Python conflict graph for timetable scheduling.

Stores adjacency as `dict[str, set[str]]` with typed edges.
Conflict types: faculty, division, batch_division, student, room.
Key rule: A division always conflicts with its own batches.
Parallel batches of the same division do NOT conflict with each other.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from timetable.engine.models import SessionNode, TeachingAssignment, Division, Batch, Faculty


class ConflictType(Enum):
    """Type of conflict between two session nodes."""
    FACULTY = "faculty"              # Same faculty member
    DIVISION = "division"            # Same division (theory sessions)
    BATCH_DIVISION = "batch_division"  # Batch vs its parent division
    STUDENT = "student"              # Shared students (electives/backlogs)
    ROOM = "room"                    # Same room (if room assigned)


@dataclass(frozen=True)
class ConflictEdge:
    """A typed conflict edge between two session nodes."""
    u: str                    # SessionNode ID
    v: str                    # SessionNode ID
    conflict_type: ConflictType
    detail: str = ""          # Human-readable detail (e.g., faculty name)


class ConflictGraph:
    """Conflict graph with typed edges and adjacency sets.
    
    Uses plain dict[str, set[str]] for adjacency plus a separate
    edge metadata map for conflict types and details.
    """
    
    def __init__(self):
        self.adj: dict[str, set[str]] = {}
        self.edges: dict[tuple[str, str], ConflictEdge] = {}
        self.nodes: set[str] = set()
    
    def add_node(self, node_id: str) -> None:
        """Add a node to the graph."""
        if node_id not in self.nodes:
            self.nodes.add(node_id)
            self.adj[node_id] = set()
    
    def add_edge(self, u: str, v: str, conflict_type: ConflictType, detail: str = "") -> None:
        """Add a conflict edge between two nodes."""
        if u == v:
            return
        self.add_node(u)
        self.add_node(v)
        
        # Ensure consistent ordering for edge key
        key = (u, v) if u < v else (v, u)
        
        # Only add if not already present (keep first conflict type found)
        if key not in self.edges:
            self.edges[key] = ConflictEdge(u, v, conflict_type, detail)
            self.adj[u].add(v)
            self.adj[v].add(u)
    
    def has_edge(self, u: str, v: str) -> bool:
        """Check if conflict exists between two nodes."""
        key = (u, v) if u < v else (v, u)
        return key in self.edges
    
    def get_edge(self, u: str, v: str) -> Optional[ConflictEdge]:
        """Get the conflict edge between two nodes."""
        key = (u, v) if u < v else (v, u)
        return self.edges.get(key)
    
    def neighbors(self, node_id: str) -> set[str]:
        """Get all conflicting neighbors of a node."""
        return self.adj.get(node_id, set())
    
    def degree(self, node_id: str) -> int:
        """Get degree (number of conflicts) of a node."""
        return len(self.adj.get(node_id, set()))
    
    def get_conflict_types(self, u: str, v: str) -> list[ConflictType]:
        """Get all conflict types between two nodes (usually just one)."""
        edge = self.get_edge(u, v)
        return [edge.conflict_type] if edge else []
    
    def __len__(self) -> int:
        return len(self.nodes)
    
    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes


def build_conflict_graph(
    nodes: list[SessionNode],
    student_enrollments: list = None,  # List of StudentEnrollment
    elective_map: dict[str, set[str]] = None,  # subject_code -> set of student_ids
    backlog_map: dict[str, set[str]] = None,   # subject_code -> set of student_ids
) -> ConflictGraph:
    """Build the complete conflict graph from session nodes.
    
    Conflicts added:
    1. FACULTY: Same faculty teaching two sessions
    2. DIVISION: Two theory sessions for the same division
    3. BATCH_DIVISION: A batch lab session vs its parent division's theory sessions
    4. STUDENT: Sessions sharing students via electives or backlogs
    4. ROOM: (Optional) Same room - requires room assignment info
    
    Key invariant: Division conflicts with its own batches.
    Parallel batches of same division do NOT conflict with each other.
    
    Args:
        nodes: List of SessionNode objects
        student_enrollments: Optional list of StudentEnrollment for student conflicts
        elective_map: Optional subject_code -> student_ids for electives
        backlog_map: Optional subject_code -> student_ids for backlogs
        
    Returns:
        Populated ConflictGraph
    """
    graph = ConflictGraph()
    
    # Add all nodes
    for node in nodes:
        graph.add_node(node.id)
    
    # Build lookup maps for efficient conflict detection
    faculty_nodes: dict[str, list[SessionNode]] = {}
    division_theory_nodes: dict[str, list[SessionNode]] = {}
    division_batch_nodes: dict[str, dict[str, list[SessionNode]]] = {}  # div_id -> batch_id -> nodes
    subject_nodes: dict[str, list[SessionNode]] = {}
    
    for node in nodes:
        assignment = node.assignment
        faculty_id = assignment.faculty.id
        div_id = assignment.division.id
        subject_code = assignment.subject.code
        
        # Faculty index
        faculty_nodes.setdefault(faculty_id, []).append(node)
        
        # Division theory index (only theory/tutorial sessions for whole division)
        if assignment.batch is None:
            division_theory_nodes.setdefault(div_id, []).append(node)
        
        # Division batch index (practical sessions for specific batches)
        if assignment.batch:
            batch_id = assignment.batch.id
            division_batch_nodes.setdefault(div_id, {}).setdefault(batch_id, []).append(node)
        
        # Subject index (for student conflicts)
        subject_nodes.setdefault(subject_code, []).append(node)
    
    # 1. FACULTY conflicts: Same faculty cannot teach two sessions at once
    for faculty_id, fac_nodes in faculty_nodes.items():
        for i in range(len(fac_nodes)):
            for j in range(i + 1, len(fac_nodes)):
                u, v = fac_nodes[i], fac_nodes[j]
                graph.add_edge(u.id, v.id, ConflictType.FACULTY, 
                              f"Faculty: {faculty_id}")
    
    # 2. DIVISION conflicts: Theory sessions within same division conflict
    for div_id, div_nodes in division_theory_nodes.items():
        for i in range(len(div_nodes)):
            for j in range(i + 1, len(div_nodes)):
                u, v = div_nodes[i], div_nodes[j]
                graph.add_edge(u.id, v.id, ConflictType.DIVISION,
                              f"Division: {div_id}")
    
    # 3. BATCH_DIVISION conflicts: Batch labs conflict with parent division's theory
    #    Parallel batches of same division do NOT conflict with each other
    for div_id, batch_map in division_batch_nodes.items():
        div_theory = division_theory_nodes.get(div_id, [])
        for batch_id, batch_nodes in batch_map.items():
            # Each batch node conflicts with ALL division theory nodes
            for batch_node in batch_nodes:
                for theory_node in div_theory:
                    graph.add_edge(batch_node.id, theory_node.id, ConflictType.BATCH_DIVISION,
                                  f"Batch {batch_id} vs Division {div_id}")
            # Batches of same division do NOT conflict with each other (parallel labs)
    
    # 4. STUDENT conflicts: Sessions for subjects enrolled in by the same student
    if student_enrollments:
        for enrollment in student_enrollments:
            enrolled_subjects = (
                set(enrollment.elective_subjects)
                | set(enrollment.backlog_subjects)
            )
            student_nodes = []
            seen_ids = set()
            for subject_code in enrolled_subjects:
                for node in subject_nodes.get(subject_code, []):
                    if node.id not in seen_ids:
                        student_nodes.append(node)
                        seen_ids.add(node.id)
            for i in range(len(student_nodes)):
                for j in range(i + 1, len(student_nodes)):
                    u, v = student_nodes[i], student_nodes[j]
                    if not graph.has_edge(u.id, v.id):
                        graph.add_edge(
                            u.id,
                            v.id,
                            ConflictType.STUDENT,
                            f"Shared student: {enrollment.student_id}",
                        )

    # Elective/backlog subject maps may be supplied independently of enrollments.
    if elective_map or backlog_map:
        elective_map = elective_map or {}
        backlog_map = backlog_map or {}
        
        # For each subject, check if it has elective/backlog students
        for subject_code, subj_nodes in subject_nodes.items():
            elective_students = elective_map.get(subject_code, set())
            backlog_students = backlog_map.get(subject_code, set())
            shared_students = elective_students | backlog_students
            
            if shared_students:
                # All sessions of this subject conflict with each other
                # (they share the same student pool)
                for i in range(len(subj_nodes)):
                    for j in range(i + 1, len(subj_nodes)):
                        u, v = subj_nodes[i], subj_nodes[j]
                        if not graph.has_edge(u.id, v.id):
                            graph.add_edge(u.id, v.id, ConflictType.STUDENT,
                                          f"Shared students: {subject_code}")
    
    return graph


def build_student_conflict_maps(
    student_enrollments: list,
    nodes: list[SessionNode],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build elective_map and backlog_map from student enrollments.
    
    Args:
        student_enrollments: List of StudentEnrollment objects
        nodes: List of SessionNode objects (to get subject codes)
        
    Returns:
        Tuple of (elective_map, backlog_map) where each maps subject_code -> student_ids
    """
    elective_map: dict[str, set[str]] = {}
    backlog_map: dict[str, set[str]] = {}
    
    for enrollment in student_enrollments:
        student_id = enrollment.student_id
        
        for subj_code in enrollment.elective_subjects:
            elective_map.setdefault(subj_code, set()).add(student_id)
        
        for subj_code in enrollment.backlog_subjects:
            backlog_map.setdefault(subj_code, set()).add(student_id)
    
    return elective_map, backlog_map