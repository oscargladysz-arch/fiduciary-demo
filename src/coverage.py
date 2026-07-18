"""Tark - evidence coverage report. Run: python src/coverage.py"""
from tark_data import product_keys, load_evidence, status_kind

print(f"{'product':<18} {'seeded':>7} {'partial':>8} {'pending':>8} {'n/a':>5} {'coverage':>9}")
tot_s = tot_p = tot_pend = 0
for prod in product_keys():
    s = p = pend = na = 0
    for row in load_evidence(prod):
        k = status_kind(row["status"])
        if k in ("extracted", "verified"): s += 1
        elif k in ("partial", "fetched"): p += 1
        elif k == "n/a": na += 1
        else: pend += 1
    applicable = s + p + pend
    cov = (s + p) / applicable * 100 if applicable else 0
    print(f"{prod:<18} {s:>7} {p:>8} {pend:>8} {na:>5} {cov:>8.0f}%")
    tot_s += s; tot_p += p; tot_pend += pend
tot_app = tot_s + tot_p + tot_pend
print(f"{'TOTAL':<18} {tot_s:>7} {tot_p:>8} {tot_pend:>8} {'':>5} {(tot_s+tot_p)/tot_app*100:>8.0f}%")
