"""Shared setup for both agents: one model, one task, one way to measure a run."""

import os
import time
from dataclasses import asdict, dataclass, field

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("MODEL", "claude-opus-5-5")
EFFORT = os.getenv("EFFORT", "medium")  # Opus 5.5's default; set explicitly so both runs match
REPO = os.getenv("REPO", "modelcontextprotocol/python-sdk")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# $ per million tokens, Claude Opus 5.5 (platform.claude.com pricing). Change with MODEL.
PRICE = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}

SYSTEM = (
    "You are a GitHub issue-triage assistant. You only read; never create, edit, "
    "comment, or merge anything. Use the tools to get real numbers; don't guess."
)

TASK = f"""In the GitHub repo {REPO}, find the 5 open issues labeled "bug" with the most comments (issues only, not pull requests).
For each one give: the number, the title, the comment count, and one sentence on what users are actually reporting, based on the issue and its most recent comments.
Finish with the one you'd fix first, and why, in two sentences."""


@dataclass
class RunResult:
    way: str
    model: str = MODEL
    api_calls: int = 0      # requests to the Claude API
    tool_calls: int = 0     # tool calls the model made (yours or the MCP server's)
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    stop_reason: str = ""
    answer: str = ""
    tools_used: list[str] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter, repr=False)

    def add(self, message) -> None:
        """Fold one API response into the totals."""
        self.api_calls += 1
        u = message.usage
        self.input_tokens += u.input_tokens or 0
        self.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.output_tokens += u.output_tokens or 0
        for block in message.content:
            if block.type in ("tool_use", "mcp_tool_use", "server_tool_use"):
                self.tool_calls += 1
                self.tools_used.append(block.name)
        text = "".join(b.text for b in message.content if b.type == "text")
        if text.strip():
            self.answer = text
        self.stop_reason = message.stop_reason or ""

    def finish(self) -> "RunResult":
        self.seconds = round(time.perf_counter() - self._t0, 1)
        return self

    @property
    def cost(self) -> float:
        return (
            self.input_tokens * PRICE["input"]
            + self.output_tokens * PRICE["output"]
            + self.cache_read_tokens * PRICE["cache_read"]
            + self.cache_write_tokens * PRICE["cache_write"]
        ) / 1_000_000

    def report(self) -> str:
        return (
            f"[{self.way}] {self.seconds}s · {self.api_calls} API calls · {self.tool_calls} tool calls · "
            f"in {self.input_tokens:,} (+{self.cache_read_tokens:,} cached) · out {self.output_tokens:,} · "
            f"${self.cost:.3f} · stop={self.stop_reason}"
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_t0")
        d["cost"] = round(self.cost, 4)
        return d
