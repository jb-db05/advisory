"""O01 Presentation Generator -- standalone entry point of the packaged skill (claude.ai).

Packaged as scripts/o01.py, next to scripts/syz_advisory/ (the generator), scripts/pypdf/
(PDF text, pure Python) and assets/ (SYZ template, samples), by apps/O01/O01_package_skill.py.
Needs Python 3.10+ and openpyxl; uses yfinance when installed (`pip install yfinance`).

    python scripts/o01.py --ingest /mnt/user-data/uploads/* --client C-0042
    python scripts/o01.py CASE.json [--prices PRICES.csv] [--offline]
    python scripts/o01.py --terms FILE.pdf|.html
    python scripts/o01.py --chart NVDA ^GSPC --vs ^GSPC --period 1y --png
    python scripts/o01.py --sample sp|client
    python scripts/o01.py --qc DECK.pptx

Outputs: --out / /mnt/user-data/outputs when it exists (claude.ai) / ./outputs. Every deck
gets an HTML preview next to it. Working data goes to $SYZ_DATA (default: a temp folder).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
os.environ.setdefault("SYZ_TEMPLATE", str(SKILL / "assets" / "S00_template.pptx"))
os.environ.setdefault("SYZ_DATA", str(Path(tempfile.gettempdir()) / "syz-o01"))
sys.path.insert(0, str(HERE))

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.exit("openpyxl is missing: run  pip install openpyxl  and try again")

from syz_advisory.decks import cli  # noqa: E402


def out_dir() -> Path:
    if "--out-dir" in sys.argv:
        i = sys.argv.index("--out-dir")
        d = Path(sys.argv[i + 1])
        del sys.argv[i:i + 2]
        return d
    if Path("/mnt/user-data/outputs").is_dir():
        return Path("/mnt/user-data/outputs")
    return Path.cwd() / "outputs"


if __name__ == "__main__":
    target = out_dir()
    sys.exit(cli.main(sys.argv[1:], target, samples=SKILL / "assets" / "samples", always_preview=True))
