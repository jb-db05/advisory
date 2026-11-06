"""Build the single-file HTML vol monitor (no Python needed to *use* it).

Inlines into html/template.html: the SheetJS Excel reader (xlsx.full.min.js, Apache-2.0), the
Nunito fonts and the Syz logo, and writes syz_vol_monitor.html next to the tool.

    python html/build.py path/to/xlsx.full.min.js
(get the library with: npm pack xlsx@0.18.5 && tar -xzf xlsx-0.18.5.tgz -> package/dist/xlsx.full.min.js)
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
b64 = lambda p: base64.b64encode(Path(p).read_bytes()).decode()

html = (ROOT / "html" / "template.html").read_text()
html = (html.replace("__FONT_REG__", b64(ROOT / "static/fonts/NunitoSans-Regular.ttf"))
            .replace("__FONT_BOLD__", b64(ROOT / "static/fonts/NunitoSans-Bold.ttf"))
            .replace("__FONT_TITLE__", b64(ROOT / "static/fonts/Nunito-Bold.ttf"))
            .replace("__LOGO__", b64(ROOT / "static/logo.svg")))
lib = Path(sys.argv[1]).read_text().replace("</script", "<\\/script")
html = html.replace("__XLSX_LIB__", lib)
out = ROOT / "syz_vol_monitor.html"
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
