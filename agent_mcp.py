"""Way 2: the MCP way. No tool code: GitHub's official MCP server, connected through the Claude API.

    python agent_mcp.py                 # everything GitHub's server exposes by default
    python agent_mcp.py --scope issues  # only the issues toolset, read-only (scoped on GitHub's side)
    python agent_mcp.py --scope allow   # full server, but only 3 tools enabled (scoped on my side)
    python agent_mcp.py --search        # full server, every tool deferred behind tool search
"""

import argparse

from anthropic import Anthropic

from common import EFFORT, GITHUB_TOKEN, MODEL, SYSTEM, TASK, RunResult

BETA = "mcp-client-2025-11-20"
URLS = {
    "full": "https://api.githubcopilot.com/mcp/",
    "issues": "https://api.githubcopilot.com/mcp/x/issues/readonly",
    "allow": "https://api.githubcopilot.com/mcp/",
}
ALLOWED = ["search_issues", "issue_read", "list_issues"]


def toolset(scope: str, search: bool) -> list[dict]:
    ts = {"type": "mcp_toolset", "mcp_server_name": "github"}
    if scope == "allow":  # allowlist: every tool off, then turn three back on
        ts["default_config"] = {"enabled": False}
        ts["configs"] = {name: {"enabled": True} for name in ALLOWED}
    if search:  # tool definitions stay out of context until the model searches for them
        ts["default_config"] = {**ts.get("default_config", {}), "defer_loading": True}
        return [ts, {"type": "tool_search_tool_bm25_20251119", "name": "tool_search_tool_bm25"}]
    return [ts]


def run(task: str = TASK, scope: str = "full", search: bool = False) -> RunResult:
    client = Anthropic()
    result = RunResult(f"mcp-{scope}" + ("+search" if search else ""))
    messages = [{"role": "user", "content": task}]
    while True:
        message = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": EFFORT},
            betas=[BETA],
            mcp_servers=[{"type": "url", "name": "github", "url": URLS[scope],
                          "authorization_token": GITHUB_TOKEN}],
            tools=toolset(scope, search),
            messages=messages,
        )
        result.add(message)
        if message.stop_reason != "pause_turn":  # Anthropic runs the MCP calls server-side
            break
        messages.append({"role": "assistant", "content": message.content})
    return result.finish()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scope", choices=URLS, default="full")
    p.add_argument("--search", action="store_true")
    p.add_argument("task", nargs="?", default=TASK)
    a = p.parse_args()
    r = run(a.task, a.scope, a.search)
    print(r.answer, "\n")
    print(r.report())
