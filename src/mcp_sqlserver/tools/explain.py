# -*- coding: utf-8 -*-
"""Tool handler: explain_query"""

import logging

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator

logger = logging.getLogger(__name__)


async def handle_explain_query(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle explain_query tool: estimated execution plan, query is NOT executed."""
    query = arguments["query"].strip()

    # Same validation as execute_query — the plan leaks schema details
    is_valid, error_msg = SecurityValidator.validate_query(query)
    if not is_valid:
        return [TextContent(type="text", text=f"🔒 Query non valida: {error_msg}")]

    for table in SecurityValidator.extract_table_names(query):
        allowed, error_msg = SecurityValidator.is_table_allowed(table)
        if not allowed:
            return [TextContent(type="text", text=f"🔒 Query non valida: {error_msg}")]

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SET SHOWPLAN_ALL ON")
        try:
            logger.info(f"Explaining query: {query[:100]}...")
            cursor.execute(query)
            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()
        finally:
            # MUST reset before the connection goes back to the pool,
            # otherwise every later query on it returns plans instead of data
            cursor.execute("SET SHOWPLAN_ALL OFF")

        idx = {name: i for i, name in enumerate(columns)}
        result = "# Piano di Esecuzione (stimato)\n\n"
        result += f"```sql\n{query}\n```\n\n"
        result += "```\n"
        result += f"{'Costo':>10} {'Righe stim.':>12}  Operazione\n"
        for row in rows:
            stmt = row[idx["StmtText"]] or ""
            cost = row[idx["TotalSubtreeCost"]]
            est_rows = row[idx["EstimateRows"]]
            cost_s = f"{cost:.4f}" if cost is not None else ""
            rows_s = f"{est_rows:.0f}" if est_rows is not None else ""
            result += f"{cost_s:>10} {rows_s:>12}  {stmt}\n"
        result += "```\n\n"
        result += "*Piano stimato: la query non è stata eseguita. Costi in unità ottimizzatore SQL Server.*\n"

        return [TextContent(type="text", text=result)]
