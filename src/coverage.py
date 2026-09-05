"""Tark evidence coverage report (per status kind, never one merged number).
Run: python src/coverage.py"""
from tark_data import COVERAGE_KINDS, coverage_summary, coverage_totals, product_keys

hdr = f"{'product':<18}" + "".join(f"{k:>11}" for k in COVERAGE_KINDS) + f"{'resolved':>18}"
print(hdr)
for prod in product_keys():
    c = coverage_summary(prod)
    print(f"{prod:<18}" + "".join(f"{c[k]:>11}" for k in COVERAGE_KINDS)
          + f"{str(c['resolved']) + ' of ' + str(c['resolvable']):>18}")
t = coverage_totals()
print(f"{'TOTAL':<18}" + "".join(f"{t['counts'][k]:>11}" for k in COVERAGE_KINDS)
      + f"{str(t['resolved']) + ' of ' + str(t['resolvable']):>18}")
print()
print(t["line"])
