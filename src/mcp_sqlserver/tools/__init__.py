# -*- coding: utf-8 -*-
"""
MCP SQL Server tool handlers.
Each tool is implemented in its own module for maintainability.
"""

from mcp_sqlserver.tools.list_tables import handle_list_tables
from mcp_sqlserver.tools.describe_table import handle_describe_table
from mcp_sqlserver.tools.execute_query import handle_execute_query
from mcp_sqlserver.tools.relationships import handle_table_relationships
from mcp_sqlserver.tools.indexes import handle_table_indexes
from mcp_sqlserver.tools.search_columns import handle_search_columns
from mcp_sqlserver.tools.statistics import handle_table_statistics
from mcp_sqlserver.tools.views import handle_get_views
from mcp_sqlserver.tools.dictionary import handle_update_dictionary

__all__ = [
    "handle_list_tables",
    "handle_describe_table",
    "handle_execute_query",
    "handle_table_relationships",
    "handle_table_indexes",
    "handle_search_columns",
    "handle_table_statistics",
    "handle_get_views",
    "handle_update_dictionary",
]
