"""Copy gate: no em dash and no semicolon in user-facing copy.
    python src/test_copy.py [--only <path>] [--show N]

Scope
  - every string and template literal in site/js/*.js
  - every string constant in the Python modules that write surface text
    (SURFACE_MODULES below) and in app.py
  - the documents this engagement owns (OWNED_DOCS), outside fenced code
    blocks and blockquotes

Exempt, and why
  - regex patterns (a character class is not prose)
  - strings with no letters once HTML tags and entities are stripped: a
    lone dash glyph in an empty table cell is a symbol, not punctuation
  - inline CSS declarations and HTML attribute plumbing (code, not copy)
  - a line carrying the marker `copy-exempt` (state the reason next to it)
  - data/ (verbatim filing quotes) and docs/verification_queue.md (its row
    format is what the queue parser reads)
Formulas use * and /. Verbatim quotes keep their punctuation.
"""
import ast
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SURFACE_MODULES = [
    "tark_memo.py", "tark_liquidity.py", "tark_benchmark.py", "tark_cohort.py",
    "tark_analytics.py", "tark_data.py", "build_site.py", "build_facts.py",
    "write_computed_cells.py", "run_supplement.py", "run_analytics.py",
    "run_benchmark.py", "coverage.py", "corrections_log.py", "promote.py",
    "resolve_citations.py", "tark_display.py", "seed_case_law_cell.py", "ingest.py",
    "calibrate_ingest.py", "verify_cell.py",
    "census/build_census.py", "census/enumerate.py", "census/classify.py",
]
# console-only scripts (validators, tests, fetchers, shots, produce) print to
# the developer, not to a surface, and stay out of scope
OWNED_DOCS = ["docs/DECISIONS_2026-09.md", "docs/BUILD_REPORT_6.md",
              "README.md", "docs/INVESTOR_DEMO.md",
              "docs/benchmark_methodology.md"]

BAD = re.compile("[—;]")
SLOT = "\x00"
TAG = re.compile(r"<[^>]*>")
TITLE = re.compile(r"""title=(?:"([^"]*)"|'([^']*)')""")
ENTITY = re.compile(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);")
CSS_DECL = re.compile(r"^\s*(?:[a-z-]+\s*:[^;]*;\s*)+$")
REGEX_FUNCS = {"compile", "match", "search", "finditer", "findall", "sub",
               "fullmatch", "split", "subn"}
REGEX_NAMES = re.compile(r"(?:_RE|_PAT|RE|PAT|PATTERN)$")


def copy_text(s: str) -> str | None:
    """The prose inside a literal, or None when the literal is not copy."""
    if CSS_DECL.match(s):
        return None
    titles = " ".join(a or b for a, b in TITLE.findall(s))
    body = ENTITY.sub(" ", TAG.sub(" ", s))
    # SLOT marks an interpolation: "{n} — {label}" is prose even though its
    # constant part has no letters. A lone glyph is not, even when its
    # tooltip attribute is an interpolation (title="${reason}").
    joiner = re.compile(re.escape(SLOT) + r"[^A-Za-z\x00]*[—;][^A-Za-z\x00]*"
                        + re.escape(SLOT))
    prose = (re.search(r"[A-Za-z]", body) or joiner.search(body)
             or re.search(r"[A-Za-z]", titles))
    if not prose:
        return None
    return (body + " " + titles).replace(SLOT, "x")


# ------------------------------------------------------------------ JS
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WORDS = {"return", "typeof", "case", "in", "of", "void", "delete"}


def _scan(src: str, i: int, line: int, out: list, in_expr: bool):
    """Recursive-descent scan of JS code from index i. Appends (line, text)
    for every string and template literal to out. Template ${...} bodies
    are code and are scanned recursively, so prose in a nested template or
    a ternary is seen too. When in_expr is true the scan returns at the
    brace that closes the enclosing ${ ... }. Returns (index, line)."""
    n = len(src)
    last_sig = ""
    last_word = ""
    depth = 0
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1; i += 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i); j = n if j < 0 else j + 2
            line += src.count("\n", i, j); i = j; continue
        if c == "/":
            is_regex = (last_sig == "" or last_sig in _REGEX_PREV
                        or last_word in _REGEX_WORDS)
            if is_regex:
                j = i + 1; in_class = False
                while j < n:
                    ch = src[j]
                    if ch == "\\": j += 2; continue
                    if in_class:
                        if ch == "]": in_class = False
                    elif ch == "[": in_class = True
                    elif ch == "/" or ch == "\n": break
                    j += 1
                j += 1
                while j < n and src[j].isalpha(): j += 1
                i = j; last_sig = "/"; last_word = ""; continue
            i += 1; last_sig = c; last_word = ""; continue
        if c in "\"'":
            j = i + 1; buf = []
            while j < n and src[j] != c:
                if src[j] == "\\":
                    buf.append(src[j + 1] if j + 1 < n else ""); j += 2; continue
                buf.append(src[j]); j += 1
            out.append((line, "".join(buf)))
            i = j + 1; last_sig = c; last_word = ""; continue
        if c == "`":
            j = i + 1; buf = []; start = line
            while j < n and src[j] != "`":
                if src.startswith("${", j):
                    j, line = _scan(src, j + 2, line, out, True)
                    j += 1                      # past the closing brace
                    buf.append(SLOT)
                    continue
                if src[j] == "\n": line += 1
                if src[j] == "\\":
                    buf.append(src[j + 1] if j + 1 < n else ""); j += 2; continue
                buf.append(src[j]); j += 1
            out.append((start, "".join(buf)))
            i = j + 1; last_sig = "`"; last_word = ""; continue
        if in_expr:
            if c == "{":
                depth += 1
            elif c == "}":
                if depth == 0:
                    return i, line
                depth -= 1
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"): j += 1
            last_word = src[i:j]; last_sig = src[j - 1]; i = j; continue
        if not c.isspace():
            last_sig = c; last_word = ""
        i += 1
    return i, line


def js_literals(src: str):
    """(line, text) for every string and template literal in JS source,
    comments and regex literals skipped, ${...} bodies scanned as code."""
    out: list = []
    _scan(src, 0, 1, out, False)
    return out


# -------------------------------------------------------------- Python
def py_literals(path: Path):
    """Yield (line, text) for string constants that are not docstrings and
    not regex patterns."""
    src = path.read_text()
    tree = ast.parse(src)
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                skip.add(id(b[0].value))
        if isinstance(node, ast.Call):
            f = node.func
            name = (f.attr if isinstance(f, ast.Attribute)
                    else f.id if isinstance(f, ast.Name) else "")
            mod = (f.value.id if isinstance(f, ast.Attribute)
                   and isinstance(f.value, ast.Name) else "")
            if name in REGEX_FUNCS and (mod == "re" or name == "compile"):
                for a in node.args[:1]:
                    for sub in ast.walk(a):
                        skip.add(id(sub))
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and REGEX_NAMES.search(t.id)
                   for t in node.targets):
                for sub in ast.walk(node.value):
                    skip.add(id(sub))
    in_fstring: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for sub in ast.walk(node):
                if sub is not node:
                    in_fstring.add(id(sub))
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and id(node) not in skip:
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                else:
                    parts.append(SLOT)
            yield node.lineno, "".join(parts)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip and id(node) not in in_fstring):
            yield node.lineno, node.value


# ---------------------------------------------------------------- docs
def doc_lines(path: Path):
    fence = False
    for i, l in enumerate(path.read_text().splitlines(), 1):
        if l.strip().startswith("```"):
            fence = not fence; continue
        if fence or l.lstrip().startswith(">"):
            continue
        yield i, l


def scan(path: Path):
    """Return [(line, text)] hits for one file."""
    rel = path.relative_to(BASE).as_posix()
    lines = path.read_text().splitlines()
    marked = {i for i, l in enumerate(lines, 1) if "copy-exempt" in l}
    hits = []
    if path.suffix == ".js":
        items = js_literals(path.read_text())
    elif path.suffix == ".py":
        items = py_literals(path)
    else:
        items = doc_lines(path)
    for ln, raw in items:
        if ln in marked:
            continue
        text = raw if path.suffix == ".md" else copy_text(raw)
        if text is None:
            continue
        if BAD.search(text):
            hits.append((ln, raw.strip().replace("\n", " ")[:100]))
    return rel, hits


def targets():
    files = sorted((BASE / "site" / "js").glob("*.js"))
    files += [BASE / "src" / m for m in SURFACE_MODULES]
    files += [BASE / "app.py"]
    files += [BASE / d for d in OWNED_DOCS]
    return [f for f in files if f.exists()]


def main(argv) -> int:
    only = None
    show = 3
    if "--only" in argv:
        only = Path(argv[argv.index("--only") + 1]).resolve()
    if "--show" in argv:
        show = int(argv[argv.index("--show") + 1])
    fails = 0
    for f in targets():
        if only and f != only:
            continue
        rel, hits = scan(f)
        if hits:
            fails += len(hits)
            print(f"[FAIL] {rel}: {len(hits)} literal(s) with an em dash or semicolon")
            for ln, t in hits[:show]:
                print(f"       :{ln}  {t!r}")
        else:
            print(f"[PASS] {rel}")
    print(f"\n{fails} copy violation(s)." if fails else
          "\nCopy gate holds: no em dash or semicolon in user-facing copy.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
