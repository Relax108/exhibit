"""Turn PDFs into numbered lines with page positions.

Every line gets a stable id such as ``D06.p2.l7`` (document, page, line). The
extractor may cite only these ids, and the verifier checks each cited value
against the text of exactly these lines, so a fact can always be traced back
to a box on a page.

Digital pages are read from the text layer. Pages without one are OCR'd with
RapidOCR (an ONNX port of PaddleOCR) at 200 dpi. Words or OCR segments are then
merged into visual rows, so a bill line reads as one line:
"02/24/2026 99204 New patient office visit 1 $425.00".
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pymupdf

OCR_DPI = 200
_ocr_engine = None


@dataclass
class Line:
    id: str
    doc: str
    page: int  # 1-based
    text: str
    bbox: tuple[float, float, float, float]  # PDF points, top-left origin
    source: str  # "text" or "ocr"
    confidence: float


@dataclass
class Page:
    doc: str
    number: int
    width: float
    height: float
    source: str


def _ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _rows(items: list[tuple[tuple[float, float, float, float], str, float]]):
    """Group (bbox, text, confidence) items into visual rows, top to bottom."""
    if not items:
        return []
    heights = sorted(b[3] - b[1] for b, _, _ in items)
    tol = max(2.0, heights[len(heights) // 2] * 0.55)
    items = sorted(items, key=lambda it: (it[0][1] + it[0][3]) / 2)
    rows, current, cy = [], [], None
    for it in items:
        y = (it[0][1] + it[0][3]) / 2
        if cy is not None and abs(y - cy) > tol:
            rows.append(current)
            current = []
        current.append(it)
        cy = y if len(current) == 1 else (cy * (len(current) - 1) + y) / len(current)
    rows.append(current)
    out = []
    for row in rows:
        row.sort(key=lambda it: it[0][0])
        text = unicodedata.normalize("NFKC", " ".join(t for _, t, _ in row)).strip()
        if not text:
            continue
        x0 = min(b[0] for b, _, _ in row)
        y0 = min(b[1] for b, _, _ in row)
        x1 = max(b[2] for b, _, _ in row)
        y1 = max(b[3] for b, _, _ in row)
        conf = min(c for _, _, c in row)
        out.append(((x0, y0, x1, y1), re.sub(r"\s+", " ", text), conf))
    return out


def read_document(doc_id: str, path: Path) -> tuple[list[Page], list[Line]]:
    pdf = pymupdf.open(path)
    pages, lines = [], []
    for pno, page in enumerate(pdf, start=1):
        words = page.get_text("words")
        if words:
            source = "text"
            items = [((w[0], w[1], w[2], w[3]), w[4], 1.0) for w in words]
        else:
            source = "ocr"
            pix = page.get_pixmap(dpi=OCR_DPI)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            result, _ = _ocr()(img)
            scale = 72.0 / OCR_DPI
            items = []
            for box, text, score in result or []:
                xs = [p[0] * scale for p in box]
                ys = [p[1] * scale for p in box]
                items.append(((min(xs), min(ys), max(xs), max(ys)), text, float(score)))
        pages.append(Page(doc_id, pno, page.rect.width, page.rect.height, source))
        for n, (bbox, text, conf) in enumerate(_rows(items), start=1):
            lines.append(Line(f"{doc_id}.p{pno}.l{n}", doc_id, pno, text, tuple(round(v, 1) for v in bbox), source, round(conf, 3)))
    return pages, lines


_NOISE = re.compile(r"(fax\W*\d.*?page\W*\d+\W*\d+)|(sample\W*record.*)", re.I)


def _fingerprint(lines: list[dict]) -> str:
    """Letters and digits only, without fax banners and footers.

    OCR often drops or adds spaces, so a word-level comparison misses a faxed
    copy of a digital original; a character-level one does not.
    """
    return "".join(re.sub(r"[^a-z0-9]", "", _NOISE.sub("", l["text"].lower())) for l in lines)


def find_duplicates(lines: list[dict], threshold: float = 0.9) -> dict[str, dict]:
    """Return {duplicate_doc: {"of": original_doc, "similarity": x}} (later document is the duplicate)."""
    docs: dict[str, list[dict]] = {}
    for l in lines:
        docs.setdefault(l["doc"], []).append(l)
    ids = sorted(docs)
    prints = {d: _fingerprint(docs[d]) for d in ids}
    dups = {}
    for i, a in enumerate(ids):
        if a in dups:
            continue
        for b in ids[i + 1 :]:
            if b in dups or not prints[a] or not prints[b]:
                continue
            ratio = SequenceMatcher(None, prints[a], prints[b], autojunk=False).ratio()
            if ratio >= threshold:
                dups[b] = {"of": a, "similarity": round(ratio, 4)}
    return dups


def ingest(documents: list[dict], doc_dir: Path) -> dict:
    all_pages, all_lines = [], []
    for d in documents:
        pages, lines = read_document(d["id"], doc_dir / d["file"])
        all_pages += pages
        all_lines += lines
    digest = {
        d["id"]: hashlib.sha256((doc_dir / d["file"]).read_bytes()).hexdigest()[:16] for d in documents
    }
    return {
        "pages": [asdict(p) for p in all_pages],
        "lines": [asdict(l) for l in all_lines],
        "file_sha256": digest,
    }
