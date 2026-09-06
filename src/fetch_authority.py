"""
Fetch the proposed rule's own words from the Federal Register.
==============================================================
Document: 91 FR 16088 (March 31, 2026), Federal Register document
2026-06178, RIN 1210-AC38, proposed 29 CFR 2550.404a-6. The script
downloads the document metadata and the full-text XML from the Federal
Register API, verifies the citation and the RIN, and writes paragraphs
(g) through (l) of proposed section 2550.404a-6 verbatim, one paragraph
per line, with a manifest row that carries the source URL, the fetch time
and two content hashes (the XML as served, the markdown as written).

It never paraphrases. If the section or a paragraph cannot be located in
the XML it writes nothing and exits non-zero. Inside a paragraph, runs of
whitespace (the XML wraps long paragraphs over several lines) are
collapsed to one space. No word, number or punctuation mark is changed.

Runbook for the person who runs it (a networked machine, repository root)
-------------------------------------------------------------------------
1. Activate the virtualenv and set the contact the fetchers identify with:
       export TARK_SEC_CONTACT='Your Name your@email'
   The contact comes from the environment, never from source.
2. Run:
       python src/fetch_authority.py
3. Files that appear:
       data/authority/2550-404a-6_proposed.md   paragraphs (g) to (l), verbatim
       data/authority/manifest.csv              one row for the document (see
                                                MANIFEST_COLUMNS), including the
                                                sha256 of the .md as written
       data/raw/authority/2026-06178.xml        the XML as served (data/raw/ is
                                                not tracked, like the filings)
4. Rebuild (python src/build_site.py) and run the hook. The Authority panel
   and the memos switch from "not yet in this build" to the verbatim
   paragraphs only when the .md exists AND the manifest row's content hash
   matches the file byte for byte. A file without its row stays "not fetched".
5. Commit data/authority/2550-404a-6_proposed.md and
   data/authority/manifest.csv together, in one commit that names the task.

Options
-------
    --out DIR    write the .md and manifest.csv under DIR (the XML under
                 DIR/raw/). DIR may be outside the repository: nothing in
                 the repository is touched, and the manifest records the
                 absolute path.
    --xml FILE   parse a local XML file instead of fetching (offline tests).
                 Requires --out, so a fixture run never writes into
                 data/authority/.

Manifest
--------
The authority document is not an EDGAR filing: it has no CIK, no accession
number and no primary document, so it does not get a row in
data/manifest.csv (whose columns are those of an EDGAR pull). It has its own
manifest, data/authority/manifest.csv, with the columns in MANIFEST_COLUMNS.
tark_data.authority() reads that manifest and admits the text into a build
only when the row's content_sha256 equals the sha256 of the file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import (AUTHORITY_FILE, AUTHORITY_MANIFEST, AUTHORITY_MANIFEST_COLUMNS,  # noqa: E402
                       BASE, DATA, sec_user_agent)

DOC = "2026-06178"
API = f"https://www.federalregister.gov/api/v1/documents/{DOC}.json"
CITATION = "91 FR 16088"
RIN = "1210-AC38"
SECTION = "2550.404a-6"
PARAS = ["g", "h", "i", "j", "k", "l"]
MANIFEST_COLUMNS = AUTHORITY_MANIFEST_COLUMNS

TOP_RE = re.compile(r"^\(([a-z])\)")
# a paragraph that starts "(i)", "(v)" or "(x)" may be a top-level letter or
# a roman sub-paragraph. It is the letter only when it is the next letter in
# sequence and the following paragraph is not the next roman numeral.
ROMAN_NEXT = {"i": "ii", "v": "vi", "x": "xi"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": sec_user_agent(),
                                               "Accept": "application/json, text/xml"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(text: str) -> str:
    """Runs of whitespace inside a paragraph become one space. Nothing else."""
    return re.sub(r"\s+", " ", text).strip()


def section_paragraphs(xml_bytes: bytes) -> list[str]:
    """Every <P> of the SECTION whose SECTNO names 2550.404a-6, in order,
    whitespace-normalized, empty paragraphs dropped."""
    root = ET.fromstring(xml_bytes)
    for sect in root.iter("SECTION"):
        no_el = sect.find("SECTNO")
        no = "".join(no_el.itertext()) if no_el is not None else ""
        if SECTION not in no:
            continue
        paras = [normalize("".join(p.itertext())) for p in sect.iter("P")]
        paras = [p for p in paras if p]
        if paras:
            return paras
    raise SystemExit(f"section {SECTION} not found in the XML")


def is_top_level(letter: str, expected: str | None, following: str) -> bool:
    if expected is None:
        return letter not in ROMAN_NEXT
    if letter != expected:
        return False
    if letter in ROMAN_NEXT and following.startswith(f"({ROMAN_NEXT[letter]})"):
        return False
    return True


def select(paragraphs: list[str], letters: list[str]) -> dict[str, list[str]]:
    """Paragraphs (g) to (l) with every sub-paragraph, keyed by letter.
    Top-level letters run in sequence, so "(i)" opens paragraph (i) only
    right after (h) and only when "(ii)" does not follow it."""
    out: dict[str, list[str]] = {}
    expected: str | None = None
    current: str | None = None
    for n, p in enumerate(paragraphs):
        m = TOP_RE.match(p)
        following = paragraphs[n + 1] if n + 1 < len(paragraphs) else ""
        if m and is_top_level(m.group(1), expected, following):
            letter = m.group(1)
            expected = chr(ord(letter) + 1)
            current = letter if letter in letters else None
            if current:
                out[current] = [p]
            continue
        if current:
            out[current].append(p)
    missing = [x for x in letters if x not in out]
    if missing:
        raise SystemExit(f"paragraphs not located verbatim: {missing}")
    return out


def render(meta: dict, source_sha: str, fetched_at: str, paras: dict[str, list[str]]) -> str:
    """The markdown: one '## (x)' heading per letter, one '> ' line per
    paragraph, a bare '>' between paragraphs. parse_authority reads exactly
    this shape."""
    lines = [f"# Proposed 29 CFR {SECTION}, paragraphs (g) to (l), verbatim",
             "",
             f"Source: Federal Register document {DOC}, {meta['citation']}, published "
             f"{meta['publication_date']}, RIN {', '.join(meta.get('regulation_id_numbers') or [])}, "
             f"docket {', '.join(meta.get('docket_ids') or [])}.",
             f"Fetched {fetched_at} from {meta['full_text_xml_url']} "
             f"(sha256 of the XML as served {source_sha}). HTML: {meta.get('html_url')}.",
             "",
             "Every paragraph below is the Federal Register text. Runs of whitespace "
             "inside a paragraph are collapsed to one space. No word, number or "
             "punctuation mark is Tark's.",
             ""]
    for letter in PARAS:
        lines.append(f"## ({letter})")
        lines.append("")
        for p in paras[letter]:
            lines.append(f"> {p}")
            lines.append(">")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def local_path_of(path: Path) -> str:
    """Repository-relative when inside the repository, else absolute. Never
    a crash for an --out outside the tree."""
    path = path.resolve()
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def write_manifest(mpath: Path, row: dict) -> None:
    """Append or replace the row for this local_path, all columns named."""
    rows: list[dict] = []
    if mpath.exists():
        with mpath.open(newline="", encoding="utf-8") as fh:
            rdr = csv.DictReader(fh)
            if rdr.fieldnames != MANIFEST_COLUMNS:
                raise SystemExit(f"{mpath} has columns {rdr.fieldnames}, expected {MANIFEST_COLUMNS}")
            rows = [r for r in rdr if r["local_path"] != row["local_path"]]
    rows.append(row)
    with mpath.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def write(out_dir: Path, raw_dir: Path, meta: dict, xml_bytes: bytes,
          paras: dict[str, list[str]], fetched_at: str) -> tuple[Path, dict]:
    """The .md, the XML as served and the manifest row. Returns the .md path
    and the row."""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_sha = sha256(xml_bytes)
    xml_path = raw_dir / f"{DOC}.xml"
    xml_path.write_bytes(xml_bytes)
    text = render(meta, source_sha, fetched_at, paras)
    path = out_dir / AUTHORITY_FILE
    path.write_text(text, encoding="utf-8")
    row = {
        "document": f"Federal Register {DOC}",
        "citation": meta["citation"],
        "rin": ", ".join(meta.get("regulation_id_numbers") or []),
        "section": SECTION,
        "paragraphs": "(g) to (l)",
        "publication_date": meta["publication_date"],
        "source_url": meta["full_text_xml_url"],
        "html_url": meta.get("html_url") or "",
        "fetched_at_utc": fetched_at,
        "source_sha256": source_sha,
        "source_local_path": local_path_of(xml_path),
        "local_path": local_path_of(path),
        "content_sha256": sha256(path.read_bytes()),
        "paragraph_count": str(sum(len(v) for v in paras.values())),
    }
    write_manifest(out_dir / AUTHORITY_MANIFEST, row)
    return path, row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="output directory (default data/authority)")
    ap.add_argument("--xml", help="parse a local XML file instead of fetching (tests, requires --out)")
    a = ap.parse_args()
    if a.xml and not a.out:
        raise SystemExit("--xml requires --out: a fixture run never writes into data/authority")
    out_dir = Path(a.out).resolve() if a.out else (DATA / "authority")
    inside = out_dir == (DATA / "authority")
    raw_dir = (DATA / "raw" / "authority") if inside else (out_dir / "raw")
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if a.xml:
        xml_bytes = Path(a.xml).read_bytes()
        meta = {"citation": CITATION, "publication_date": "2026-03-31",
                "regulation_id_numbers": [RIN], "docket_ids": ["EBSA-2026-0166"],
                "full_text_xml_url": f"file://{Path(a.xml).resolve()}", "html_url": ""}
    else:
        meta = json.loads(get(API))
        if meta.get("citation") != CITATION or RIN not in (meta.get("regulation_id_numbers") or []):
            raise SystemExit(f"identity check failed: citation {meta.get('citation')!r}, "
                             f"RINs {meta.get('regulation_id_numbers')!r}")
        xml_bytes = get(meta["full_text_xml_url"])
    paras = select(section_paragraphs(xml_bytes), PARAS)
    path, row = write(out_dir, raw_dir, meta, xml_bytes, paras, fetched_at)
    print(f"wrote {path} ({row['paragraph_count']} paragraphs, sha256 {row['content_sha256']})")
    print(f"manifest row in {out_dir / AUTHORITY_MANIFEST}, XML in {raw_dir / (DOC + '.xml')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
