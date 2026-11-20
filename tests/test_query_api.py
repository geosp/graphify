"""graphify.query_api: in-process access to the MCP query tools."""
import json

import networkx as nx
import pytest
from networkx.readwrite import json_graph

from graphify import query_api
from graphify.serve import TOOL_HANDLERS


def _write(path, edges: list[tuple[str, str]]) -> None:
    G = nx.DiGraph()
    for a, b in edges:
        for n in (a, b):
            G.add_node(n, label=n, community=0, source_file=f"{n}.py", file_type="code")
        G.add_edge(a, b, relation="calls", confidence="EXTRACTED")
    path.write_text(json.dumps(json_graph.node_link_data(G, edges="links")), encoding="utf-8")


def test_tool_sets_partition_handlers():
    assert query_api.GRAPH_TOOLS | query_api.PR_TOOLS == frozenset(TOOL_HANDLERS)
    assert not query_api.GRAPH_TOOLS & query_api.PR_TOOLS
    assert query_api.PR_TOOLS == {"list_prs", "get_pr_impact", "triage_prs"}


def test_load_and_run_tools(tmp_path):
    gp = tmp_path / "graph.json"
    _write(gp, [("main", "parse"), ("parse", "tokenize")])
    cache = query_api.GraphCache(max_contexts=2)
    ctx = query_api.load(cache, gp)

    assert ctx.graph_path == str(gp.resolve())
    assert "Nodes: 3" in query_api.run_tool("graph_stats", ctx)
    assert "Node: parse" in query_api.run_tool("get_node", ctx, {"label": "parse"})
    neighbors = query_api.run_tool("get_neighbors", ctx, {"label": "parse"})
    assert "main" in neighbors and "tokenize" in neighbors
    path = query_api.run_tool("shortest_path", ctx, {"source": "main", "target": "tokenize"})
    assert "parse" in path
    assert "parse" in query_api.run_tool("query_graph", ctx, {"question": "parse"})


def test_projects_stay_separate(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _write(a, [("alpha", "beta")])
    _write(b, [("gamma", "delta")])
    cache = query_api.GraphCache(max_contexts=2)
    ctx_a, ctx_b = query_api.load(cache, a), query_api.load(cache, b)
    assert "alpha" in query_api.run_tool("get_node", ctx_a, {"label": "alpha"})
    assert "No node matching 'alpha'" in query_api.run_tool("get_node", ctx_b, {"label": "alpha"})
    assert "Node: gamma" in query_api.run_tool("get_node", ctx_b, {"label": "gamma"})


def test_reload_after_rewrite(tmp_path):
    gp = tmp_path / "graph.json"
    _write(gp, [("one", "two")])
    cache = query_api.GraphCache()
    assert "Nodes: 2" in query_api.run_tool("graph_stats", query_api.load(cache, gp))
    _write(gp, [("one", "two"), ("two", "three"), ("three", "four")])
    assert "Nodes: 4" in query_api.run_tool("graph_stats", query_api.load(cache, gp))


def test_missing_graph_and_unknown_tool(tmp_path):
    cache = query_api.GraphCache()
    with pytest.raises(FileNotFoundError):
        query_api.load(cache, tmp_path / "nope.json")
    gp = tmp_path / "graph.json"
    _write(gp, [("x", "y")])
    with pytest.raises(KeyError):
        query_api.run_tool("drop_tables", query_api.load(cache, gp))
