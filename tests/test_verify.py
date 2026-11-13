"""Fault injection for the verifier: plant the mistakes a model makes and prove each is caught.

Run after one pipeline run (it reads work/result.json):
    .venv/bin/python tests/test_verify.py

Harm guarded against: a wrong date, amount, code or quote being shown as
proven, or counted in a total or a finding. No model is called.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exhibit.verify import build_case  # noqa: E402

R = json.loads((Path(__file__).resolve().parents[1] / "work" / "result.json").read_text())
TITLES = {d["id"]: d["title"] for d in R["documents"]}
LINES = R["lines"]


def run(ex):
    return build_case(ex, LINES, R["duplicates"], TITLES)


def first_encounter(ex, doc):
    return ex[doc]["encounters"][0]


def first_bill_line(ex, doc):
    return ex[doc]["bills"][0]["lines"][0]


baseline = run(R["extractions"])
assert baseline["fact_counts"]["unsupported"] == 0, "baseline must be clean before planting faults"
BASE_TOTAL = baseline["total_billed"]
failures = []


def expect(name, ex, check):
    case = run(ex)
    ok, why = check(case)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        failures.append(name)


def unsupported_values(case):
    return {(u["kind"], u["value"]) for u in case["unsupported"]}


# 1. A date one day off, citing the right line.
ex = copy.deepcopy(R["extractions"])
first_encounter(ex, "D01")["date"]["value"] = "2026-02-04"
expect("date one day off", ex, lambda c: (
    ("date", "2026-02-04") in unsupported_values(c)
    and not any(e["verified"] and e["date"]["value"] == "2026-02-04" for e in c["encounters"]),
    "wrong date was accepted"))

# 2. Transposed digits in a charge.
ex = copy.deepcopy(R["extractions"])
bl = first_bill_line(ex, "D07")
orig = bl["charge"]["value"]
bl["charge"]["value"] = "452.00" if orig == "425.00" else "999.99"
expect("charge with transposed digits", ex, lambda c: (
    ("money", bl["charge"]["value"]) in unsupported_values(c)
    and abs(c["total_billed"] - (BASE_TOTAL - float(orig))) < 0.005,
    f"total {c['total_billed']} should drop the unproven line"))

# 3. A diagnosis code one digit off.
ex = copy.deepcopy(R["extractions"])
enc = next(e for e in ex["D06"]["encounters"] if e["diagnoses"])
enc["diagnoses"][0]["code"]["value"] = "M50.221"
expect("diagnosis code one digit off", ex, lambda c: (("code", "M50.221") in unsupported_values(c), "wrong code accepted"))

# 4. A correct-looking value cited to a line in another document.
ex = copy.deepcopy(R["extractions"])
other = next(l["id"] for l in LINES if l["doc"] == "D02" and "02/03/2026" in l["text"])
first_encounter(ex, "D04")["date"] = {"value": "2026-02-03", "line_ids": [other]}
expect("citation to another document", ex, lambda c: (
    any(u["value"] == "2026-02-03" and other in u["line_ids"] for u in c["unsupported"]),
    "cross-document citation accepted"))

# 5. A citation to a line that does not exist.
ex = copy.deepcopy(R["extractions"])
first_bill_line(ex, "D05")["code"]["line_ids"] = ["D05.p1.l99"]
expect("citation to a missing line", ex, lambda c: (
    any("D05.p1.l99" in u["line_ids"] for u in c["unsupported"]), "missing line accepted"))

# 6. A quote with one word changed.
ex = copy.deepcopy(R["extractions"])
kf = next(k for e in ex["D01"]["encounters"] for k in e["key_facts"] if k["value"])
kf["value"] = kf["value"].replace("7/10", "9/10") if "7/10" in kf["value"] else kf["value"] + " severe"
expect("altered quote", ex, lambda c: (("quote", kf["value"]) in unsupported_values(c), "altered quote accepted"))

# 7. The right value pinned to the wrong line of the same document.
ex = copy.deepcopy(R["extractions"])
header = next(l["id"] for l in LINES if l["doc"] == "D07" and l["text"].startswith("ITEMIZED"))
first_bill_line(ex, "D07")["charge"]["line_ids"] = [header]
expect("right value, wrong line", ex, lambda c: (
    any(header in u["line_ids"] for u in c["unsupported"]), "value accepted from a line that does not contain it"))

# 8. A visit invented from nothing: must not appear as proven, close a gap, or hide a finding.
ex = copy.deepcopy(R["extractions"])
fake = copy.deepcopy(first_encounter(ex, "D06"))
fake["date"]["value"] = "2026-04-05"  # would split the 33-day gap if it were believed
ex["D06"]["encounters"].append(fake)
expect("invented visit", ex, lambda c: (
    any(f["type"] == "care_gap" and f["days"] == 33 for f in c["findings"])
    and not any(e["verified"] and e["date"]["value"] == "2026-04-05" for e in c["encounters"]),
    "an invented visit was believed"))

print()
print("all faults caught" if not failures else f"{len(failures)} fault(s) slipped through: {failures}")
sys.exit(1 if failures else 0)
