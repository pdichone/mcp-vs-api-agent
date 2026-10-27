"""Run every configuration N times on the same task and write the scoreboard.

    python bench.py              # 3 runs each, about $3-5 on Opus 5.5
    python bench.py --runs 1     # one pass, for a smoke test
    python bench.py --only api mcp-full
"""

import argparse
import json
import re
import statistics
from pathlib import Path

import agent_api
import agent_mcp
from agent_api import search_issues
from common import MODEL, REPO

CONFIGS = {
    "api": lambda: agent_api.run(),
    "mcp-full": lambda: agent_mcp.run(scope="full"),
    "mcp-issues": lambda: agent_mcp.run(scope="issues"),
    "mcp-allow": lambda: agent_mcp.run(scope="allow"),
    "mcp-search": lambda: agent_mcp.run(scope="full", search=True),
}
OUT = Path("results")


def ground_truth() -> set[int]:
    """The right answer, straight from GitHub, no model involved."""
    items = json.loads(search_issues.call({"query": f"repo:{REPO} is:issue is:open label:bug", "limit": 5}))
    return {i["number"] for i in items}


def score(answer: str, truth: set[int]) -> int:
    found = {int(n) for n in re.findall(r"#(\d+)", answer)}
    return len(truth & found)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--only", nargs="*", choices=CONFIGS, default=list(CONFIGS))
    a = p.parse_args()

    OUT.mkdir(exist_ok=True)
    truth = ground_truth()
    print(f"Ground truth for {REPO}: {sorted(truth)}\n")
    runs: dict[str, list[dict]] = {}
    with open(OUT / "runs.jsonl", "a") as log:
        for name in a.only:
            for i in range(a.runs):
                try:
                    r = CONFIGS[name]()
                except Exception as e:  # a failed run is a result too
                    print(f"[{name}] run {i + 1} FAILED: {e!r}")
                    runs.setdefault(name, []).append({"failed": repr(e)})
                    continue
                row = {**r.to_dict(), "config": name, "correct": score(r.answer, truth)}
                log.write(json.dumps(row) + "\n")
                runs.setdefault(name, []).append(row)
                print(r.report(), f"· {row['correct']}/5 correct")

    lines = [f"Model {MODEL} · repo {REPO} · {a.runs} runs each · medians\n",
             "| config | input tokens | output tokens | tool calls | seconds | $ per run | correct | failed |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, rows in runs.items():
        ok = [r for r in rows if "failed" not in r]
        med = lambda k: statistics.median(r[k] for r in ok) if ok else 0  # noqa: E731
        lines.append(
            f"| {name} | {med('input_tokens'):,.0f} | {med('output_tokens'):,.0f} | {med('tool_calls'):.0f} | "
            f"{med('seconds'):.1f} | ${med('cost'):.3f} | {med('correct'):.0f}/5 | {len(rows) - len(ok)} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
