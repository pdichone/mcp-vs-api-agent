# MCP vs API: the same agent, built both ways

One GitHub issue-triage agent, one model, one task. Built once with three tools I wrote over the GitHub REST API, and once with GitHub's official MCP server through the Claude API's MCP connector. Then measured: code, tokens, time, dollars, and whether the answer was right.

Video: [link]

## The task

> In `modelcontextprotocol/python-sdk`, find the 5 open issues labeled "bug" with the most comments. For each: number, title, comment count, and one sentence on what users are reporting. Then say which one you'd fix first.

The grader is not a model: `bench.py` asks GitHub for the real top 5 and checks the answer names all five numbers.

## Run it

```bash
git clone https://github.com/pdichone/mcp-vs-api-agent && cd mcp-vs-api-agent
uv venv && source .venv/bin/activate && uv pip install -r pyproject.toml
cp .env.example .env    # ANTHROPIC_API_KEY, GITHUB_TOKEN (read-only is enough; `gh auth token` works)

python peek_mcp.py              # what GitHub's MCP server hands the model: one POST, no SDK
python agent_api.py             # Way 1: hand-written tools over the REST API
python agent_mcp.py             # Way 2: GitHub's MCP server, default toolsets
python agent_mcp.py --scope issues   # Way 2, scoped to read-only issue tools on GitHub's side
python agent_mcp.py --scope allow    # Way 2, three tools allowlisted on my side
python agent_mcp.py --search         # Way 2, every tool deferred behind tool search
python tool_tokens.py --openapi # what each tool list costs before the agent does anything
python bench.py                 # all five configs, 3 runs each, writes results/summary.md
```

`bench.py` costs a few dollars on Claude Opus 5.5 (about $3-5 for 15 runs). `tool_tokens.py` and `peek_mcp.py` are free.

## Files

| File | What |
|---|---|
| `common.py` | model, effort, task, system prompt, and the run meter (tokens, calls, seconds, $) |
| `agent_api.py` | Way 1: `search_issues`, `get_issue`, `get_comments` with `@beta_tool`, driven by the SDK's tool runner |
| `agent_mcp.py` | Way 2: `mcp_servers` + `mcp_toolset` (beta `mcp-client-2025-11-20`); scopes and tool search |
| `peek_mcp.py` | raw JSON-RPC `tools/list` against GitHub's server on the stateless 2026-07-28 spec |
| `tool_tokens.py` | definition cost per config via `count_tokens`, plus GitHub's OpenAPI spec as tools |
| `bench.py` | runs everything, grades against GitHub, writes `results/summary.md` |

## Results

See `results/summary.md` for my numbers (model, date, and versions are in its first line). Yours will drift: issue counts change, GitHub's server changes its tools, and models change. That's the point of shipping the bench instead of a screenshot.

## Notes

- Same `EFFORT` for every run (`medium`, Opus 5.5's default, set explicitly). No sampling parameters: API version `2026-10-21` rejects `temperature`.
- No refusal fallback on purpose: a fallback would swap the model mid-benchmark. A refused run shows up as `stop=refusal`.
- The MCP connector can't send custom headers, so scoping uses GitHub's URL paths (`/mcp/x/issues/readonly`) or the toolset allowlist (`default_config` + `configs`).
- `count_tokens` doesn't accept the MCP connector, so `tool_tokens.py` counts the server's `tools/list` as plain tool definitions: the same text the model receives.

MIT licensed.
