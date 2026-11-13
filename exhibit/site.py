"""Build the static viewer: page images, the PDFs, and one data file."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pymupdf

PAGE_DPI = 144


def build_site(result: dict, doc_dir: Path, template_dir: Path, out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "pages").mkdir(parents=True)
    (out_dir / "documents").mkdir()
    for f in template_dir.iterdir():
        if f.is_file():
            shutil.copy(f, out_dir / f.name)

    for d in result["documents"]:
        src = doc_dir / d["file"]
        shutil.copy(src, out_dir / "documents" / d["file"])
        pdf = pymupdf.open(src)
        for pno, page in enumerate(pdf, start=1):
            page.get_pixmap(dpi=PAGE_DPI).save(out_dir / "pages" / f"{d['id']}-p{pno}.png")

    data = {
        "case_name": result["case_name"],
        "documents": result["documents"],
        "pages": result["pages"],
        "lines": [
            {k: l[k] for k in ("id", "doc", "page", "text", "bbox", "source") if k in l}
            | ({"ocr_text": l["ocr_text"], "agreement": l["agreement"]} if "ocr_text" in l else {})
            for l in result["lines"]
        ],
        "duplicates": result["duplicates"],
        "case": result["case"],
        "quality": result["quality"],
        "comparison": result.get("comparison", {}),
    }
    (out_dir / "data.js").write_text("window.EXHIBIT = " + json.dumps(data, separators=(",", ":")) + ";\n")
