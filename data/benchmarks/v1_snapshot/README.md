# Benchmark engine v1: frozen snapshot

These are the sixteen selection artifacts and the profile inputs exactly as
the v1 engine (`src/tark_benchmark.py` at commit 292eca9, the P0 exit on
2026-09-04) produced them, after the P0 copy sweep and before any P1
engine change. They are read-only history: the before side of every
v1 to v2 comparison in `docs/benchmark_methodology.md` and
`docs/BUILD_REPORT_6.md`, and the source of the corrections log entries
that P1 writes.

No producer writes here and no surface reads from here. `MANIFEST.sha256`
pins every file and `src/test_benchmark.py` fails the commit if any byte
changes. The known defects these files carry are the ones the 2026-09-03
audit lists: index windows anchored before the proxy series begins, a
10-point ceiling on a 12-point scale, Lane A placeholders, Lane C entries
that never scored, and lane D pseudo-candidates. Do not cite a number from
this directory on any surface.
