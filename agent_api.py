"""Way 1: the API way. Three tools I wrote myself over the GitHub REST API."""

import json
import sys

import httpx
from anthropic import Anthropic, beta_tool

from common import EFFORT, GITHUB_TOKEN, MODEL, SYSTEM, TASK, RunResult

gh = httpx.Client(
    base_url="https://api.github.com",
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
    timeout=30,
)


def get(path: str, **params):
    r = gh.get(path, params=params)
    r.raise_for_status()
    return r.json()


@beta_tool
def search_issues(query: str, sort: str = "comments", limit: int = 10) -> str:
    """Search GitHub issues with GitHub search syntax.

    Args:
        query: e.g. 'repo:owner/name is:issue is:open label:bug'.
        sort: 'comments', 'created', 'updated', or 'reactions'. Highest first.
        limit: Max results, 1-30.
    """
    items = get("/search/issues", q=query, sort=sort, order="desc", per_page=min(limit, 30))["items"]
    return json.dumps([
        {"number": i["number"], "title": i["title"], "comments": i["comments"],
         "labels": [l["name"] for l in i["labels"]], "is_pr": "pull_request" in i}
        for i in items
    ])


@beta_tool
def get_issue(repo: str, number: int) -> str:
    """Get one issue: title, state, labels, comment count, and the first 1,500 characters of the body.

    Args:
        repo: 'owner/name'.
        number: The issue number.
    """
    i = get(f"/repos/{repo}/issues/{number}")
    return json.dumps({"number": i["number"], "title": i["title"], "state": i["state"],
                       "labels": [l["name"] for l in i["labels"]], "comments": i["comments"],
                       "body": (i["body"] or "")[:1500]})


@beta_tool
def get_comments(repo: str, number: int, last: int = 3) -> str:
    """Get the most recent comments on an issue: author, date, first 600 characters each.

    Args:
        repo: 'owner/name'.
        number: The issue number.
        last: How many of the newest comments to return, 1-10.
    """
    comments = get(f"/repos/{repo}/issues/{number}/comments", per_page=100)[-min(last, 10):]
    return json.dumps([{"author": c["user"]["login"], "date": c["created_at"][:10],
                        "body": c["body"][:600]} for c in comments])


TOOLS = [search_issues, get_issue, get_comments]


def run(task: str = TASK) -> RunResult:
    client = Anthropic()
    result = RunResult("api")
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": EFFORT},
        tools=TOOLS,
        messages=[{"role": "user", "content": task}],
    )
    for message in runner:  # one iteration per API call; the runner executes my tools in between
        result.add(message)
    return result.finish()


if __name__ == "__main__":
    r = run(sys.argv[1] if len(sys.argv) > 1 else TASK)
    print(r.answer, "\n")
    print(r.report())
