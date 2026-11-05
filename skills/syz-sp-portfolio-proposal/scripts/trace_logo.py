"""Trace a logo PNG into a vector SVG with its own gradient: python scripts/trace_logo.py assets/logo.png assets/logo.svg 1

Needs `pip install potracer`. The last argument is 1 for this tracer (it treats False as the shape)."""
import sys
import numpy as np, potrace
from PIL import Image
src, dst, invert = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
im = Image.open(src).convert("RGBA"); a = np.asarray(im).astype(float); W, H = im.size
S, P = 2, 40                                   # trace at 2x, with a 40 px empty border
big = np.asarray(Image.fromarray(a[..., 3].astype("uint8")).resize((W*S, H*S), Image.LANCZOS)) > 127
pad = np.zeros((H*S + 2*P, W*S + 2*P), bool); pad[P:-P, P:-P] = big
mask = ~pad if invert else pad
path = potrace.Bitmap(mask).trace(turdsize=4, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.0, opticurve=True, opttolerance=0.2)
f = lambda p: f"{(p.x - P)/S:.1f} {(p.y - P)/S:.1f}"
d = []
for c in path:
    d.append(f"M{f(c.start_point)}")
    for s in c.segments:
        d.append(f"L{f(s.c)}L{f(s.end_point)}" if s.is_corner else f"C{f(s.c1)} {f(s.c2)} {f(s.end_point)}")
    d.append("Z")
stops = []
for i in range(11):
    x0 = int(i * (W - 1) / 10); band = a[:, max(0, x0 - 15):x0 + 15]; m = band[..., 3] > 200
    if m.sum() > 20:
        r, g, b = (band[..., k][m].mean() for k in range(3))
        stops.append(f'<stop offset="{i/10:.2f}" stop-color="#{int(r):02X}{int(g):02X}{int(b):02X}"/>')
open(dst, "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><defs><linearGradient id="syzg" x1="0" y1="0" x2="{W}" y2="0" gradientUnits="userSpaceOnUse">{"".join(stops)}</linearGradient></defs><path fill="url(#syzg)" fill-rule="evenodd" d="{"".join(d)}"/></svg>')
print(dst, len(path), "curves")
