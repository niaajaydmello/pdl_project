import customtkinter as ctk
from tkinter import messagebox, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from scheduler import TimetableScheduler
from visualizer import GraphVisualizer

# App Theme Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TimetableApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("College Timetable & Exam Scheduler")
        self.geometry("1200x750")

        self.scheduler = TimetableScheduler()
        self.canvas = None
        self.selected_course_code = None

        self._build_ui()
        self._load_sample_data()

    def _build_ui(self):
        # Header
        self.header = ctk.CTkLabel(self, text="College Timetable & Exam Scheduler", font=("Arial", 22, "bold"))
        self.header.pack(pady=10)

        # Main Layout (2 Columns)
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=10)

        # Left Column - Controls & Data Entry
        self.left_frame = ctk.CTkFrame(self.main_container, width=380)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        # Right Column - Output & Graph
        self.right_frame = ctk.CTkFrame(self.main_container)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        lbl = ctk.CTkLabel(self.left_frame, text="Add Course / Exam", font=("Arial", 16, "bold"))
        lbl.pack(pady=(10, 5))

        # Input Fields
        self.entry_code = ctk.CTkEntry(self.left_frame, placeholder_text="Course Code (e.g. CS101)")
        self.entry_code.pack(fill="x", padx=15, pady=5)

        self.entry_prof = ctk.CTkEntry(self.left_frame, placeholder_text="Professor Name (e.g. Dr. Smith)")
        self.entry_prof.pack(fill="x", padx=15, pady=5)

        self.entry_group = ctk.CTkEntry(self.left_frame, placeholder_text="Student Group (e.g. Year 1 CS)")
        self.entry_group.pack(fill="x", padx=15, pady=5)

        # Action Buttons
        btn_add = ctk.CTkButton(self.left_frame, text="Add Course", command=self.add_course)
        btn_add.pack(fill="x", padx=15, pady=10)

        btn_update = ctk.CTkButton(self.left_frame, text="Update Selected", command=self.update_selected_course)
        btn_update.pack(fill="x", padx=15, pady=5)

        btn_delete = ctk.CTkButton(self.left_frame, text="Delete Selected", command=self.delete_selected_course)
        btn_delete.pack(fill="x", padx=15, pady=5)

        btn_clear = ctk.CTkButton(self.left_frame, text="Clear All", fg_color="#c0392b", hover_color="#922b21", command=self.clear_all_courses)
        btn_clear.pack(fill="x", padx=15, pady=5)

        btn_run = ctk.CTkButton(self.left_frame, text="Generate Schedule", fg_color="#27ae60", hover_color="#219150", command=self.generate_schedule)
        btn_run.pack(fill="x", padx=15, pady=10)

        btn_export = ctk.CTkButton(self.left_frame, text="Export CSV", fg_color="#8e44ad", hover_color="#732d91", command=self.export_csv)
        btn_export.pack(fill="x", padx=15, pady=5)

        # Info Card
        info = (
            "How it Works:\n"
            "• Courses are Graph Vertices.\n"
            "• Shared Professors/Groups create Edges.\n"
            "• Welsh-Powell algorithm colors the graph.\n"
            "• Same Color = Same Time Slot."
        )
        info_label = ctk.CTkLabel(self.left_frame, text=info, justify="left", font=("Arial", 11), text_color="#aaaaaa")
        info_label.pack(side="bottom", padx=15, pady=15)

    def _build_right_panel(self):
        self.tabs = ctk.CTkTabview(self.right_frame)
        self.tabs.pack(fill="both", expand=True)

        self.tab_table = self.tabs.add("Timetable")
        self.tab_graph = self.tabs.add("Conflict Graph Visualization")

        # Treeview Schedule Table
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=25)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", font=("Arial", 10, "bold"))

        self.tree = ttk.Treeview(self.tab_table, columns=("Code", "Prof", "Group", "Slot"), show="headings")
        self.tree.heading("Code", text="Course Code")
        self.tree.heading("Prof", text="Professor")
        self.tree.heading("Group", text="Student Group")
        self.tree.heading("Slot", text="Assigned Time Slot")

        self.tree.column("Code", width=100)
        self.tree.column("Prof", width=150)
        self.tree.column("Group", width=150)
        self.tree.column("Slot", width=200)

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._on_course_selected)

    def _on_course_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.selected_course_code = None
            return
        values = self.tree.item(selection[0], "values")
        if not values:
            return
        self.selected_course_code = str(values[0])
        for entry, value in zip((self.entry_code, self.entry_prof, self.entry_group), values[:3]):
            entry.delete(0, "end")
            entry.insert(0, value)

    def _clear_graph(self):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None

    def _refresh_schedule(self):
        if self.scheduler.courses:
            self.generate_schedule()
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._clear_graph()
        self.selected_course_code = None

    def add_course(self):
        code = self.entry_code.get().strip()
        prof = self.entry_prof.get().strip()
        group = self.entry_group.get().strip()

        if not code or not prof or not group:
            messagebox.showwarning("Input Error", "Please fill all fields.")
            return

        self.scheduler.add_course(code, prof, group)
        self.selected_course_code = None
        messagebox.showinfo("Success", f"Course '{code}' added successfully.")
        self.entry_code.delete(0, 'end')
        self.entry_prof.delete(0, 'end')
        self.entry_group.delete(0, 'end')

    def update_selected_course(self):
        if not self.selected_course_code:
            messagebox.showwarning("Selection Required", "Select a course in the timetable first.")
            return

        new_code = self.entry_code.get().strip()
        prof = self.entry_prof.get().strip()
        group = self.entry_group.get().strip()
        if not new_code or not prof or not group:
            messagebox.showwarning("Input Error", "Please fill all fields.")
            return

        old_code = self.selected_course_code
        if not self.scheduler.update_course(old_code, new_code, prof, group):
            messagebox.showwarning("Update Error", "The course no longer exists or that course code is already in use.")
            return

        self.selected_course_code = None
        self._refresh_schedule()

    def delete_selected_course(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Selection Required", "Select a course in the timetable first.")
            return
        values = self.tree.item(selection[0], "values")
        if not values or not self.scheduler.remove_course(str(values[0])):
            messagebox.showwarning("Delete Error", "The selected course could not be found.")
            return
        self._refresh_schedule()

    def clear_all_courses(self):
        if not messagebox.askyesno("Clear All Courses", "Are you sure you want to delete all courses?"):
            return
        self.scheduler.clear_courses()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._clear_graph()
        self.selected_course_code = None
        for entry in (self.entry_code, self.entry_prof, self.entry_group):
            entry.delete(0, "end")

    def generate_schedule(self):
        if not self.scheduler.courses:
            messagebox.showwarning("Warning", "No courses to schedule!")
            return

        df, coloring = self.scheduler.generate_schedule()

        for row in self.tree.get_children():
            self.tree.delete(row)
        self.selected_course_code = None

        for _, row in df.iterrows():
            self.tree.insert("", "end", values=(row["Course Code"], row["Professor"], row["Student Group"], row["Assigned Time Slot"]))

        self._render_graph(coloring)

    def _render_graph(self, coloring):
        self._clear_graph()

        fig = GraphVisualizer.draw_colored_graph(self.scheduler.graph, coloring)
        self.canvas = FigureCanvasTkAgg(fig, master=self.tab_graph)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def export_csv(self):
        if not self.scheduler.courses:
            messagebox.showwarning("Warning", "No schedule to export.")
            return

        df, _ = self.scheduler.generate_schedule()
        df.to_csv("generated_timetable.csv", index=False)
        messagebox.showinfo("Export Successful", "Timetable exported to 'generated_timetable.csv'.")

    def _load_sample_data(self):
        """Pre-populate sample college courses with realistic conflicts."""
        samples = [
            ("CS101", "Dr. Alan", "CS Batch A"),
            ("CS102", "Dr. Alan", "CS Batch B"),
            ("MATH101", "Dr. Beth", "CS Batch A"),
            ("EE201", "Dr. Charlie", "EE Batch A"),
            ("EE202", "Dr. Charlie", "EE Batch B"),
            ("CS201", "Dr. Alan", "CS Batch B"),
            ("PHYS101", "Dr. David", "EE Batch A"),
        ]
        for code, prof, group in samples:
            self.scheduler.add_course(code, prof, group)
        
        self.generate_schedule()


if __name__ == "__main__":
    app = TimetableApp()
    app.mainloop()
