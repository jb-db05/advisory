"""O02 Investment Solutions decks -- standalone entry point of the packaged skill (claude.ai).

Packaged as scripts/o02.py, next to scripts/o02_run.py (the command line), scripts/syz_advisory/
(the renderer), scripts/pypdf/ (PDF text, pure Python) and assets/ (SYZ template, sample), by
apps/O02/O02_package_skill.py. Needs Python 3.10+ and openpyxl.

    python scripts/o02.py SPEC.json [--offline] [--out DECK.pptx]
    python scripts/o02.py --extract OLD_DECK.pdf|.pptx
    python scripts/o02.py --news NVDA SOXX
    python scripts/o02.py --qc DECK.pptx

Outputs: --out-dir / /mnt/user-data/outputs when it exists (claude.ai) / ./outputs. Every deck
gets an HTML preview next to it.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
os.environ.setdefault("SYZ_TEMPLATE", str(SKILL / "assets" / "S00_template.pptx"))
os.environ.setdefault("SYZ_DATA", str(Path(tempfile.gettempdir()) / "syz-o02"))
sys.path.insert(0, str(HERE))

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.exit("openpyxl is missing: run  pip install openpyxl  and try again")

from o02_run import main  # noqa: E402


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
    args = sys.argv[1:]
    if args and not args[0].startswith("--") and "--preview" not in args:
        args.append("--preview")
    sys.exit(main(args, target))
