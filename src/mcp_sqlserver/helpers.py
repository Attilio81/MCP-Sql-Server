# -*- coding: utf-8 -*-
"""
Output formatting helpers for MCP SQL Server.
"""


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
