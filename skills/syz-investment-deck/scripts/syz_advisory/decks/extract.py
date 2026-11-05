"""Read an existing deck (PDF or PPTX) back into its parts, to rebuild it in the SYZ format.

    extract(path, out_dir) -> summary dict

Writes to `out_dir`:
    slides.md      every page's text, in order (what the deck says, to keep the analysis)
    charts.json    PPTX only: each native chart's series and categories (the numbers behind it)
    images/        embedded pictures (chart screenshots, photos), reusable in `image` blocks
    draft.json     a deck spec with one slide per page (title + the text as points), the
                   starting point to restructure: split, merge, turn numbers into charts

Disclaimer and closing pages are recognised and left out of the draft (the builder adds them).
"""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
BOILERPLATE = re.compile(r"This communication has been sent to recipients|Welcome to\s*Syzerland|Important Information\s*$", re.I)
NOISE = re.compile(r"^(PRIVATE\s*&\s*CONFIDENTIAL|Please see important information.*|\d{1,3})$", re.I)


def _clean(lines: list[str]) -> list[str]:
    out = []
    for l in lines:
        l = re.sub(r"^\d{1,3}(?=Please see important)", "", l.strip())
        l = re.sub(r"Please see important information at the end of the document", "", l).strip()
        if l and not NOISE.match(l):
            out.append(l)
    return out


def _pdf(path: Path, img_dir: Path) -> tuple[list[dict], list[dict]]:
    import pypdf
    pages, images = [], []
    for n, page in enumerate(pypdf.PdfReader(str(path)).pages, start=1):
        text = page.extract_text() or ""
        pics = []
        try:
            for k, im in enumerate(page.images, start=1):
                ext = Path(im.name).suffix.lower() or ".bin"
                if ext not in (".jpg", ".jpeg", ".png"):
                    continue                              # other encodings need Pillow (blocked here)
                f = img_dir / f"page{n:02d}_{k}{ext}"
                f.write_bytes(im.data)
                pics.append(f.name)
        except Exception as exc:                          # an image pypdf cannot decode: note it, go on
            pics.append(f"(images not extracted: {type(exc).__name__})")
        pages.append({"page": n, "lines": _clean(text.splitlines()), "images": pics})
        images += [{"page": n, "file": p} for p in pics if not p.startswith("(")]
    return pages, images


def _pptx(path: Path, img_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    z = zipfile.ZipFile(path)
    names = z.namelist()
    slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
    pages, images, charts = [], [], []
    for k, n in enumerate(slides, start=1):
        root = ET.fromstring(z.read(n))
        lines = []
        for p in root.iter(A + "p"):
            t = "".join(x.text or "" for x in p.iter(A + "t")).strip()
            if t:
                lines.append(t)
        for tbl in root.iter(A + "tbl"):
            for tr in tbl.iter(A + "tr"):
                cells = ["".join(x.text or "" for x in tc.iter(A + "t")).strip() for tc in tr.iter(A + "tc")]
                lines.append(" | ".join(cells))
        rel_path = n.replace("slides/", "slides/_rels/") + ".rels"
        pics = []
        if rel_path in names:
            for rel in ET.fromstring(z.read(rel_path)):
                target = str(PurePosixPath("ppt/slides") / rel.get("Target"))
                target = re.sub(r"[^/]+/\.\./", "", target)
                kind = rel.get("Type", "")
                if kind.endswith("/image") and target in names and Path(target).suffix.lower() in (".png", ".jpg", ".jpeg"):
                    f = img_dir / f"slide{k:02d}_{Path(target).name}"
                    f.write_bytes(z.read(target))
                    pics.append(f.name)
                elif kind.endswith("/chart") and target in names:
                    charts.append({"slide": k, **_chart_data(z.read(target))})
        pages.append({"page": k, "lines": _clean(lines), "images": pics})
        images += [{"page": k, "file": p} for p in pics]
    return pages, images, charts


def _chart_data(xml: bytes) -> dict:
    root = ET.fromstring(xml)
    kind = next((t.tag.split("}")[1] for t in root.iter() if t.tag.endswith("Chart") and t.tag != C + "chart"), "")
    series = []
    for ser in root.iter(C + "ser"):
        def cache(tag):
            el = ser.find(C + tag)
            if el is None:
                return []
            return [v.text for v in el.iter(C + "v")]
        name = "".join(cache("tx")) or f"Series {len(series) + 1}"
        series.append({"name": name, "categories": cache("cat") or cache("xVal"), "values": cache("val") or cache("yVal")})
    return {"type": kind, "series": series}


def _draft(pages: list[dict], source_name: str) -> dict:
    slides = []
    for p in pages:
        if not p["lines"] or BOILERPLATE.search(" ".join(p["lines"])):
            continue
        if p["page"] == 1 and any(re.search(r"Investment Solutions|by your Advisory Team", l, re.I) for l in p["lines"]):
            continue                                       # the cover: rebuilt from the deck's title and date
        title, *rest = p["lines"]
        slides.append({"title": title[:60], "subtitle": "", "blocks": [{"type": "text", "items": rest[:40]}],
                       "source": "", "_from": f"{source_name}, page {p['page']}",
                       **({"_images": p["images"]} if p["images"] else {})})
    return {"title": "Investment Solutions\nby your Advisory Team", "date": "", "cover_caption": "", "slides": slides}


def extract(path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "images"
    img_dir.mkdir(exist_ok=True)
    charts: list[dict] = []
    if path.suffix.lower() == ".pdf":
        pages, images = _pdf(path, img_dir)
    elif path.suffix.lower() == ".pptx":
        pages, images, charts = _pptx(path, img_dir)
    else:
        raise ValueError(f"{path.name}: give a .pdf or a .pptx")
    md = [f"# {path.name}: {len(pages)} pages\n"]
    for p in pages:
        md.append(f"\n## Page {p['page']}" + (" (boilerplate: disclaimer / closing)" if BOILERPLATE.search(" ".join(p["lines"])) else ""))
        md += [f"- {l}" for l in p["lines"]]
        if p["images"]:
            md.append(f"- images: {', '.join(p['images'])}")
    (out_dir / "slides.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out_dir / "charts.json").write_text(json.dumps(charts, indent=1, ensure_ascii=False), encoding="utf-8")
    draft = _draft(pages, path.name)
    (out_dir / "draft.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": len(pages), "images": len(images), "charts": len(charts), "draft_slides": len(draft["slides"]),
            "out": out_dir}
