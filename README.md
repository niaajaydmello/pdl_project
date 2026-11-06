# College Timetable and Exam Scheduler

A desktop application that creates a timetable by modeling courses as a graph. Courses that share a professor or student group are treated as conflicts and assigned different time slots. The app displays the resulting timetable and a colored conflict graph, and can export the schedule to CSV.

> This is a desktop application built with Tkinter; it is not a website and does not need a web server.

## Team

- Nia Dmello
- Jaanya Jain
- Chakshu Patel
- Shraddha

## Features

- Add courses with a course code, professor, and student group.
- Automatically detect conflicts between courses that share a professor or student group.
- Generate a schedule using the Welsh–Powell graph-coloring algorithm.
- View the timetable and conflict graph in separate tabs.
- Export the generated timetable as `generated_timetable.csv`.
- Start with sample courses so the app has example data to display.

## How scheduling works

Each course is represented by a node in a NetworkX graph. An edge connects courses that have the same professor or student group, because those courses should not be scheduled at the same time. The scheduler orders courses by graph degree and assigns each course the lowest available color not used by its neighboring courses. Each color represents a time slot.

The algorithm is a heuristic: it produces a valid schedule for the detected conflicts, but it does not guarantee the fewest possible time slots. Fifteen named weekday time slots are provided; if a schedule needs more, additional slots are labeled `Slot 16`, `Slot 17`, and so on.

## Main functions and modules

### `main.py`

- `TimetableApp.__init__()` creates the app, scheduler, and interface, then loads sample courses.
- `TimetableApp._build_ui()` and the panel-building methods create the window, controls, timetable, and tabs.
- `TimetableApp.add_course()` validates the form and adds a course.
- `TimetableApp.generate_schedule()` updates the timetable and graph.
- `TimetableApp._render_graph()` embeds the graph visualization in the app.
- `TimetableApp.export_csv()` writes the generated schedule to `generated_timetable.csv` in the current working directory.
- `TimetableApp._load_sample_data()` adds example courses.

### `scheduler.py`

- `TimetableScheduler.add_course()` stores a course and adds its graph node.
- `TimetableScheduler.add_conflict()` adds an edge between two existing courses.
- `TimetableScheduler.auto_detect_conflicts()` finds shared professors or student groups.
- `TimetableScheduler.welsh_powell_coloring()` assigns a color/time-slot index to each course.
- `TimetableScheduler.generate_schedule()` returns the schedule as a Pandas DataFrame and the course-to-color mapping.

### `visualizer.py`

- `GraphVisualizer.draw_colored_graph()` draws the conflict graph, coloring each course according to its assigned time slot.

## Libraries

Dependencies are listed in [`requirements.txt`](requirements.txt).

- **CustomTkinter** — themed desktop interface and controls.
- **Tkinter** (Python standard library) — GUI event loop, dialogs, and timetable tree view.
- **NetworkX** — conflict graph and graph operations.
- **Pandas** — schedule data and CSV export.
- **Matplotlib** — graph drawing and embedding in the interface.
- **tabulate** — installed as a project dependency; the current app does not directly call it.

## Requirements

- Python 3.10 or later is recommended.
- Windows 10/11 or macOS.
- Internet access for the initial dependency installation.

## Installation and running

Run the commands from the project directory (the directory containing `main.py` and `requirements.txt`).

### Windows

1. Install Python from [python.org/downloads](https://www.python.org/downloads/). During installation, enable **Add Python to PATH**.
2. Open PowerShell and change to the project directory. For example:

   ```powershell
   cd "C:\path\to\pdl_project"
   ```

3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt instead:

   ```bat
   .venv\Scripts\activate.bat
   ```

4. Install dependencies and launch the app:

   ```powershell
   python -m pip install -r requirements.txt
   python main.py
   ```

### macOS

1. Install Python 3.10 or later from [python.org/downloads/macos](https://www.python.org/downloads/macos/). The python.org installer is recommended if the system Python/Tk window displays incorrectly.
2. Open Terminal and change to the project directory. For example:

   ```bash
   cd "/path/to/pdl_project"
   ```

   If you are not sure of the path, type `cd ` (including the space) in Terminal and drag the project folder from Finder into the Terminal window, then press Return.

3. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies and launch the app:

   ```bash
   python -m pip install -r requirements.txt
   python main.py
   ```

The app window stays open while it is running. Close the window to exit. If Terminal prints an error, keep the full traceback; it can help diagnose the problem.

## Using the app

1. On startup, the app loads example courses and generates a sample schedule.
2. Enter a course code, professor, and student group, then select **Add Course**.
3. Select **Generate Schedule** to include added courses and refresh the results.
4. Use the **Timetable** and **Conflict Graph Visualization** tabs to view the output.
5. Select **Export CSV** to write `generated_timetable.csv` to the directory from which the app was launched.

Course data is kept in memory and is not saved when the app closes. Export the schedule if you need to keep a copy.

## Troubleshooting

- **`No such file or directory`**: Make sure the Terminal/PowerShell working directory is the project folder and that it contains `main.py` and `requirements.txt`. Quote paths that contain spaces.
- **`No module named ...`**: Activate the virtual environment and run `python -m pip install -r requirements.txt` again.
- **A Tk deprecation warning on macOS**: The warning alone does not mean the app failed. If the window is blank, try the Python version installed from python.org and repeat the setup steps in a new Terminal window.
- **The app appears blank or exits unexpectedly**: Launch it from Terminal/PowerShell using `python main.py` and check for a traceback.

## Project files

```text
pdl_project/
├── main.py          # Desktop interface and app actions
├── scheduler.py     # Conflict detection and timetable generation
├── visualizer.py    # Conflict graph drawing
├── requirements.txt # Python dependencies
└── README.md        # Project and setup documentation
```
