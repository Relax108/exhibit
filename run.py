"""Run the whole Exhibit pipeline on the sample case.

    EXHIBIT_PROVIDER=anthropic ANTHROPIC_API_KEY=... .venv/bin/python run.py
    EXHIBIT_PROVIDER=gemini    GEMINI_API_KEY=...    .venv/bin/python run.py

Steps: make the sample PDFs, read every page into positioned lines (OCR for
scans), re-read scanned lines from zoomed crops, find duplicate documents,
extract cited facts per document, verify every fact in code, reconcile bills
with records, score against the ground truth, and build the viewer in site/.
Model calls are cached in work/, so a second run is free and identical.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from exhibit import sample_case
from exhibit.evaluate import evaluate
from exhibit.extract import extract_document
from exhibit.generate import generate
from exhibit.ingest import find_duplicates, ingest
from exhibit.llm import LLM, PROVIDER
from exhibit.site import build_site
from exhibit.verify import build_case
from exhibit.vision import reread_scanned_lines

ROOT = Path(__file__).parent
DOCS = ROOT / "case" / "documents"
WORK = ROOT / "work"


def step(name: str):
    print(f"- {name}", flush=True)
    return time.monotonic()


def main() -> int:
    WORK.mkdir(exist_ok=True)
    llm = LLM(WORK)
    t0 = time.monotonic()

    step("making the sample record set")
    manifest = generate(DOCS)
    titles = {d["id"]: d["title"] for d in manifest}

    step("reading pages (text layer, OCR for scans)")
    read = ingest(manifest, DOCS)
    lines = read["lines"]

    step("re-reading scanned lines from zoomed crops")
    reread = reread_scanned_lines(lines, {d["id"]: DOCS / d["file"] for d in manifest}, llm)

    step("finding duplicate documents")
    duplicates = find_duplicates(lines)

    step("extracting cited facts")
    extractions = {}
    for d in manifest:
        if d["id"] in duplicates:
            continue
        doc_lines = [l for l in lines if l["doc"] == d["id"]]
        extractions[d["id"]] = extract_document(d["id"], d["file"], doc_lines, llm).model_dump()

    step("verifying every fact and reconciling bills with records")
    case = build_case(extractions, lines, duplicates, titles)

    step("scoring against the ground truth")
    report = evaluate(case, llm.calls, len(read["pages"]))
    report["ocr"] = {**reread, "ocr_pages": sum(p["source"] == "ocr" for p in read["pages"])}
    report["wall_seconds"] = round(time.monotonic() - t0, 1)

    out = {
        "case_name": "Vega - sample personal-injury file (fictional)",
        "documents": manifest,
        "pages": read["pages"],
        "lines": lines,
        "duplicates": duplicates,
        "extractions": extractions,
        "case": case,
        "quality": report,
    }
    (WORK / f"result-{PROVIDER}.json").write_text(json.dumps(out, indent=1))
    (WORK / "result.json").write_text(json.dumps(out, indent=1))

    step("building the viewer")
    # The viewer shows Claude's run when there is one; every model's scores go in a comparison table.
    runs = {p.stem.removeprefix("result-"): json.loads(p.read_text()) for p in sorted(WORK.glob("result-*.json"))}
    shown = runs.get("anthropic", out)
    shown["comparison"] = {name: r["quality"] for name, r in runs.items()}
    build_site(shown, DOCS, ROOT / "viewer", ROOT / "site")

    q = report
    print()
    print(f"encounters  precision {q['encounters']['precision']:.0%} recall {q['encounters']['recall']:.0%}")
    print(f"bill lines  precision {q['bill_lines']['precision']:.0%} recall {q['bill_lines']['recall']:.0%}")
    print(f"dx codes    precision {q['diagnosis_codes']['precision']:.0%} recall {q['diagnosis_codes']['recall']:.0%}")
    print(f"total billed {q['total_billed']['exhibit']:,.2f} (expected {q['total_billed']['expected']:,.2f})")
    print(f"findings    {q['findings']['found']}/{q['findings']['expected']} found, false alarms: {q['findings']['false_alarms']}")
    print(f"facts       {q['facts']}")
    print(f"verified but wrong: {q['verified_but_wrong']}")
    print(f"cost        {q['cost']}")
    return 0 if q["verified_but_wrong"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
