"""Render the fictional record set to PDF files.

Digital documents keep a text layer. Scanned documents are rendered, tilted,
blurred and speckled, then saved as image-only pages, so they can be read only
through OCR, as in a real faxed or scanned record.
"""

import io
import json
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

from . import sample_case as case

CSS = """
* { font-family: sans-serif; font-size: 10.5pt; line-height: 1.35; color: #111; }
.org { font-size: 15pt; font-weight: bold; }
.addr { font-size: 9pt; color: #444; margin-bottom: 6pt; }
.title { font-size: 12pt; font-weight: bold; margin: 8pt 0 6pt 0; border-bottom: 1px solid #333; }
h3 { font-size: 10.5pt; font-weight: bold; margin: 9pt 0 2pt 0; }
p { margin: 3pt 0; }
table.meta td { padding-right: 24pt; }
table.grid { border-collapse: collapse; margin-top: 6pt; }
table.grid th, table.grid td { border: 0.6pt solid #555; padding: 3pt 5pt; font-size: 9.5pt; }
.r { text-align: right; }
.total { margin-top: 10pt; font-size: 11pt; }
.small { font-size: 8.5pt; color: #444; }
.footer { font-size: 7.5pt; color: #666; }
"""

LETTER = pymupdf.paper_rect("letter")
MARGIN = 54  # points


def _render_digital(pages_html: list[str], out: Path, fax: bool = False) -> None:
    writer = pymupdf.DocumentWriter(str(out))
    for i, html in enumerate(pages_html, start=1):
        if fax:
            html = (
                "<p class='small'>FAX 03/04/2026 09:12 FROM: BAYVIEW RMC BILLING TO: VEGA FILE PAGE 1/1</p>" + html
            )
        html += f"<p class='footer'>{case.FOOTER} - page {i} of {len(pages_html)}</p>"
        story = pymupdf.Story(html=html, user_css=CSS)
        where = LETTER + (MARGIN, MARGIN, -MARGIN, -MARGIN)
        more = True
        while more:
            dev = writer.begin_page(LETTER)
            more, _ = story.place(where)
            story.draw(dev)
            writer.end_page()
    writer.close()


def _scan(src: Path, out: Path, seed: int) -> None:
    """Turn a digital PDF into an image-only 'scan'."""
    rng = random.Random(seed)
    doc = pymupdf.open(src)
    scanned = pymupdf.open()
    for page in doc:
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        img = img.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, expand=False, fillcolor=255)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        px = img.load()
        for _ in range(img.width * img.height // 400):  # light speckle
            x, y = rng.randrange(img.width), rng.randrange(img.height)
            px[x, y] = rng.choice((0, 90, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        new = scanned.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=buf.getvalue())
    scanned.save(out, garbage=4, deflate=True)


def generate(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n, d in enumerate(case.DOCUMENTS):
        target = out_dir / d["file"]
        if d.get("scanned"):
            tmp = out_dir / f".{d['id']}_digital.pdf"
            _render_digital(d["pages"], tmp, fax=d.get("fax", False))
            _scan(tmp, target, seed=n)
            tmp.unlink()
        else:
            _render_digital(d["pages"], target)
        manifest.append({"id": d["id"], "file": d["file"], "title": d["title"]})
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
