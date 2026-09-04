"""
Census EDGAR access layer (C4: politeness + resumability).
- Identified User-Agent, <= 5 req/sec (paced at 0.25s), retry on throttle.
- Every long pull checkpoints under data/census/raw/ (gitignored) and is
  resumable: cached artifacts are never refetched.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "data" / "census" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

import sys as _sys  # noqa: E402
_sys.path.insert(0, str(BASE / "src"))
from tark_data import sec_user_agent  # noqa: E402  (contact from TARK_SEC_CONTACT)


def ua() -> dict:
    return {"User-Agent": sec_user_agent()}
PACE = 0.25  # 4/sec < the 5/sec ceiling


def get(url: str, as_json: bool = True, retries: int = 3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=ua())
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            time.sleep(PACE)
            return json.loads(data) if as_json else data
        except urllib.error.HTTPError as e:
            if e.code == 404:  # a real miss — retrying only burns backoff
                time.sleep(PACE)
                raise
            if attempt == retries - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def cached_json(name: str, producer):
    """Checkpoint: data/census/raw/<name>.json holds the result; reruns load
    it instead of refetching."""
    p = RAW / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    out = producer()
    p.write_text(json.dumps(out))
    return out


def submissions(cik: int | str) -> dict:
    """Per-CIK submissions JSON, cached on disk forever (resume-safe)."""
    cik = int(cik)
    p = RAW / "submissions" / f"CIK{cik:010d}.json"
    p.parent.mkdir(exist_ok=True)
    if p.exists():
        return json.loads(p.read_text())
    d = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    p.write_text(json.dumps(d))
    return d


_ATOM_ENTRY = re.compile(
    r"<title>(.*?)</title>.*?CIK=(\d{7,10})", re.S)
# SIC-axis atom feeds carry no usable names (SEC "ARRAY(0x…)" bug in both
# title and name attributes) — only <cik> elements are reliable there; names
# are filled later from each entity's submissions JSON.
_ATOM_CIK = re.compile(r"<cik>(\d{7,10})</cik>")


def companies_by_query(label: str, **params) -> dict[str, str]:
    """Enumerate ALL companies matching a browse-edgar company query
    (form type and/or SIC). Returns {cik: name}. Paged 100 at a time,
    checkpointed per page so an interrupted pull resumes."""
    ck = RAW / f"enum_{label}.json"
    state = json.loads(ck.read_text()) if ck.exists() else {
        "start": 0, "done": False, "companies": {}}
    while not state["done"]:
        q = {"action": "getcompany", "company": "", "dateb": "",
             "owner": "include", "count": "100", "start": str(state["start"]),
             "output": "atom", **params}
        url = ("https://www.sec.gov/cgi-bin/browse-edgar?"
               + urllib.parse.urlencode(q))
        text = get(url, as_json=False).decode("utf-8", "ignore")
        found = 0
        for m in _ATOM_ENTRY.finditer(text):
            name = m.group(1).strip()
            if "EDGAR" in name and "Search" in name:
                continue
            cik = str(int(m.group(2)))
            if cik not in state["companies"]:
                state["companies"][cik] = re.sub(r"\s*\(\d{7,10}\)\s*$", "",
                                                 name).strip()
            found += 1
        if found == 0:  # SIC-axis feed variant: <cik> elements, no names
            for m in _ATOM_CIK.finditer(text):
                cik = str(int(m.group(1)))
                state["companies"].setdefault(cik, "")
                found += 1
        state["start"] += 100
        if found < 100:
            state["done"] = True
        ck.write_text(json.dumps(state))
        print(f"  enum {label}: {len(state['companies'])} companies"
              f"{'' if state['done'] else ' …'}", flush=True)
    return state["companies"]


def company_tickers() -> dict[int, list[str]]:
    """The listing oracle: SEC company_tickers.json -> {cik: [tickers]}."""
    def produce():
        t = get("https://www.sec.gov/files/company_tickers.json")
        out: dict[str, list[str]] = {}
        for row in t.values():
            out.setdefault(str(row["cik_str"]), []).append(row["ticker"])
        return out
    return {int(k): v for k, v in cached_json("company_tickers", produce).items()}
