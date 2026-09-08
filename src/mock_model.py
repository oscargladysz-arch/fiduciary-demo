"""
A mocked model client for the ingest gate and the mocked-model job
(decision 8.17: no test calls the real API). It answers each cell from a
canned fixture, reports the token usage the fixture states, counts tokens
by a character rule, and can fail on a schedule so the retry, the per-cell
writes and the stops are exercised without a network.

    answers, usage, default_usage = canned_answers(doc.label)
    client = MockClient(answers, usage, default_usage, fail={"2.1": [SomeError()]})
    run_extraction(client, key, docs, model="mock-model", ...)
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ingest import CellExtraction

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CANNED_PATH = FIXTURES / "ingest_canned.json"
FILING_PATH = FIXTURES / "ingest_filing_synthetic.htm"
IXBRL_PATH = FIXTURES / "ingest_ixbrl_synthetic.htm"
PDFTEXT_PATH = FIXTURES / "ingest_pdftotext_synthetic.txt"


def canned_answers(doc_label: str, path: Path | None = None) -> tuple[dict[str, CellExtraction], dict[str, dict], dict]:
    """The fixture's answers keyed by cell, its per-cell usage, and the usage
    every other call reports. $DOC in a source_doc becomes the label given."""
    raw = json.loads((path or CANNED_PATH).read_text())
    answers, usage = {}, {}
    for cid, a in raw["cells"].items():
        a = dict(a)
        u = a.pop("usage", None)
        if u:
            usage[cid] = u
        a["source_doc"] = a["source_doc"].replace("$DOC", doc_label)
        answers[cid] = CellExtraction(**a)
    return answers, usage, dict(raw["default_usage"])


class FakeClock:
    """A clock the mock advances per call, so a time budget is deterministic."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class MockResponse:
    def __init__(self, parsed, usage: dict, stop_reason: str = "end_turn"):
        self.parsed_output = parsed
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(**usage)


class _Messages:
    def __init__(self, owner: "MockClient"):
        self._o = owner

    @staticmethod
    def cell_of(kw: dict) -> str:
        return kw["messages"][0]["content"][1]["text"].split(",")[0].replace("Cell ", "")

    def parse(self, **kw):
        o = self._o
        o.calls.append(kw)
        cid = self.cell_of(kw)
        if o.clock is not None:
            o.clock.advance(o.latency_s)
        pending = o.fail.get(cid) or []
        if pending:
            raise pending.pop(0)
        answer = o.answers.get(cid) or CellExtraction(
            found=False, value="", quote="", source_doc="", section="", not_found_reason=f"no passage for {cid}")
        return MockResponse(answer, o.usage.get(cid) or o.default_usage)

    def count_tokens(self, **kw):
        if not self._o.can_count:
            raise AttributeError("count_tokens")
        chars = len(kw.get("system") or "")
        for m in kw.get("messages", []):
            for block in m.get("content", []):
                chars += len(block.get("text", ""))
        self._o.count_calls += 1
        return SimpleNamespace(input_tokens=chars // self._o.chars_per_token)


class MockClient:
    """messages.parse answers from the canned dict, messages.count_tokens
    counts characters. fail maps a cell id to the exceptions its successive
    attempts raise (then it answers normally)."""

    def __init__(self, answers: dict[str, CellExtraction], usage: dict[str, dict] | None = None,
                 default_usage: dict | None = None, *, fail: dict[str, list[BaseException]] | None = None,
                 clock: FakeClock | None = None, latency_s: float = 0.0, can_count: bool = True,
                 chars_per_token: int = 4):
        self.answers = dict(answers)
        self.usage = dict(usage or {})
        self.default_usage = dict(default_usage or {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                                    "cache_read_input_tokens": 0, "output_tokens": 0})
        self.fail = {k: list(v) for k, v in (fail or {}).items()}
        self.clock = clock
        self.latency_s = latency_s
        self.can_count = can_count
        self.chars_per_token = chars_per_token
        self.calls: list[dict] = []
        self.count_calls = 0
        self.messages = _Messages(self)


def context_error(message: str = "prompt is too long: exceeds the context window") -> Exception:
    """A request-too-large error of the SDK's own class when the SDK is
    installed, a stand-in of the same name otherwise."""
    try:
        import anthropic
        import httpx
        return anthropic.BadRequestError(
            message, response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
            body=None)
    except ImportError:
        return type("BadRequestError", (Exception,), {})(message)
