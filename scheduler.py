import networkx as nx
import pandas as pd
from typing import Dict, List, Tuple


class TimetableScheduler:
    def __init__(self):
        self.graph = nx.Graph()
        self.courses: Dict[str, dict] = {}
        self.time_slots: List[str] = [
            "Mon 09:00 - 10:30", "Mon 10:45 - 12:15", "Mon 13:00 - 14:30",
            "Tue 09:00 - 10:30", "Tue 10:45 - 12:15", "Tue 13:00 - 14:30",
            "Wed 09:00 - 10:30", "Wed 10:45 - 12:15", "Wed 13:00 - 14:30",
            "Thu 09:00 - 10:30", "Thu 10:45 - 12:15", "Thu 13:00 - 14:30",
            "Fri 09:00 - 10:30", "Fri 10:45 - 12:15", "Fri 13:00 - 14:30"
        ]

    def add_course(self, course_code: str, professor: str, student_group: str):
        """Add a course node to the graph with details."""
        self.courses[course_code] = {
            "professor": professor,
            "group": student_group
        }
        self.graph.add_node(course_code)

    def add_conflict(self, course1: str, course2: str, reason: str = "Constraint"):
        """Add an edge between two courses indicating a schedule conflict."""
        if course1 in self.graph and course2 in self.graph:
            self.graph.add_edge(course1, course2, reason=reason)

    def auto_detect_conflicts(self):
        """Automatically add conflict edges based on shared professors or student groups."""
        course_list = list(self.courses.keys())
        for i in range(len(course_list)):
            for j in range(i + 1, len(course_list)):
                c1, c2 = course_list[i], course_list[j]
                data1, data2 = self.courses[c1], self.courses[c2]

                # Conflict 1: Same Professor
                if data1["professor"] == data2["professor"]:
                    self.add_conflict(c1, c2, reason="Same Professor")
                # Conflict 2: Same Student Group
                elif data1["group"] == data2["group"]:
                    self.add_conflict(c1, c2, reason="Same Student Group")

    def welsh_powell_coloring(self) -> Dict[str, int]:
        """
        Welsh-Powell Graph Coloring Algorithm:
        1. Order vertices by decreasing degree.
        2. Assign the lowest available color (time slot) to uncolored nodes without conflicts.
        """
        # Step 1: Sort nodes by degree in descending order
        sorted_nodes = sorted(self.graph.nodes(), key=lambda x: self.graph.degree(x), reverse=True)
        color_map: Dict[str, int] = {}

        for node in sorted_nodes:
            # Find colors used by neighbors
            neighbor_colors = {color_map[neighbor] for neighbor in self.graph.neighbors(node) if neighbor in color_map}
            
            # Find the lowest available color index
            color = 0
            while color in neighbor_colors:
                color += 1
            
            color_map[node] = color

        return color_map

    def generate_schedule(self) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """Run auto-conflict detection and return schedule DataFrame & coloring map."""
        self.auto_detect_conflicts()
        coloring = self.welsh_powell_coloring()

        schedule_data = []
        for course, color_idx in coloring.items():
            slot = self.time_slots[color_idx] if color_idx < len(self.time_slots) else f"Slot {color_idx + 1}"
            prof = self.courses[course]["professor"]
            group = self.courses[course]["group"]
            schedule_data.append({
                "Course Code": course,
                "Professor": prof,
                "Student Group": group,
                "Assigned Time Slot": slot,
                "Color Index (Slot ID)": color_idx
            })

        df = pd.DataFrame(schedule_data)
        return df, coloring