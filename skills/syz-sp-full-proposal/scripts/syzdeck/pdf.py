"""Step 8: print the HTML to an A4 PDF.

Uses the first browser engine available: Playwright for Python, Playwright for Node, or a local
Chrome / Edge / Chromium in headless mode (Windows: Edge is always there).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets"   # <skill>/assets

BROWSERS = [
    "msedge", "chrome", "google-chrome", "chromium", "chromium-browser",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/opt/pw-browsers/chromium",
]


def _python_playwright(html: Path, pdf: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        page.goto(html.resolve().as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
        b.close()
    return True


def _node_playwright(html: Path, pdf: Path) -> bool:
    if not shutil.which("node"):
        return False
    script = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();"
              f"await p.goto({html.resolve().as_uri()!r},{{waitUntil:'networkidle'}});"
              f"await p.pdf({{path:{str(pdf)!r},preferCSSPageSize:true,printBackground:true}});await b.close();}})()"
              ".catch(e=>{console.error(e);process.exit(1)});")
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    return r.returncode == 0 and pdf.exists()


def _browser(html: Path, pdf: Path) -> bool:
    for b in BROWSERS:
        exe = shutil.which(b) or (b if os.path.exists(b) else None)
        if not exe:
            continue
        with tempfile.TemporaryDirectory() as profile:
            cmd = [exe, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}",
                   "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={pdf.resolve()}",
                   html.resolve().as_uri()]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if pdf.exists():
            return True
    return False


def to_pdf(html: Path, pdf: Path) -> str:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    if pdf.exists():
        pdf.unlink()
    raw = pdf.with_suffix(".body.pdf")
    for name, fn in (("Playwright (Python)", _python_playwright), ("Playwright (Node)", _node_playwright),
                     ("headless browser", _browser)):
        try:
            if fn(html, raw):
                engine = name
                break
        except Exception:
            continue
    else:
        raise RuntimeError("No browser engine found to print the PDF: install Playwright "
                           "(pip install playwright && playwright install chromium) or Chrome / Edge. "
                           f"The HTML is ready: {html}")
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for page in PdfReader(raw).pages:
        w.add_page(page)
    w.add_metadata({"/Producer": "SYZ Advisory", "/Title": html.stem})
    with open(pdf, "wb") as fh:
        w.write(fh)
    raw.unlink()
    return engine
