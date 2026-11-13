# Exhibit

Every fact points to its page.

Exhibit turns a personal-injury record set (medical records and itemized bills, digital or scanned) into a
medical chronology and a bill summary in which every date, code, amount and quoted fact links to the exact line
of the page it came from, and is proven there by code before it is shown or counted.

This repository runs it on a **fictional** sample file built to contain the problems real record sets contain:
a faxed duplicate bill, a bill whose printed total is $100 more than its charges, a therapy visit billed with no
treatment note, a 33-day gap in treatment, and scanned pages whose table of visit dates plain OCR misreads.
Because the file is synthetic, the right answer is known exactly and every run is scored against it.

## Run it

```
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python anthropic google-genai pydantic pymupdf rapidocr-onnxruntime pillow
EXHIBIT_PROVIDER=anthropic ANTHROPIC_API_KEY=... .venv/bin/python run.py   # Claude Opus 5.5
EXHIBIT_PROVIDER=gemini    GEMINI_API_KEY=...    .venv/bin/python run.py   # Gemini 3.5 Flash
.venv/bin/python tests/test_verify.py                                    # plants 8 kinds of mistakes; all must be caught
cd site && python3 -m http.server 8766                                   # open http://127.0.0.1:8766
```

Model calls are cached in `work/`, so a second run is free. A hard cap (`EXHIBIT_BUDGET_USD`, default $2)
stops all model calls once the recorded spend reaches it.

## How it works

| Step | File | What it does |
|---|---|---|
| 1 | `exhibit/generate.py`, `sample_case.py` | Writes the fictional record set and its answer key; scans are tilted, blurred and speckled image-only pages |
| 2 | `exhibit/ingest.py` | Reads every page into lines with ids (`D06.p2.l7`) and page positions; OCR (RapidOCR) for scans |
| 3 | `exhibit/vision.py` | Re-reads every OCR line from a 300 dpi full-width crop; keeps both readings |
| 4 | `exhibit/ingest.py` | Finds duplicate documents letter for letter before anything is extracted |
| 5 | `exhibit/extract.py` | Structured extraction: every value comes back with the line ids it was read from |
| 6 | `exhibit/verify.py` | No model: proves each value is in its cited lines (dates in any format, amounts to the cent, codes exactly, quotes word for word); reconciles bills with records |
| 7 | `exhibit/evaluate.py` | Precision and recall against the answer key, wrong-but-proven facts, cost and time |
| 8 | `exhibit/site.py`, `viewer/` | Static viewer: click any fact to see its line highlighted on the page |

## Results on the sample file (13 pages)

Live viewer: https://exhibit.ameyan.in

| Model (effort low) | Dates | Bill lines | Dx codes | Planted problems | Wrong but proven | Cost | Model time |
|---|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 11/11 | 22/22 | 9/9 | 4/4 | 0 | $0.35 | 81 s |
| Gemini 3.5 Flash | 11/11 | 22/22 | 9/9 | 4/4 | 0 | $0.17 at list price (free tier) | 573 s (free tier, retries) |

The file is small and written by the same person who built the checks, so these numbers show the checks work,
not how the system would score on a thousand real files.
