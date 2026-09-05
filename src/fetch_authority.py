"""
Fetch the proposed rule's own words from the Federal Register.
    python src/fetch_authority.py [--out data/authority]

Document: 91 FR 16088 (March 31, 2026), Federal Register document
2026-06178, RIN 1210-AC38, proposed 29 CFR 2550.404a-6. The script
downloads the document metadata and the full-text XML from the Federal
Register API, verifies the citation and the RIN, and writes paragraphs
(g) through (l) of proposed section 2550.404a-6 VERBATIM to
data/authority/2550-404a-6_proposed.md, with the source URL, the fetch
date and the sha256 of the XML. It appends one row to data/manifest.csv.

It never paraphrases. If the section or a paragraph cannot be located
verbatim in the XML it writes nothing and exits non-zero. In the 2026-09
build container federalregister.gov is blocked by the egress policy, so
this script is written and tested for its parsing on a fixture, and run
on a machine with network. Surfaces render the file when present and say
"regulatory text not yet fetched into this build" when absent.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import BASE, DATA, sec_user_agent  # noqa: E402

DOC = "2026-06178"
API = f"https://www.federalregister.gov/api/v1/documents/{DOC}.json"
CITATION = "91 FR 16088"
RIN = "1210-AC38"
SECTION = "2550.404a-6"
PARAS = ["g", "h", "i", "j", "k", "l"]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": sec_user_agent(),
                                               "Accept": "application/json, text/xml"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def section_paragraphs(xml_bytes: bytes) -> list[str]:
    """All <P> texts of the SECTION whose SECTNO names 2550.404a-6, in order."""
    root = ET.fromstring(xml_bytes)
    for sect in root.iter("SECTION"):
        no = "".join(sect.find("SECTNO").itertext()) if sect.find("SECTNO") is not None else ""
        if SECTION in no:
            return ["".join(p.itertext()).strip() for p in sect.iter("P")]
    raise SystemExit(f"section {SECTION} not found in the XML")


def select(paragraphs: list[str], letters: list[str]) -> dict[str, list[str]]:
    """Paragraphs (g) to (l) with their sub-paragraphs, keyed by letter.
    A top-level paragraph starts with '(x)' for a single lower-case letter."""
    out: dict[str, list[str]] = {}
    current = None
    for p in paragraphs:
        m = re.match(r"^\(([a-z])\)", p)
        if m:
            current = m.group(1) if m.group(1) in letters else None
            if current:
                out[current] = [p]
            continue
        if current:
            out[current].append(p)
    missing = [x for x in letters if x not in out]
    if missing:
        raise SystemExit(f"paragraphs not located verbatim: {missing}")
    return out


def write(out_dir: Path, meta: dict, xml_bytes: bytes, paras: dict[str, list[str]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(xml_bytes).hexdigest()
    lines = [f"# Proposed 29 CFR {SECTION}, paragraphs (g) to (l), verbatim",
             "",
             f"Source: Federal Register document {DOC}, {meta['citation']}, published "
             f"{meta['publication_date']}, RIN {', '.join(meta.get('regulation_id_numbers') or [])}, "
             f"docket {', '.join(meta.get('docket_ids') or [])}.",
             f"Fetched {date.today().isoformat()} from {meta['full_text_xml_url']} "
             f"(sha256 {sha}). HTML: {meta.get('html_url')}.",
             "",
             "Every paragraph below is the Federal Register text unchanged. Nothing "
             "here is Tark's wording.",
             ""]
    for letter in PARAS:
        lines.append(f"## ({letter})")
        lines.append("")
        for p in paras[letter]:
            lines.append(f"> {p}")
            lines.append(">")
        lines.append("")
    path = out_dir / f"{SECTION.replace('.', '-')}_proposed.md"
    path.write_text("\n".join(lines).rstrip("\n") + "\n")
    return path


def manifest_row(path: Path, meta: dict, xml_bytes: bytes) -> None:
    """Append one row to data/manifest.csv using whatever columns it has."""
    mpath = DATA / "manifest.csv"
    with mpath.open() as f:
        header = next(csv.reader(f))
    values = {
        "product": "authority", "product_key": "authority",
        "doc": f"Federal Register {DOC}", "document": f"Federal Register {DOC}",
        "doc_type": "FR proposed rule", "form": "FR proposed rule",
        "date": meta["publication_date"], "filed": meta["publication_date"],
        "accession": f"n/a - Federal Register document {DOC}",
        "url": meta["full_text_xml_url"], "source_url": meta["full_text_xml_url"],
        "local_path": str(path.relative_to(BASE)), "path": str(path.relative_to(BASE)),
        "sha256": hashlib.sha256(xml_bytes).hexdigest(),
        "note": f"{meta['citation']}, RIN {RIN}, paragraphs (g) to (l) of {SECTION} verbatim",
        "pulled": date.today().isoformat(), "date_pulled": date.today().isoformat(),
    }
    with mpath.open("a", newline="") as f:
        csv.writer(f).writerow([values.get(c, "") for c in header])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DATA / "authority"))
    ap.add_argument("--xml", help="parse a local XML file instead of fetching (tests)")
    a = ap.parse_args()
    if a.xml:
        xml_bytes = Path(a.xml).read_bytes()
        meta = {"citation": CITATION, "publication_date": "2026-03-31",
                "regulation_id_numbers": [RIN], "docket_ids": ["EBSA-2026-0166"],
                "full_text_xml_url": f"file://{a.xml}", "html_url": ""}
    else:
        meta = json.loads(get(API))
        if meta.get("citation") != CITATION or RIN not in (meta.get("regulation_id_numbers") or []):
            raise SystemExit(f"identity check failed: citation {meta.get('citation')!r}, "
                             f"RINs {meta.get('regulation_id_numbers')!r}")
        xml_bytes = get(meta["full_text_xml_url"])
    paras = select(section_paragraphs(xml_bytes), PARAS)
    path = write(Path(a.out), meta, xml_bytes, paras)
    if not a.xml:
        manifest_row(path, meta, xml_bytes)
    print(f"wrote {path} ({sum(len(v) for v in paras.values())} paragraphs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
