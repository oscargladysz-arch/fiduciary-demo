# Deploy log

Every deploy of the static frontend to the `gh-pages` branch is recorded
here from the hook run that authorized it, and the entry is committed with
the deploy. A deploy without an entry is a rule violation (round-2 brief,
rule 10). One entry per deploy, newest last.

Each entry carries: the source commit, the machine, the hook run (gate list
in order, exit code, PASS-line count, wall time, timestamp), the build
outputs, the deploy target and its resulting commit, the Tier 1 drawer check
and the EDGAR URL check, and anything that could not be checked from the
machine that deployed.

Pre-deploy steps, in order:
1. `sh hooks/pre-commit` on the exact commit to deploy, output kept.
2. `python src/build_site.py` on that commit.
3. `python src/check_edgar_urls.py` on a machine that reaches sec.gov
   (needs `TARK_SEC_CONTACT`). Every Tier 1 URL must answer 200.
4. Deploy per `docs/INVESTOR_DEMO.md`, then write the entry below.
