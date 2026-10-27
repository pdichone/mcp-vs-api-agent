"""How many tokens do the tool definitions cost, before the agent does anything?

Counts with the Claude API's count_tokens endpoint (free), as plain tool definitions, because
count_tokens doesn't accept the MCP connector. Same text the model sees either way.

    python tool_tokens.py             # API tools vs every MCP scope
    python tool_tokens.py --openapi   # plus "just point it at the OpenAPI spec"
"""

import json
import sys

import httpx
from anthropic import Anthropic

import agent_api
from common import MODEL, SYSTEM, TASK
from peek_mcp import tool_defs

OPENAPI = "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json"
METHODS = ("get", "post", "put", "patch", "delete")
client = Anthropic()


def count(tools: list[dict]) -> int:
    """Input tokens the tools add on top of the same system prompt and task."""
    base = dict(model=MODEL, system=SYSTEM, messages=[{"role": "user", "content": TASK}])
    with_tools = client.messages.count_tokens(**base, tools=tools).input_tokens if tools else 0
    return with_tools - client.messages.count_tokens(**base).input_tokens if tools else 0


def openapi_tools(path_filter: str = "") -> list[dict]:
    """Every operation in GitHub's OpenAPI spec as a tool: the 'just give it the spec' approach."""
    spec = httpx.get(OPENAPI, timeout=120, follow_redirects=True).json()
    refs = spec["components"]

    def resolve(node, depth=0):
        if depth > 6:
            return {"type": "object"}
        if isinstance(node, dict):
            if "$ref" in node:
                kind, name = node["$ref"].split("/")[-2:]
                return resolve(refs[kind][name], depth + 1)
            return {k: resolve(v, depth) for k, v in node.items() if k not in ("examples", "example", "x-github")}
        if isinstance(node, list):
            return [resolve(v, depth) for v in node]
        return node

    tools = []
    for path, ops in spec["paths"].items():
        if path_filter not in path:
            continue
        for method, op in ops.items():
            if method not in METHODS:
                continue
            props, required = {}, []
            for p in resolve(op.get("parameters", [])):
                props[p["name"]] = {**p.get("schema", {}), "description": p.get("description", "")[:300]}
                required += [p["name"]] if p.get("required") else []
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            if body:
                props["body"] = resolve(body)
            name = op["operationId"].replace("/", "__")[:64]
            tools.append({"name": name, "description": f"{op.get('summary', '')}. {op.get('description', '')}"[:1024],
                          "input_schema": {"type": "object", "properties": props, "required": required}})
    return tools


if __name__ == "__main__":
    rows = [
        ("API: 3 hand-written tools", [t.to_dict() for t in agent_api.TOOLS]),
        ("MCP: allowlist, 3 tools", [t for t in tool_defs("full") if t["name"] in ("search_issues", "issue_read", "list_issues")]),
        ("MCP: issues, read-only", tool_defs("issues")),
        ("MCP: default toolsets", tool_defs("full")),
        ("MCP: every toolset", tool_defs("all")),
    ]
    if "--openapi" in sys.argv:
        rows.append(("OpenAPI: issue endpoints only", openapi_tools("/issues")))
    print(f"{'config':32} {'tools':>9} {'chars':>9} {'tokens':>9}")
    for label, tools in rows:
        tokens = count(tools)
        print(f"{label:32} {len(tools):>9} {len(json.dumps(tools)):>9,} {tokens:>9,}")
    if "--openapi" in sys.argv:
        # Too many tools for one count_tokens request, so scale the issue subset's tokens-per-character
        everything = openapi_tools()
        chars = len(json.dumps(everything))
        estimate = round(chars * tokens / len(json.dumps(rows[-1][1])), -3)
        print(f"{'OpenAPI: whole spec':32} {len(everything):>9} {chars:>9,} {'~' + format(estimate, ',.0f'):>9} (estimated)")
