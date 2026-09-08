"""
Plan intake: an advisor's own plan enters the record, anonymized
    python src/plan_intake.py <intake.json>            # a form export or a hand-written file
    python src/plan_intake.py <intake.json> --dry-run  # validate and print, write nothing

The intake file carries the plan's own figures (Form 5500 and Schedule H
primitives) and an anonymized display label. Rules:
  - `anonymization_label` is required and must equal `display_label`, and
    the label may not look like a sponsor name (Inc, LLC, Corp, an EIN).
    No identity block is stored for an intake plan.
  - derived figures are recomputed from the primitives here, never taken
    from the form
  - Schedule H lines the form leaves empty are stored as null with the
    reason, never as zero
  - the file is validated with the same validate_plan every reference plan
    passes, then written to data/plans/<plan_key>.json
After that: python src/produce.py && python src/build_site.py (the plan
gets its liquidity matches and memos for every product on the next build).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from tark_anon import leaks
from tark_data import DATA, load_plan, validate_plan

# a corporate suffix or an EIN. "company" and "co" are not here: a plan
# description says "consulting company" and a Colorado plan says "CO". The
# reference sponsors' own tokens are screened by tark_anon, the same list
# the build refuses to emit (audit item 39).
SPONSOR_HINT = re.compile(r"\b(inc|llc|l\.l\.c|corp|corporation|ltd|limited|lp|l\.p|plc|holdings)\b\.?"
                          r"|\b\d{2}-\d{7}\b", re.I)
ANON_RULE = ("Sponsor name never appears on demo surfaces. The plan entered the record through "
             "plan intake under an anonymized label and no identity block is stored.")
NUMERIC = ("net_assets_eoy", "net_assets_boy", "tot_admin_expenses", "with_account_balances",
           "active_eoy", "separated_deferred_vested", "retired_receiving")


class Refused(SystemExit):
    """Exit 1 on the command line, the sentence readable by a caller (the
    workspace API answers with it)."""

    def __init__(self, message: str):
        super().__init__(1)
        self.message = message


def refuse(msg: str) -> None:
    print(f"refused: {msg}")
    raise Refused(msg)


def plan_key_from(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40]
    return "plan_" + (slug or "intake")


def derive(fin: dict, part: dict) -> dict:
    net, boy = fin["net_assets_eoy"], fin.get("net_assets_boy")
    bal, adm = part["with_account_balances"], fin.get("tot_admin_expenses")
    out = {"avg_balance_per_account": round(net / bal),
           "admin_expense_ratio_pct": round(adm / net * 100, 3) if adm else None}
    if boy:
        out["yoy_net_asset_growth_pct"] = round((net / boy - 1) * 100, 1)
    return out


def scaffold(form: dict) -> dict:
    """The plan file from an intake form. Refuses what the record cannot hold."""
    label = str(form.get("display_label") or "").strip()
    if not label:
        refuse("display_label is required (an anonymized description of the plan)")
    if str(form.get("anonymization_label") or "").strip() != label:
        refuse("anonymization_label is required and must equal display_label: the person entering the "
               "plan confirms the label names no sponsor")
    if SPONSOR_HINT.search(label):
        refuse(f"display_label {label!r} looks like a sponsor name or an EIN, describe the plan instead "
               "(industry, size, state)")
    if leaks(label):
        refuse("display_label carries a token from a reference plan's sponsor identity, the build would "
               "refuse to publish it, describe the plan instead (industry, size, state)")
    for f in NUMERIC:
        v = form.get(f)
        if f in ("net_assets_boy", "tot_admin_expenses", "retired_receiving") and v in (None, ""):
            continue
        if not isinstance(v, (int, float)) or v < 0:
            refuse(f"{f} must be a non-negative number")
    if form["with_account_balances"] <= 0 or form["net_assets_eoy"] <= 0:
        refuse("net_assets_eoy and with_account_balances must be positive")
    codes = str(form.get("pension_benefit_codes") or "").upper().replace(" ", "")
    if not codes:
        refuse("pension_benefit_codes (Form 5500 line 8a, e.g. 2E2G2J2K) are required, the liquidity "
               "engine reads 2G and 2H for plan direction")
    key = str(form.get("plan_key") or plan_key_from(label))
    if not re.fullmatch(r"plan_[a-z0-9_]{2,40}", key):
        refuse(f"plan_key {key!r} must match plan_[a-z0-9_]")
    fin = {k: float(form[k]) for k in ("net_assets_eoy",) }
    for k in ("net_assets_boy", "tot_admin_expenses", "tot_expenses"):
        if form.get(k) not in (None, ""):
            fin[k] = float(form[k])
    part = {k: float(form[k]) for k in ("with_account_balances", "active_eoy", "separated_deferred_vested")}
    part["retired_receiving"] = float(form.get("retired_receiving") or 0)
    if part["separated_deferred_vested"] > part["with_account_balances"]:
        refuse("separated participants with balances cannot exceed accounts with balances")

    def sh(field: str, source: str) -> dict:
        v = form.get(field)
        if v in (None, ""):
            return {"value": None, "reason": "not provided at intake, fill from Schedule H citing the line",
                    "source": source}
        return {"value": v, "source": str(form.get(field + "_source") or source)}

    ref = load_plan("plan_tech_media")
    plan_year = str(form.get("plan_year") or "")
    # provenance a reader can meet (R3-P2-10): the publisher, the date the
    # figures were entered (the form's date, else today: an intake is an
    # action on a day, not a build output) and one note with no path in it
    pulled = str(form.get("pulled") or date.today().isoformat())
    source = {"publisher": str(form.get("publisher") or "advisor intake (Form 5500 and Schedule H of the plan)"),
              "pulled": pulled,
              "note": f"plan intake, {pulled}, figures as the advisor supplied them"}
    # the filed outflow proxy (R2-P1-10) is the scenario layer's base demand:
    # computed here only from the three totals the advisor supplied, else
    # null with the reason, never a default
    totals = ("tot_expenses", "tot_admin_expenses", "net_assets_boy")
    if all(k in fin for k in totals) and fin["net_assets_boy"]:
        proxy = {
            "value": round((fin["tot_expenses"] - fin["tot_admin_expenses"]) / fin["net_assets_boy"] * 100, 2),
            "unit": "percent of beginning-of-year net assets, per plan year",
            "formula": "(total expenses minus total administrative expenses) / net assets at the "
                       "beginning of the plan year * 100",
            "inputs": {"tot_expenses": {"value": fin["tot_expenses"], "meaning": "total expenses, Schedule H"},
                       "tot_admin_expenses": {"value": fin["tot_admin_expenses"],
                                              "meaning": "total administrative expenses, Schedule H"},
                       "net_assets_boy": {"value": fin["net_assets_boy"],
                                          "meaning": "net assets at the beginning of the plan year, Schedule H"}},
            "plan_year": plan_year,
            "source": dict(source),
            "what": "a proxy for the plan's filed outflow rate while Schedule H line 2e is not in the record, "
                    "total expenses less administrative expenses over beginning net assets",
        }
    else:
        proxy = {"value": None,
                 "reason": "not computable at intake: total expenses, total administrative expenses and "
                           "beginning net assets are all needed, fill them from Schedule H",
                 "formula": "(total expenses minus total administrative expenses) / net assets at the "
                            "beginning of the plan year * 100"}
    return {
        "plan_key": key,
        "display_label": label,
        "anonymization_label": label,
        "archetype": str(form.get("archetype") or ""),
        "anonymization_rule": ANON_RULE,
        "plan_year": plan_year,
        "source": source,
        "plan_characteristics": {"pension_benefit_codes": codes,
                                 "codes_decoded": str(form.get("codes_decoded") or codes),
                                 "note": str(form.get("characteristics_note") or "")},
        "participants": part,
        "financials": fin,
        "schedule_h": {
            "benefit_payments_2e": sh("benefit_payments_2e", "Schedule H line 2e (benefit payments and payments to provide benefits)"),
            "participant_contributions_2a1b": sh("participant_contributions_2a1b", "Schedule H line 2a(1)(B) (participant contributions)"),
            "qdia_indicator": sh("qdia_indicator", "plan document or 404a-5 participant fee disclosure"),
            "filed_outflow_proxy": proxy,
        },
        "derived": derive(fin, part),
        "dictionary_cells": ref.get("dictionary_cells", {}),
    }


def intake(form: dict, dry_run: bool = False) -> Path:
    plan = scaffold(form)
    out = DATA / "plans" / f"{plan['plan_key']}.json"
    if out.exists():
        refuse(f"{out.relative_to(DATA.parent)} already exists, choose another plan_key")
    if dry_run:
        print(json.dumps(plan, indent=2))
        return out
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    errs = validate_plan(plan["plan_key"])
    if errs:
        out.unlink()
        refuse("the scaffold did not validate, nothing kept: " + " | ".join(errs))
    print(f"wrote {out.relative_to(DATA.parent)}. Next: python src/produce.py && python src/build_site.py")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("intake_json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    intake(json.loads(Path(a.intake_json).read_text()), a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
