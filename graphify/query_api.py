"""Public, in-process API over the MCP query tools.

``graphify.serve`` exposes these tools over MCP. This module lets another
host, such as a multi-project MCP gateway, load graphs and run the same tools
in its own process, without speaking MCP to a child server and without
reaching into ``serve``'s private helpers.

Example::

    from graphify import query_api

    cache = query_api.GraphCache(max_contexts=8)
    ctx = query_api.load(cache, "/data/projects/app/graph/graph.json")
    print(query_api.run_tool("query_graph", ctx, {"question": "who calls main"}))

Every tool returns plain text, exactly what the MCP server would send. A
handler that signals a user-facing error raises :class:`ToolError`.
"""
from __future__ import annotations

from pathlib import Path

from graphify.serve import (
    TOOL_HANDLERS,
    GraphContext,
    ToolError,
    _GraphContextCache,
    _max_server_contexts,
)

__all__ = [
    "GRAPH_TOOLS",
    "PR_TOOLS",
    "GraphCache",
    "GraphContext",
    "ToolError",
    "load",
    "run_tool",
]

#: Tools that need only the graph.
GRAPH_TOOLS: frozenset[str] = frozenset(
    {
        "query_graph",
        "get_node",
        "get_section",
        "get_neighbors",
        "get_community",
        "god_nodes",
        "graph_stats",
        "shortest_path",
    }
)

#: Tools that also call the GitHub CLI (``gh``) for pull-request data.
PR_TOOLS: frozenset[str] = frozenset(TOOL_HANDLERS) - GRAPH_TOOLS


class GraphCache(_GraphContextCache):
    """Thread-safe LRU of loaded graphs, reloaded when graph.json changes.

    ``max_contexts`` defaults to ``GRAPHIFY_MAX_CONTEXTS`` (8 when unset).
    """

    def __init__(self, max_contexts: int | None = None) -> None:
        super().__init__(max_contexts if max_contexts is not None else _max_server_contexts())


def load(cache: GraphCache, graph_path: str | Path) -> GraphContext:
    """Return the context for ``graph_path``, loading or reloading it as needed.

    Raises ``FileNotFoundError`` when graph.json is missing and
    ``RuntimeError`` when it cannot be parsed.
    """
    resolved = str(Path(graph_path).resolve())
    G, communities = cache.load(resolved)
    return GraphContext(G, communities, resolved)


def run_tool(name: str, ctx: GraphContext, arguments: dict | None = None) -> str:
    """Run MCP tool ``name`` against ``ctx`` and return its text result."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"unknown graphify tool: {name}")
    return handler(ctx, dict(arguments or {}))
