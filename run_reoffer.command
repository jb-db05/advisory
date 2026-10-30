#!/bin/bash
# Double-click on macOS: imports workspace/inbox and rebuilds the reports.
cd "$(dirname "$0")"
python3 -m reoffer run
open workspace/output
