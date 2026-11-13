"""Deterministic checks. No model is involved in this file.

1. Every extracted value is checked against the text of the lines it cites.
   A value that is not there is kept but marked "unsupported" and never
   counted in a chronology date, a total or a finding.
2. Bills are reconciled with records: duplicate documents, printed totals
   that do not match their lines, charges with no treatment note, visits with
   no charge, and gaps in treatment.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

CARE_GAP_DAYS = 30


def _human(iso: str) -> str:
    """2026-03-23 -> Mar 23, 2026"""
    d = date.fromisoformat(iso)
    return f"{calendar.month_abbr[d.month]} {d.day}, {d.year}"


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).lower()


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(s))


def _date_forms(iso: str) -> list[str]:
    y, m, d = (int(x) for x in iso.split("-"))
    date(y, m, d)  # raises on an impossible date
    mon, month = calendar.month_abbr[m].lower(), calendar.month_name[m].lower()
    forms = [
        f"{m:02d}/{d:02d}/{y}", f"{m}/{d}/{y}", f"{m:02d}/{d:02d}/{y % 100:02d}", f"{m}/{d}/{y % 100:02d}",
        f"{mon} {d}, {y}", f"{month} {d}, {y}", f"{mon} {d:02d}, {y}", f"{month} {d:02d}, {y}",
        f"{d} {month} {y}", f"{y}-{m:02d}-{d:02d}",
    ]
    return forms


def _bounded(needle: str, hay: str, edge: str = "0-9a-z") -> bool:
    return re.search(rf"(?<![{edge}])" + re.escape(needle) + rf"(?![{edge}])", hay) is not None


def _found(needle: str, text: str) -> bool:
    """Find a date or code in the text.

    First in the normal text with strict word edges. Then, because OCR often
    drops or adds spaces, in the text with every space removed, where only
    digits count as edges (so "2/3/2026" never matches inside "12/3/2026").
    """
    spaced = re.sub(r"\s+", " ", _norm(text))
    n = _norm(needle)
    if _bounded(n, spaced):
        return True
    return _bounded(n.replace(" ", ""), spaced.replace(" ", ""), edge="0-9")


def _check(kind: str, value: str, text: str) -> tuple[bool, str]:
    """Is `value` (of the given kind) stated in `text`? Returns (ok, reason)."""
    t = _norm(text)
    tight = t.replace(" ", "")
    if kind == "date":
        try:
            forms = _date_forms(value)
        except (ValueError, TypeError):
            return False, f"not a valid YYYY-MM-DD date: {value!r}"
        return (any(_found(f, text) for f in forms), "date not found in the cited lines")
    if kind == "money":
        try:
            want = Decimal(value.replace(",", "").replace("$", ""))
        except InvalidOperation:
            return False, f"not an amount: {value!r}"
        found = [Decimal(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.\d{2}", tight)]
        return (want in found, "amount not found in the cited lines")
    if kind == "code":
        return (_found(value.strip(), text), "code not found in the cited lines")
    if kind == "quote":
        a, b = _alnum(value), _alnum(text)
        return (bool(a) and a in b, "quote is not word for word in the cited lines")
    # "name": most words of the value must appear in the cited lines
    words = [w for w in re.findall(r"[a-z0-9]+", _norm(value)) if len(w) > 1]
    hay = _alnum(text)
    hits = sum(1 for w in words if w in hay)
    return (bool(words) and hits / len(words) >= 0.8, "name not found in the cited lines")


class Verifier:
    def __init__(self, lines: list[dict]):
        self.lines = {l["id"]: l for l in lines}

    def field(self, cited: dict, kind: str, doc: str, required: bool = True) -> dict:
        value, ids = cited["value"].strip(), list(dict.fromkeys(cited["line_ids"]))
        out = {"value": value, "line_ids": ids, "kind": kind}
        if not value:
            out.update(status="absent" if not required else "unsupported", reason="no value")
            return out
        bad = [i for i in ids if i not in self.lines or self.lines[i]["doc"] != doc]
        if not ids or bad:
            out.update(status="unsupported", reason=f"cites lines that are not in this document: {bad or 'none'}")
            return out
        text = " ".join(self.lines[i]["text"] for i in ids)
        ok, reason = _check(kind, value, text)
        sources = {self.lines[i]["source"] for i in ids}
        out["evidence"] = "text layer" if sources == {"text"} else "scan, re-read from a zoomed crop"
        out.update(status="verified" if ok else "unsupported", reason="" if ok else reason)
        return out


# ---------------------------------------------------------------------------


def _same_org(a: str, b: str) -> bool:
    stop = {"the", "of", "and", "inc", "llc", "pc", "associates", "center", "medical", "department"}
    wa = {w for w in re.findall(r"[a-z0-9]+", _norm(a)) if w not in stop}
    wb = {w for w in re.findall(r"[a-z0-9]+", _norm(b)) if w not in stop}
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.5


class Orgs:
    """Gives one canonical name to every spelling of the same provider."""

    def __init__(self):
        self.names: list[str] = []

    def canon(self, name: str) -> str:
        for n in self.names:
            if _same_org(n, name):
                return n
        self.names.append(name)
        return name


def build_case(extractions: dict[str, dict], lines: list[dict], duplicates: dict, titles: dict[str, str]) -> dict:
    v = Verifier(lines)
    orgs = Orgs()
    encounters, bills = [], []

    for doc, ex in sorted(extractions.items()):
        for e in ex["encounters"]:
            enc = {
                "doc": doc,
                "date": v.field(e["date"], "date", doc),
                "provider": v.field(e["provider"], "name", doc),
                "clinician": v.field(e["clinician"], "name", doc, required=False),
                "kind": e["kind"],
                "diagnoses": [{"code": v.field(c["code"], "code", doc), "description": c["description"]} for c in e["diagnoses"]],
                "procedures": [{"code": v.field(c["code"], "code", doc), "description": c["description"]} for c in e["procedures"]],
                "key_facts": [v.field(k, "quote", doc) for k in e["key_facts"]],
            }
            enc["verified"] = enc["date"]["status"] == "verified" and enc["provider"]["status"] == "verified"
            enc["org"] = orgs.canon(enc["provider"]["value"])
            encounters.append(enc)
        for b in ex["bills"]:
            bill = {
                "doc": doc,
                "provider": v.field(b["provider"], "name", doc),
                "account": v.field(b["account"], "code", doc, required=False),
                "printed_total": v.field(b["printed_total"], "money", doc, required=False),
                "lines": [],
            }
            bill["org"] = orgs.canon(bill["provider"]["value"])
            for bl in b["lines"]:
                line = {
                    "date": v.field(bl["date"], "date", doc),
                    "code": v.field(bl["code"], "code", doc),
                    "description": bl["description"],
                    "units": bl["units"],
                    "charge": v.field(bl["charge"], "money", doc),
                }
                line["verified"] = all(line[k]["status"] == "verified" for k in ("date", "code", "charge"))
                bill["lines"].append(line)
            bills.append(bill)

    encounters.sort(key=lambda e: (e["date"]["value"], e["org"]))
    findings = []

    # Duplicate documents (found before extraction; their contents are never counted).
    for dup, info in sorted(duplicates.items()):
        findings.append({
            "type": "duplicate_document", "severity": "info",
            "title": "Duplicate document left out of the totals",
            "detail": f"{titles.get(dup, dup)} is a copy of {titles.get(info['of'], info['of'])} "
                      + ("(identical letter for letter, after OCR). " if info["similarity"] >= 0.9999
                         else f"({info['similarity']:.2%} identical letter for letter, after OCR). ")
                      + "Counting both would overstate the bills.",
            "doc": dup, "of": info["of"],
            "line_ids": [l["id"] for l in lines if l["doc"] == dup and re.search(r"\d\.\d\d", l["text"])],
        })

    # Printed totals versus the sum of the lines.
    for b in bills:
        pt = b["printed_total"]
        if pt["status"] != "verified" or not all(l["verified"] for l in b["lines"]):
            continue
        computed = sum(Decimal(l["charge"]["value"]) for l in b["lines"])
        printed = Decimal(pt["value"])
        if computed != printed:
            findings.append({
                "type": "total_mismatch", "severity": "warning",
                "title": "Bill total does not match its line items",
                "detail": f"{b['org']} prints a total of ${printed:,.2f}, but its {len(b['lines'])} charges add up to "
                          f"${computed:,.2f} (a difference of ${printed - computed:,.2f}). Exhibit uses the line items.",
                "doc": b["doc"], "printed": float(printed), "computed": float(computed),
                "line_ids": pt["line_ids"] + [i for l in b["lines"] for i in l["charge"]["line_ids"]],
            })

    seen_visits = {(e["org"], e["date"]["value"]) for e in encounters if e["verified"]}
    billed_orgs = {b["org"] for b in bills}

    # Charges with no treatment note on that date.
    for b in bills:
        flagged = set()
        for l in b["lines"]:
            key = (b["org"], l["date"]["value"])
            if l["date"]["status"] != "verified" or key in seen_visits or key in flagged:
                continue
            flagged.add(key)
            same_day = [x for x in b["lines"] if x["date"]["value"] == l["date"]["value"]]
            amount = sum(Decimal(x["charge"]["value"]) for x in same_day if x["charge"]["status"] == "verified")
            findings.append({
                "type": "billed_not_documented", "severity": "warning",
                "title": "Charge with no treatment note",
                "detail": f"{b['org']} bills ${amount:,.2f} for {_human(l['date']['value'])}, but no record in the file "
                          f"documents a visit that day. Request the note, or expect the charge to be challenged.",
                "doc": b["doc"], "provider": b["org"], "date": l["date"]["value"],
                "line_ids": [i for x in same_day for i in x["date"]["line_ids"] + x["charge"]["line_ids"]],
            })

    # Visits with no charge (only for providers whose bills we have).
    billed_visits = {(b["org"], l["date"]["value"]) for b in bills for l in b["lines"] if l["date"]["status"] == "verified"}
    for e in encounters:
        key = (e["org"], e["date"]["value"])
        if e["verified"] and e["org"] in billed_orgs and key not in billed_visits:
            findings.append({
                "type": "documented_not_billed", "severity": "info",
                "title": "Visit with no charge",
                "detail": f"{e['org']} documents a visit on {_human(e['date']['value'])} that is not on its bill. "
                          f"The bill may be incomplete.",
                "doc": e["doc"], "provider": e["org"], "date": e["date"]["value"],
                "line_ids": e["date"]["line_ids"],
            })
    for org in sorted({e["org"] for e in encounters if e["verified"]} - billed_orgs):
        findings.append({
            "type": "missing_bill", "severity": "warning",
            "title": "No bill from a treating provider",
            "detail": f"The file has records from {org} but no bill. Request an itemized statement.",
            "provider": org, "line_ids": [],
        })

    # Gaps in treatment.
    dated = sorted({e["date"]["value"]: e for e in encounters if e["verified"]}.items())
    for (d1, e1), (d2, e2) in zip(dated, dated[1:]):
        days = (date.fromisoformat(d2) - date.fromisoformat(d1)).days
        if days > CARE_GAP_DAYS:
            findings.append({
                "type": "care_gap", "severity": "warning",
                "title": f"{days}-day gap in treatment",
                "detail": f"No documented care between {_human(d1)} ({e1['org']}) and {_human(d2)} ({e2['org']}). "
                          f"Insurers use gaps over {CARE_GAP_DAYS} days to argue the injury had resolved; "
                          f"the reason for the gap should be documented.",
                "from": d1, "to": d2, "days": days,
                "line_ids": e1["date"]["line_ids"] + e2["date"]["line_ids"],
            })

    # Totals use verified charge lines only.
    by_org: dict[str, Decimal] = {}
    for b in bills:
        for l in b["lines"]:
            if l["verified"]:
                by_org[b["org"]] = by_org.get(b["org"], Decimal(0)) + Decimal(l["charge"]["value"])
    total = sum(by_org.values(), Decimal(0))

    facts = _all_fields(encounters, bills)
    return {
        "encounters": encounters,
        "bills": bills,
        "findings": findings,
        "billed_by_provider": {k: float(v_) for k, v_ in sorted(by_org.items())},
        "total_billed": float(total),
        "fact_counts": {
            "total": len(facts),
            "verified": sum(f["status"] == "verified" for f in facts),
            "unsupported": sum(f["status"] == "unsupported" for f in facts),
            "from_scans": sum(f["status"] == "verified" and f.get("evidence", "").startswith("scan") for f in facts),
        },
        "unsupported": [f for f in facts if f["status"] == "unsupported"],
    }


def _all_fields(encounters, bills):
    out = []
    for e in encounters:
        out += [e["date"], e["provider"], e["clinician"]]
        out += [c["code"] for c in e["diagnoses"] + e["procedures"]] + e["key_facts"]
    for b in bills:
        out += [b["provider"], b["account"], b["printed_total"]]
        for l in b["lines"]:
            out += [l["date"], l["code"], l["charge"]]
    return [f for f in out if f["status"] != "absent"]
