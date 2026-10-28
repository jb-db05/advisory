"""Read a finished deck back and check it -- the only real test of a .pptx here
(PowerPoint automation and headless browsers are blocked by group policy).

Errors make the deck unfit to send; warnings need a look.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from syz_advisory.decks.ooxml import BODY_B, EMU, FONT, PAGE_H, PAGE_W, TITLE_FONT, TITLE_MAX, text_height

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
R = "{http://schemas.openxmlformats.org/package/2006/relationships}"
ALLOWED_FONTS = {FONT, TITLE_FONT, "+mn-lt", "+mj-lt", "+mn-cs", "+mj-cs", "Arial"}       # Arial: bullet glyphs only
# A Python / JS null printed as a value: a text run that is only that word, or one ending a
# label ("Coupon: None"). "None (1x)" in a sentence is English, not a leak.
LEAKS = re.compile(r"^\s*(None|nan|NaN|null|undefined)\s*$|:\s*(None|nan|NaN|null|undefined)\b|\{\{|\}\}|Traceback")


def check(path: Path) -> list[tuple[str, int, str]]:
    issues: list[tuple[str, int, str]] = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        parts = {n: z.read(n) for n in names}
    # 1. package integrity
    ct = ET.fromstring(parts["[Content_Types].xml"])
    defaults = {e.get("Extension").lower() for e in ct if e.tag.endswith("Default")}
    overrides = {e.get("PartName").lstrip("/") for e in ct if e.tag.endswith("Override")}
    for n in names:
        if n.endswith("/") or n == "[Content_Types].xml":
            continue
        if n not in overrides and n.rsplit(".", 1)[-1].lower() not in defaults:
            issues.append(("error", 0, f"no content type for {n}"))
        if n.endswith((".xml", ".rels")):
            try:
                ET.fromstring(parts[n])
            except ET.ParseError as exc:
                issues.append(("error", 0, f"{n} is not well-formed XML: {exc}"))
    for n in [n for n in names if n.endswith(".rels")]:
        base = PurePosixPath(n.replace("_rels/", "").removesuffix(".rels")).parent
        for rel in ET.fromstring(parts[n]):
            if rel.get("TargetMode") == "External":
                continue
            target = str((base / rel.get("Target")).as_posix())
            target = _normalise(target)
            if target not in names:
                issues.append(("error", 0, f"{n}: missing target {target}"))
    # 2. slides
    slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.search(r"\d+", n.split("/")[-1]).group()))
    if not slides:
        issues.append(("error", 0, "the deck has no slides"))
    for k, n in enumerate(slides, start=1):
        root = ET.fromstring(parts[n])
        rels = ET.fromstring(parts[n.replace("slides/", "slides/_rels/") + ".rels"])
        layout = next((r.get("Target") for r in rels if r.get("Type", "").endswith("/slideLayout")), "")
        layout_xml = parts.get(_normalise(str(PurePosixPath("ppt/slides") / layout)), b"")
        content_page = b'name="One Content"' in layout_xml
        for rpr in root.iter():
            if rpr.tag in (A + "latin", A + "cs") and rpr.get("typeface") not in ALLOWED_FONTS:
                issues.append(("error", k, f"font {rpr.get('typeface')!r} (house faces: {FONT} for text, {TITLE_FONT} Bold for titles)"))
        # House rule: slide titles and every run on the cover are Nunito Bold.
        title_shapes = [sp for sp in root.iter(P + "sp")
                        if k == 1 or any(ph.get("type") in ("title", "ctrTitle") for ph in sp.iter(P + "ph"))]
        for sp in title_shapes:
            for r in sp.iter(A + "r"):
                rpr, text = r.find(A + "rPr"), "".join(t.text or "" for t in r.iter(A + "t")).strip()
                latin = rpr.find(A + "latin") if rpr is not None else None
                if text and (latin is None or latin.get("typeface") != TITLE_FONT or rpr.get("b") != "1"):
                    where = "cover" if k == 1 else "title"
                    issues.append(("error", k, f"{where} text {text[:30]!r} is not {TITLE_FONT} Bold"))
                    break
        leak = next((m for m in (LEAKS.search(t.text or "") for t in root.iter(A + "t")) if m), None)
        if leak:
            issues.append(("error", k, f"leaked placeholder or null value: {leak.group(0).strip()!r}"))
        if content_page:
            title = [sp for sp in root.iter(P + "sp") if any(ph.get("type") == "title" for ph in sp.iter(P + "ph"))]
            heading = "".join(t.text or "" for t in title[0].iter(A + "t")).strip() if title else ""
            if not heading:
                issues.append(("error", k, "content slide without a title"))
            elif len(heading) > TITLE_MAX:
                issues.append(("warning", k, f"title is {len(heading)} characters (keep it under {TITLE_MAX}): {heading!r}"))
        boxes = []
        for el in list(root.iter(P + "sp")) + list(root.iter(P + "graphicFrame")) + list(root.iter(P + "pic")):
            off, ext = el.find(".//" + A + "off"), el.find(".//" + A + "ext")
            if off is None or ext is None:
                continue                                   # placeholder: geometry from the layout
            x, y = int(off.get("x")) / EMU, int(off.get("y")) / EMU
            w, h = int(ext.get("cx")) / EMU, int(ext.get("cy")) / EMU
            name = (el.find(".//" + P + "cNvPr").get("name") or "")
            if x < -0.01 or y < -0.01 or x + w > PAGE_W + 0.01 or y + h > PAGE_H + 0.01:
                issues.append(("error", k, f"{name} runs off the page"))
            if content_page and y + h > BODY_B + 0.02 and h > 0:
                issues.append(("error", k, f"{name} ends at {y + h:.2f} in, over the compliance footer (body ends {BODY_B} in)"))
            boxes.append((name, x, y, w, h))
            if el.tag == P + "sp" and w > 0.3 and h > 0.2:
                body = el.find(".//" + A + "bodyPr")
                inset = int(body.get("lIns", 91440)) / EMU if body is not None else 0.1
                need, sized = inset, False
                for p in el.iter(A + "p"):
                    text_p = "".join(t.text or "" for t in p.iter(A + "t"))
                    rpr = next((r for r in p.iter(A + "rPr") if r.get("sz")), None)
                    if not text_p or rpr is None:
                        continue
                    sized = True
                    size = int(rpr.get("sz")) / 100
                    indent = 0.19 if p.find(".//" + A + "buChar") is not None else 0
                    need += text_height([text_p], w - indent, size, rpr.get("b") == "1", inset) - inset + size * 0.45 / 72
                if sized and need > h + 0.05:
                    issues.append(("warning", k, f"{name}: text needs ~{need:.2f} in, the box is {h:.2f} in"))
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if _overlap(a, b) > 0.04 and not {"Accent", "Card"} & {a[0].split()[0], b[0].split()[0]}:
                    issues.append(("warning", k, f"{a[0]} overlaps {b[0]}"))
    # 3. charts
    for n in [n for n in names if re.fullmatch(r"ppt/charts/chart\d+\.xml", n)]:
        root = ET.fromstring(parts[n])
        series = list(root.iter(C + "ser"))
        if not series:
            issues.append(("error", 0, f"{n}: chart without series"))
        for cache in root.iter(C + "numCache"):
            count = int(cache.find(C + "ptCount").get("val"))
            pts = cache.findall(C + "pt")
            if any(int(p.get("idx")) >= count for p in pts):
                issues.append(("error", 0, f"{n}: point index beyond ptCount"))
            for p in pts:
                v = p.find(C + "v").text
                try:
                    float(v)
                except (TypeError, ValueError):
                    issues.append(("error", 0, f"{n}: non-numeric value {v!r}"))
    return issues


def _normalise(path: str) -> str:
    out = []
    for part in path.split("/"):
        if part == "..":
            if out:
                out.pop()
        elif part not in ("", "."):
            out.append(part)
    return "/".join(out)


def _overlap(a, b) -> float:
    _, ax, ay, aw, ah = a
    _, bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    return w * h if w > 0 and h > 0 else 0.0


def report(issues: list[tuple[str, int, str]]) -> str:
    if not issues:
        return "QC: no issues."
    lines = [f"QC: {sum(1 for s, *_ in issues if s == 'error')} error(s), {sum(1 for s, *_ in issues if s == 'warning')} warning(s)"]
    lines += [f"  {s.upper():7} slide {k or '-':>2}  {m}" for s, k, m in issues]
    return "\n".join(lines)
