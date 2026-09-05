# Advisor-stated inputs

One file per plan and product: `<plan_key>__<product_key>.json`.

```
{
  "plan": "plan_tech_media",
  "product": "cliffwater_cclfx",
  "not_evidence": "An advisor-stated cell is the adopting fiduciary's own input ...",
  "cells": {
    "6.6": {"value": "...", "signer": "name and role", "date": "2026-09-04",
            "status": "advisor-stated - name and role, 2026-09-04"}
  }
}
```

Only cells 6.6, 6.8, 3.7, 2.8, 3.5 and 4.9. Every entry needs a value, a
signer and an ISO date (`validate_data` refuses anything else). These are
inputs, not evidence: they never enter `data/evidence/`, the product
record's cell stays as it is, and the site's Evaluation view emits the
file content from its form because a static site writes nothing.
