"""What does an MCP server actually send the model? One HTTP POST, no SDK.

    python peek_mcp.py            # GitHub's default toolsets
    python peek_mcp.py issues     # issues toolset, read-only
    python peek_mcp.py all        # every toolset
"""

import json
import sys

import httpx

from common import GITHUB_TOKEN

URLS = {
    "full": "https://api.githubcopilot.com/mcp/",
    "issues": "https://api.githubcopilot.com/mcp/x/issues/readonly",
    "all": "https://api.githubcopilot.com/mcp/x/all",
}
VERSION = "2026-07-28"  # the stateless spec: no initialize handshake, no session id


def rpc(url: str, method: str) -> dict:
    r = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/json, text/event-stream",
            "Mcp-Protocol-Version": VERSION,
            "Mcp-Method": method,
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method,
              "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": VERSION,
                                   "io.modelcontextprotocol/clientCapabilities": {}}}},
        timeout=30,
    )
    r.raise_for_status()
    body = r.text.split("data: ", 1)[1] if r.text.startswith("event:") else r.text  # SSE or plain JSON
    return json.loads(body)["result"]


def tool_defs(scope: str = "full") -> list[dict]:
    """The server's tools, in the shape the Claude API takes them."""
    return [{"name": t["name"], "description": t.get("description", ""), "input_schema": t["inputSchema"]}
            for t in rpc(URLS[scope], "tools/list")["tools"]]


if __name__ == "__main__":
    scope = sys.argv[1] if len(sys.argv) > 1 else "full"
    tools = rpc(URLS[scope], "tools/list")["tools"]
    writes = [t["name"] for t in tools if not t.get("annotations", {}).get("readOnlyHint")]
    print(f"{len(tools)} tools, {len(json.dumps(tool_defs(scope))):,} characters of definitions")
    print(f"{len(writes)} can change things:", ", ".join(sorted(writes)) or "none")
    print("\nFirst tool, exactly as the model sees it:")
    print(json.dumps(tool_defs(scope)[0], indent=2)[:1200])
