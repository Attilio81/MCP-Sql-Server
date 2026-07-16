# -*- coding: utf-8 -*-
"""
Output formatting helpers for MCP SQL Server.
"""

import csv
import io
import json


def format_csv(columns: list[str], rows: list[tuple]) -> str:
    """Format results as CSV inside a code block. No truncation."""
    if not rows:
        return "*Nessun dato trovato*"
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return f"```csv\n{buf.getvalue()}```"


def format_json(columns: list[str], rows: list[tuple]) -> str:
    """Format results as a JSON array of objects. No truncation."""
    if not rows:
        return "*Nessun dato trovato*"
    data = [dict(zip(columns, row)) for row in rows]
    # default=str handles datetime / Decimal / bytes
    return f"```json\n{json.dumps(data, ensure_ascii=False, indent=2, default=str)}\n```"


def format_table_data(columns: list[str], rows: list[tuple], max_col_width: int = 50) -> str:
    """Format results as markdown table with truncation for large values"""
    if not rows:
        return "*Nessun dato trovato*"

    def truncate(val, max_len=max_col_width):
        s = str(val) if val is not None else "NULL"
        s = s.replace("|", "\\|")
        return s if len(s) <= max_len else s[:max_len-3] + "..."

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join(["---" for _ in columns]) + "|"

    # Rows
    data_rows = []
    for row in rows:
        formatted_row = "| " + " | ".join(truncate(val) for val in row) + " |"
        data_rows.append(formatted_row)

    return "\n".join([header, separator] + data_rows)
