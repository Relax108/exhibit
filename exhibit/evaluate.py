"""Score a run against the sample case's ground truth.

The sample case is synthetic, so the right answer is known exactly. The most
important number is the last one: facts marked verified that are wrong. That
is the failure a law firm cannot afford, so it must be zero.
"""

from __future__ import annotations

from collections import Counter

from . import sample_case as gold
from .verify import _same_org


def _gold_org(name: str) -> str | None:
    for g in (gold.ER, gold.IMAGING, gold.ORTHO, gold.PT):
        if _same_org(g, name):
            return g
    return None


def _pr(found: int, extracted: int, expected: int) -> dict:
    return {
        "precision": round(found / extracted, 3) if extracted else 0.0,
        "recall": round(found / expected, 3) if expected else 0.0,
        "matched": found, "extracted": extracted, "expected": expected,
    }


def evaluate(case: dict, calls: list[dict], pages: int) -> dict:
    # Treatment encounters, matched on date and provider.
    want = Counter((g["date"], g["provider"]) for g in gold.GOLD_ENCOUNTERS)
    got = Counter((e["date"]["value"], _gold_org(e["provider"]["value"])) for e in case["encounters"] if e["verified"])
    enc = _pr(sum((want & got).values()), sum(got.values()), sum(want.values()))

    # Diagnosis codes on matched encounters.
    gold_dx = {(g["date"], g["provider"]): set(g["dx"]) for g in gold.GOLD_ENCOUNTERS}
    dx_found = dx_extracted = 0
    for e in case["encounters"]:
        key = (e["date"]["value"], _gold_org(e["provider"]["value"]))
        codes = {c["code"]["value"].upper() for c in e["diagnoses"] if c["code"]["status"] == "verified"}
        dx_extracted += len(codes)
        dx_found += len(codes & gold_dx.get(key, set()))
    dx = _pr(dx_found, dx_extracted, sum(len(g["dx"]) for g in gold.GOLD_ENCOUNTERS))

    # Bill lines, matched on provider, date, code and amount.
    want_b = Counter((g["provider"], g["date"], g["code"], g["amount"]) for g in gold.GOLD_BILL_LINES)
    got_b = Counter()
    for b in case["bills"]:
        for l in b["lines"]:
            if l["verified"]:
                got_b[(_gold_org(b["org"]), l["date"]["value"], l["code"]["value"], float(l["charge"]["value"]))] += 1
    bl = _pr(sum((want_b & got_b).values()), sum(got_b.values()), sum(want_b.values()))

    # Findings.
    def hit(g):
        for f in case["findings"]:
            if f["type"] != g["type"]:
                continue
            if g["type"] == "duplicate_document" and f.get("doc") == g["doc"] and f.get("of") == g["of"]:
                return True
            if g["type"] == "total_mismatch" and f.get("doc") == g["doc"] and abs(f["computed"] - g["computed"]) < 0.005:
                return True
            if g["type"] == "billed_not_documented" and f.get("date") == g["date"] and _gold_org(f["provider"]) == g["provider"]:
                return True
            if g["type"] == "care_gap" and f.get("from") == g["from"] and f.get("to") == g["to"]:
                return True
        return False

    found_findings = [g for g in gold.GOLD_FINDINGS if hit(g)]
    false_findings = [
        f for f in case["findings"]
        if not any(f["type"] == g["type"] and hit(g) for g in gold.GOLD_FINDINGS)
    ]

    verified_but_wrong = (enc["extracted"] - enc["matched"]) + (bl["extracted"] - bl["matched"]) + (dx["extracted"] - dx["matched"])

    fresh = [c for c in calls]
    return {
        "encounters": enc,
        "diagnosis_codes": dx,
        "bill_lines": bl,
        "total_billed": {"exhibit": case["total_billed"], "expected": gold.GOLD_TOTAL_BILLED,
                         "exact": abs(case["total_billed"] - gold.GOLD_TOTAL_BILLED) < 0.005},
        "findings": {"expected": len(gold.GOLD_FINDINGS), "found": len(found_findings),
                     "false_alarms": [f["title"] for f in false_findings]},
        "facts": case["fact_counts"],
        "verified_but_wrong": verified_but_wrong,
        "cost": {
            "calls": len(fresh),
            "usd": round(sum(c["cost_usd"] for c in fresh), 4),
            "usd_per_page": round(sum(c["cost_usd"] for c in fresh) / pages, 4) if pages else 0,
            "model_seconds": round(sum(c["seconds"] for c in fresh), 1),
            "input_tokens": sum(c["input_tokens"] for c in fresh),
            "output_tokens": sum(c["output_tokens"] for c in fresh),
            "model": fresh[0]["model"] if fresh else "",
            "effort": fresh[0]["effort"] if fresh else "",
        },
        "pages": pages,
    }
