"""A small vector PDF writer in pure Python: lines, shapes and text in an embedded TrueType font.

reportlab and fpdf need Pillow, whose compiled extension is blocked by group policy, and headless
Edge cannot print to PDF here; this covers what charts and tables need. Coordinates are in points
from the top-left corner of the page. Text is WinAnsi (cp1252): €, –, ·, é and the like work;
other characters are replaced.
"""

from __future__ import annotations

import math
import os
import struct
import zlib
from pathlib import Path

# House fonts: Nunito Sans for text, Nunito Bold for titles (and bold text). The skill bundles them in
# assets/fonts (SIL OFL), so they are used without being installed. SYZ_FONTS may name another folder
# holding them; apps/S00/fonts holds them in the workspace. Open Sans, DejaVu and Liberation are only
# fallbacks for when the files are missing.
_PAIRS = [("NunitoSans-Regular.ttf", "Nunito-Bold.ttf"), ("OpenSans-Regular.ttf", "OpenSans-Bold.ttf"),
          ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"), ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf")]
_BUNDLED = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_SHARED = Path(__file__).resolve().parents[2] / "apps" / "S00" / "fonts"
_DIRS = [os.environ.get("SYZ_FONTS"), str(_BUNDLED), str(_SHARED), r"C:\Windows\Fonts",
         os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"),
         "/usr/share/fonts/truetype/open-sans", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
         "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/TTF", "/Library/Fonts"]


NUNITO_SANS = [("NunitoSans-Regular.ttf", "NunitoSans-Bold.ttf"),
               ("NunitoSans_10pt-Regular.ttf", "NunitoSans_10pt-Bold.ttf")]


def find_fonts(pairs: list[tuple[str, str]] | None = None) -> tuple[Path, Path] | None:
    """(regular, bold) TrueType files of the first face found, or None. `pairs` defaults to the
    house pair (Nunito Sans / Nunito Bold) and its stand-ins; pass e.g. NUNITO_SANS to look for
    another pair first."""
    for reg, bold in pairs or _PAIRS:
        for d in filter(None, _DIRS):
            if (Path(d) / reg).is_file() and (Path(d) / bold).is_file():
                return Path(d) / reg, Path(d) / bold
    return None


_FOUND = find_fonts()
REGULAR, BOLD = _FOUND or (Path(r"C:\Windows\Fonts\OpenSans-Regular.ttf"), Path(r"C:\Windows\Fonts\OpenSans-Bold.ttf"))
A4 = (595.28, 841.89)
_SWAP = {"→": ">", "←": "<", "≤": "<=", "≥": ">=", "−": "-"}


def _rgb(colour: str) -> str:
    c = colour.lstrip("#")
    return " ".join(f"{int(c[i:i + 2], 16) / 255:.3f}" for i in (0, 2, 4))


def _cp1252(text: str) -> bytes:
    for a, b in _SWAP.items():
        text = text.replace(a, b)
    return text.encode("cp1252", errors="replace")


def _encode(text: str) -> bytes:
    """A PDF string literal's body."""
    return _cp1252(text).replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class TrueType:
    """Widths and metrics of a TrueType font, for a simple WinAnsi font."""

    def __init__(self, path: Path):
        self.path, self.data = path, path.read_bytes()
        d = self.data
        n = struct.unpack(">H", d[4:6])[0]
        t = {d[12 + 16 * i:16 + 16 * i].decode("latin-1"): struct.unpack(">II", d[20 + 16 * i:28 + 16 * i])
             for i in range(n)}
        head, hhea, hmtx, os2 = (t[k][0] for k in ("head", "hhea", "hmtx", "OS/2"))
        self.upm = struct.unpack(">H", d[head + 18:head + 20])[0]
        self.bbox = struct.unpack(">hhhh", d[head + 36:head + 44])
        self.ascent, self.descent = struct.unpack(">hh", d[hhea + 4:hhea + 8])
        n_metrics = struct.unpack(">H", d[hhea + 34:hhea + 36])[0]
        advances = [struct.unpack(">H", d[hmtx + 4 * i:hmtx + 4 * i + 2])[0] for i in range(n_metrics)]
        version = struct.unpack(">H", d[os2:os2 + 2])[0]
        self.cap = struct.unpack(">h", d[os2 + 88:os2 + 90])[0] if version >= 2 else self.ascent
        glyph = self._cmap(t["cmap"][0])
        self.widths = []
        for code in range(32, 256):
            try:
                ch = bytes([code]).decode("cp1252")
            except UnicodeDecodeError:
                self.widths.append(0)
                continue
            g = glyph.get(ord(ch), 0)
            self.widths.append(round(advances[min(g, n_metrics - 1)] * 1000 / self.upm))

    def _cmap(self, at: int) -> dict[int, int]:
        """Unicode -> glyph from the (3, 1) format 4 subtable."""
        d = self.data
        for i in range(struct.unpack(">H", d[at + 2:at + 4])[0]):
            plat, enc, off = struct.unpack(">HHI", d[at + 4 + 8 * i:at + 12 + 8 * i])
            sub = at + off
            if (plat, enc) == (3, 1) and struct.unpack(">H", d[sub:sub + 2])[0] == 4:
                break
        else:
            raise ValueError(f"{self.path.name}: no Unicode BMP cmap")
        segs = struct.unpack(">H", d[sub + 6:sub + 8])[0] // 2
        arr = lambda k: struct.unpack(f">{segs}H", d[sub + k:sub + k + 2 * segs])  # noqa: E731
        ends, starts = arr(14), arr(16 + 2 * segs)
        deltas, ranges_at = arr(16 + 4 * segs), sub + 16 + 6 * segs
        ranges = arr(16 + 6 * segs)
        out = {}
        for s in range(segs):
            for c in range(starts[s], min(ends[s], 0x2FFF) + 1):
                if ranges[s] == 0:
                    g = (c + deltas[s]) & 0xFFFF
                else:
                    p = ranges_at + 2 * s + ranges[s] + 2 * (c - starts[s])
                    g = struct.unpack(">H", d[p:p + 2])[0]
                    g = (g + deltas[s]) & 0xFFFF if g else 0
                out[c] = g
        return out

    def width(self, text: str, size: float) -> float:
        return sum(self.widths[b - 32] for b in _cp1252(text) if b >= 32) * size / 1000


class Page:
    def __init__(self, doc: "Document", w: float, h: float):
        self.doc, self.w, self.h, self.ops = doc, w, h, []

    def _y(self, y: float) -> float:
        return self.h - y

    def _stroke(self, colour: str, width: float, dash) -> None:
        self.ops.append(f"{_rgb(colour)} RG {width:.2f} w " + (f"[{' '.join(str(x) for x in dash)}] 0 d" if dash else "[] 0 d"))

    def line(self, x1, y1, x2, y2, colour="#000000", width=0.75, dash=None) -> None:
        self._stroke(colour, width, dash)
        self.ops.append(f"{x1:.2f} {self._y(y1):.2f} m {x2:.2f} {self._y(y2):.2f} l S")

    def polyline(self, pts, colour="#000000", width=1.0) -> None:
        if len(pts) < 2:
            return
        self._stroke(colour, width, None)
        self.ops.append("1 j " + " ".join(f"{x:.2f} {self._y(y):.2f} {'m' if i == 0 else 'l'}"
                                          for i, (x, y) in enumerate(pts)) + " S 0 j")

    def rect(self, x, y, w, h, fill=None, stroke=None, width=0.75, radius=0.0) -> None:
        if stroke:
            self._stroke(stroke, width, None)
        if fill:
            self.ops.append(f"{_rgb(fill)} rg")
        if radius:
            r, k = radius, radius * 0.5523
            x0, y0, x1, y1 = x, self._y(y + h), x + w, self._y(y)
            self.ops.append(
                f"{x0 + r:.2f} {y0:.2f} m {x1 - r:.2f} {y0:.2f} l {x1 - r + k:.2f} {y0:.2f} {x1:.2f} {y0 + r - k:.2f} "
                f"{x1:.2f} {y0 + r:.2f} c {x1:.2f} {y1 - r:.2f} l {x1:.2f} {y1 - r + k:.2f} {x1 - r + k:.2f} {y1:.2f} "
                f"{x1 - r:.2f} {y1:.2f} c {x0 + r:.2f} {y1:.2f} l {x0 + r - k:.2f} {y1:.2f} {x0:.2f} {y1 - r + k:.2f} "
                f"{x0:.2f} {y1 - r:.2f} c {x0:.2f} {y0 + r:.2f} l {x0:.2f} {y0 + r - k:.2f} {x0 + r - k:.2f} {y0:.2f} "
                f"{x0 + r:.2f} {y0:.2f} c h")
        else:
            self.ops.append(f"{x:.2f} {self._y(y + h):.2f} {w:.2f} {h:.2f} re")
        self.ops.append("B" if fill and stroke else "f" if fill else "S")

    def circle(self, cx, cy, r, fill=None, stroke=None, width=0.75) -> None:
        k, y = r * 0.5523, self._y(cy)
        if stroke:
            self._stroke(stroke, width, None)
        if fill:
            self.ops.append(f"{_rgb(fill)} rg")
        self.ops.append(
            f"{cx + r:.2f} {y:.2f} m {cx + r:.2f} {y + k:.2f} {cx + k:.2f} {y + r:.2f} {cx:.2f} {y + r:.2f} c "
            f"{cx - k:.2f} {y + r:.2f} {cx - r:.2f} {y + k:.2f} {cx - r:.2f} {y:.2f} c "
            f"{cx - r:.2f} {y - k:.2f} {cx - k:.2f} {y - r:.2f} {cx:.2f} {y - r:.2f} c "
            f"{cx + k:.2f} {y - r:.2f} {cx + r:.2f} {y - k:.2f} {cx + r:.2f} {y:.2f} c "
            + ("B" if fill and stroke else "f" if fill else "S"))

    def image(self, data: bytes, x, y, w, h) -> None:
        """A JPEG or PNG (8-bit RGB / RGBA, not interlaced) drawn into the box x, y, w, h. Parts
        outside the page are clipped by the viewer, so a box larger than the page crops the image."""
        name = self.doc.image_name(data)
        self.ops.append(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {self._y(y + h):.2f} cm /{name} Do Q")

    def text(self, x, y, s, size=9.0, bold=False, colour="#000000", anchor="start") -> float:
        """Text with its baseline at y; anchor start / middle / end. Returns its width."""
        s = str(s)
        w = self.width(s, size, bold)
        x -= w / 2 if anchor == "middle" else w if anchor == "end" else 0
        self.ops.append(f"BT /F{2 if bold else 1} {size:.2f} Tf {_rgb(colour)} rg {x:.2f} {self._y(y):.2f} Td "
                        f"({_encode(s).decode('latin-1')}) Tj ET")
        return w

    def width(self, s: str, size=9.0, bold=False) -> float:
        return (self.doc.bold if bold else self.doc.regular).width(str(s), size)

    def fit(self, s: str, size: float, max_w: float, bold=False) -> str:
        """s, cut with an ellipsis to fit max_w."""
        s = str(s)
        if self.width(s, size, bold) <= max_w:
            return s
        while s and self.width(s + "…", size, bold) > max_w:
            s = s[:-1]
        return s.rstrip(" /·") + "…"

    def wrap(self, s: str, size: float, max_w: float, bold=False) -> list[str]:
        lines, cur = [], ""
        for word in str(s).split():
            trial = f"{cur} {word}".strip()
            if cur and self.width(trial, size, bold) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + ([cur] if cur else [])


class Document:
    def __init__(self, title: str = "", regular: Path = REGULAR, bold: Path = BOLD):
        if not (regular.is_file() and bold.is_file()):
            raise FileNotFoundError(f"No TrueType font found (looked for {', '.join(p[0] for p in _PAIRS)}); "
                                    "set SYZ_FONTS to a folder holding a Regular and a Bold .ttf")
        self.title, self.pages = title, []
        self.regular, self.bold = TrueType(regular), TrueType(bold)
        self.images: dict[bytes, str] = {}          # image bytes -> resource name, each embedded once

    def image_name(self, data: bytes) -> str:
        if data not in self.images:
            self.images[data] = f"Im{len(self.images) + 1}"
        return self.images[data]

    def page(self, size=A4) -> Page:
        p = Page(self, *size)
        self.pages.append(p)
        return p

    def save(self, path: Path) -> Path:
        objs: list[bytes] = []

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        def stream(data: bytes, extra: str = "") -> bytes:
            z = zlib.compress(data, 9)
            return f"<< /Length {len(z)} /Filter /FlateDecode {extra}>>\nstream\n".encode() + z + b"\nendstream"

        fonts = []
        for i, f in enumerate((self.regular, self.bold), 1):
            name = f.path.stem.replace("-Regular", "").replace(" ", "")
            ff = add(stream(f.data, f"/Length1 {len(f.data)} "))
            s = 1000 / f.upm
            desc = add((f"<< /Type /FontDescriptor /FontName /{name} /Flags 32 /FontBBox [{' '.join(str(round(v * s)) for v in f.bbox)}] "
                        f"/ItalicAngle 0 /Ascent {round(f.ascent * s)} /Descent {round(f.descent * s)} "
                        f"/CapHeight {round(f.cap * s)} /StemV {120 if i == 2 else 80} /FontFile2 {ff} 0 R >>").encode())
            fonts.append(add((f"<< /Type /Font /Subtype /TrueType /BaseFont /{name} /FirstChar 32 /LastChar 255 "
                              f"/Widths [{' '.join(map(str, f.widths))}] /Encoding /WinAnsiEncoding "
                              f"/FontDescriptor {desc} 0 R >>").encode()))
        xobjects = []
        for data, name in self.images.items():
            xobjects.append(f"/{name} {_image_object(data, add, stream)} 0 R")
        resources = f"/Font << /F1 {fonts[0]} 0 R /F2 {fonts[1]} 0 R >>" + (
            f" /XObject << {' '.join(xobjects)} >>" if xobjects else "")
        pages_id = len(objs) + 1 + 2 * len(self.pages) + 1    # after the page and content objects, and the catalog
        kids = []
        for p in self.pages:
            content = add(stream("\n".join(p.ops).encode("latin-1")))
            kids.append(add((f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {p.w:.2f} {p.h:.2f}] "
                             f"/Resources << {resources} >> "
                             f"/Contents {content} 0 R >>").encode()))
        catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
        assert add((f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>").encode()) == pages_id
        title = self.title.replace("\\", "").replace("(", "").replace(")", "")
        info = add(f"<< /Title ({title}) /Producer (SYZ Advisory) >>".encode("latin-1", "replace"))

        out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        path.write_bytes(bytes(out))
        return path


def _image_object(data: bytes, add, stream) -> int:
    """Embed a JPEG as is (DCTDecode), or a PNG as RGB plus an alpha soft mask. Returns the object id."""
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                _, h, w, comps = struct.unpack(">BHHB", data[i + 4:i + 10])
                break
            i += 2 + length
        else:
            raise ValueError("JPEG without a frame header")
        space = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}[comps]
        head = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace {space} "
                f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n").encode()
        return add(head + data + b"\nendstream")
    w, h, rgb, alpha = decode_png(data)
    mask = add(stream(alpha, f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
                             f"/BitsPerComponent 8 ")) if alpha else None
    return add(stream(rgb, f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                           f"/BitsPerComponent 8 " + (f"/SMask {mask} 0 R " if alpha else "")))


def decode_png(data: bytes) -> tuple[int, int, bytes, bytes | None]:
    """(width, height, RGB bytes, alpha bytes or None) of an 8-bit RGB or RGBA, non-interlaced PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat = 8, bytearray()
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    if depth != 8 or ctype not in (2, 6) or interlace:
        raise ValueError("only 8-bit RGB / RGBA PNGs without interlacing are supported")
    bpp = 4 if ctype == 6 else 3
    raw, stride = zlib.decompress(bytes(idat)), w * bpp
    out, prev = bytearray(), bytearray(stride)
    for r in range(h):
        f, row = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        if f == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif f == 2:
            row = bytearray((a + b) & 255 for a, b in zip(row, prev))
        elif f == 3:
            for i in range(stride):
                row[i] = (row[i] + ((row[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b, c = prev[i], prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += row
        prev = row
    if bpp == 3:
        return w, h, bytes(out), None
    rgb = bytearray(w * h * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = out[0::4], out[1::4], out[2::4]
    return w, h, bytes(rgb), bytes(out[3::4])


def nice_step(span: float, ticks: int = 7) -> float:
    """A round grid step giving at most `ticks` lines over span."""
    for s in (1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        if span / s <= ticks:
            return s
    return 10 ** math.ceil(math.log10(span))
