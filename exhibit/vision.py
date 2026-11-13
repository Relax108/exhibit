"""Second reading of scanned lines: a zoomed crop of each OCR line, read by Claude.

OCR keeps what it is good at (where each line sits on the page). Its text is
often wrong on scanned tables, and its own confidence score does not reliably
say when, so every OCR line is re-read from a 300 dpi crop. Both readings are
kept. The line's text becomes the vision reading; the OCR text and the
agreement between the two stay on the line, and the viewer labels any fact
that rests on such a line as read from a scan.
"""

from __future__ import annotations

import base64
import re
from difflib import SequenceMatcher
from pathlib import Path

import pymupdf
from pydantic import BaseModel, Field

from .llm import LLM

CROP_DPI = 300
BATCH = 24


class Reading(BaseModel):
    line_id: str
    text: str = Field(description="Exactly what is printed in the crop, with normal spacing. Use [?] for any illegible character.")


class Readings(BaseModel):
    readings: list[Reading]


SYSTEM = (
    "You transcribe cropped lines from scanned medical and billing records. "
    "Each crop shows one line of the page (neighbouring lines may be partly visible at the edges; ignore them). Write exactly the characters printed in it: keep dates, codes, "
    "amounts and punctuation as printed, add normal spaces between words, and do not correct, "
    "complete or interpret anything. If a character is illegible write [?]. "
    "The OCR text shown with each crop may be wrong; use it only to know which line is meant."
)


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def reread_scanned_lines(lines: list[dict], doc_paths: dict[str, Path], llm: LLM) -> dict:
    ocr_lines = [l for l in lines if l["source"] == "ocr"]
    by_page: dict[tuple[str, int], list[dict]] = {}
    for l in ocr_lines:
        by_page.setdefault((l["doc"], l["page"]), []).append(l)

    changed = 0
    for (doc, pno), page_lines in by_page.items():
        page = pymupdf.open(doc_paths[doc])[pno - 1]
        for start in range(0, len(page_lines), BATCH):
            batch = page_lines[start : start + BATCH]
            content: list[dict] = []
            for l in batch:
                x0, y0, x1, y1 = l["bbox"]
                # The crop spans the full width of the page, never just the OCR box: OCR boxes
                # can start late (one cut off the "3" of "3/16/26"), and a model shown half a
                # date either refuses it or, worse, guesses the missing digit.
                clip = pymupdf.Rect(page.rect.x0 + 12, y0 - 4, page.rect.x1 - 12, y1 + 4)
                png = page.get_pixmap(clip=clip, dpi=CROP_DPI).tobytes("png")
                content.append({"type": "text", "text": f"Line {l['id']} (OCR read: {l['text']!r})"})
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                             "data": base64.standard_b64encode(png).decode()}})
            content.append({"type": "text", "text": f"Transcribe all {len(batch)} lines above, one reading per line id."})
            result = llm.parse(task=f"reread {doc} p{pno}", system=SYSTEM, content=content, schema=Readings, max_tokens=8000)
            got = {r.line_id: r.text for r in result.readings}
            for l in batch:
                if l["id"] not in got:
                    continue  # keep the OCR text; the verifier will treat it as unreliable
                vision = re.sub(r"\s+", " ", got[l["id"]]).strip()
                agreement = SequenceMatcher(None, _alnum(l["text"]), _alnum(vision)).ratio()
                l["ocr_text"] = l["text"]
                l["text"] = vision
                l["source"] = "ocr+vision"
                l["agreement"] = round(agreement, 3)
                changed += agreement < 0.999
    # The re-read covers the full row, so its highlight should too: OCR boxes can start late
    # or end early. Widen each re-read line to the text width of its page.
    for page_lines in by_page.values():
        left = min(l["bbox"][0] for l in page_lines)
        right = max(l["bbox"][2] for l in page_lines)
        for l in page_lines:
            if l["source"] == "ocr+vision":
                l["ocr_bbox"] = l["bbox"]
                l["bbox"] = (left, l["bbox"][1], right, l["bbox"][3])
    return {"lines_reread": len(ocr_lines), "lines_where_readings_differ": changed}
