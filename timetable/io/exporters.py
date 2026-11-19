"""Write timetable datasets and generated schedules to portable report formats."""

import csv
import json
from html import escape
from pathlib import Path
from typing import Any

from timetable.engine.models import CollegeDataset


def save_to_json(
    dataset: CollegeDataset,
    path: str | Path,
    schedule_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Save the dataset and, when supplied, its generated schedule snapshot."""
    result = dataset.to_dict()
    if schedule_rows is not None:
        result["schedule"] = schedule_rows
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)


def export_schedule_csv(schedule_rows: list[dict[str, Any]], path: str | Path) -> None:
    """Export schedule dictionaries as a headered CSV file."""
    columns = list(schedule_rows[0]) if schedule_rows else []
    with Path(path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if columns:
            writer.writeheader()
            writer.writerows(schedule_rows)


def export_schedule_xlsx(schedule_rows: list[dict[str, Any]], path: str | Path) -> None:
    """Export schedule dictionaries to a formatted XLSX worksheet."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError as error:
        raise ImportError("XLSX support requires openpyxl>=3.1.0.") from error
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Timetable"
    columns = list(schedule_rows[0]) if schedule_rows else []
    if columns:
        worksheet.append(columns)
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24527A")
        for row in schedule_rows:
            worksheet.append([row.get(column) for column in columns])
        for column in worksheet.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 2
            worksheet.column_dimensions[column[0].column_letter].width = min(width, 40)
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
    workbook.save(Path(path))


def export_schedule_html(
    schedule_rows: list[dict[str, Any]], path: str | Path, title: str = "Timetable"
) -> None:
    """Write an escaped, standalone HTML table report."""
    columns = list(schedule_rows[0]) if schedule_rows else []
    head = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body_rows = []
    for row in schedule_rows:
        cells = "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    document = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{escape(title)}</title>"
        f"<style>body{{font:16px Arial,sans-serif;margin:2rem;color:#222}}h1{{color:#24527a}}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:.6rem;text-align:left}"
        "th{background:#24527a;color:white}tr:nth-child(even){background:#f2f5f8}</style>"
        f"</head><body><h1>{escape(title)}</h1><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></body></html>"
    )
    Path(path).write_text(document, encoding="utf-8")
