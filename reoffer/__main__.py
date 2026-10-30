"""Command line:

    python -m reoffer run                 process the inbox, refresh reports
    python -m reoffer run old.xlsx        import specific files (left in place)
    python -m reoffer check trades.csv    dry run: show what would be refused
    python -m reoffer report              rebuild the reports only
    python -m reoffer template            write a fresh input template
"""

import argparse
import sys
from pathlib import Path

from .clean import blank, clean_frame
from .ingest import read_file
from .pipeline import Workspace, load_register, run
from .reference import Reference
from .report import build_report
from .template import build_template


def main(argv=None):
    p = argparse.ArgumentParser(prog="reoffer", description="Reoffer trade register")
    p.add_argument("--workspace", default="workspace", help="folder with inbox/ and register")
    p.add_argument("--reference", default=None, help="folder with lists/aliases/fx CSVs")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="import inbox (or given files) and rebuild reports")
    r.add_argument("files", nargs="*")
    c = sub.add_parser("check", help="validate files without importing")
    c.add_argument("files", nargs="+")
    sub.add_parser("report", help="rebuild reoffer_report.xlsx from the register")
    t = sub.add_parser("template", help="write the Excel input template")
    t.add_argument("--out", default=None)
    a = p.parse_args(argv)

    ref = Reference.load(a.reference) if a.reference else Reference.load()
    ws = Workspace(a.workspace)

    if a.cmd == "run":
        res = run(ws.root, a.reference, files=a.files or None)
        print(f"Files read:      {len(res.files)}")
        for e in res.file_errors:
            print(f"  NOT READ  {e}")
        print(f"Accepted:        {res.accepted}  (auto-corrected: {res.corrected})")
        print(f"Refused:         {res.rejected}  (duplicates: {res.duplicates})")
        print(f"Skipped (non-trade rows): {res.ignored}")
        for label, path in (("Exceptions", res.exceptions_path), ("Log", res.log_path),
                            ("Report", res.report_path)):
            if path:
                print(f"{label + ':':16} {path}")
        return 1 if res.rejected or res.file_errors else 0

    if a.cmd == "check":
        bad = 0
        for f in a.files:
            raw = read_file(f)
            raw = raw[~(raw["isin"].map(blank) & raw["size"].map(blank))]
            ok, rej = clean_frame(raw, ref)
            print(f"{Path(f).name}: {len(ok)} ok, {len(rej)} refused")
            for row in ok[ok["warnings"] != ""].itertuples():
                print(f"  row {row.source_row}: FIXED  {row.warnings}")
            for row in rej.itertuples():
                print(f"  row {row.source_row}: REFUSED {row.errors}")
            bad += len(rej)
        return 1 if bad else 0

    if a.cmd == "report":
        reg = load_register(ws.register_path)
        if not len(reg):
            print("Register is empty; run an import first.")
            return 1
        print(build_report(reg, ref, ws.output / "reoffer_report.xlsx"))
        return 0

    if a.cmd == "template":
        out = a.out or (ws.root / "reoffer_input_template.xlsx")
        print(build_template(out, ref))
        return 0


if __name__ == "__main__":
    sys.exit(main())
