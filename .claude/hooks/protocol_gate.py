#!/usr/bin/env python3
"""PreToolUse(Bash) gate: refuse to run a new experiment script that skips the protocol.

The protocol lives in docs/FORECAST_TEST_PLAN_V12.md ("Protocol -- applies to every arm,
no exceptions"). This enforces the parts a file check can see:

  1. Harness parity -- the script imports MO_80 / MO_27 / mo_panel, whose import runs
     assert_forecast_parity(). A script that rebuilds the harness itself is how the
     11.83pp MO_118 divergence happened.
  2. Predictions recorded before running -- the module docstring has a PREDICTIONS
     section, so the result can falsify it.
  3. History-band breakout -- the script mentions history bands. Two conclusions have
     reversed under the band breakdown; a pooled-only script is not allowed to run.

Applies only to MO_127 and later (MO_126 already ran, per README 227), so the existing scripts keep running unchanged.
A script that is not a forecast arm (data audit, plotting) opts out explicitly with
the line `# protocol: not-a-forecast-arm`, which makes the exemption visible in review.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

FIRST_ENFORCED = 127

payload = json.load(sys.stdin)
cmd = payload.get("tool_input", {}).get("command", "")
if "python" not in cmd:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
problems: list[str] = []

for m in re.finditer(r"(MO_(\d+)[A-Za-z0-9_]*\.py)", cmd):
    name, num = m.group(1), int(m.group(2))
    if num < FIRST_ENFORCED:
        continue
    path = root / "scripts" / name
    if not path.exists():
        continue
    src = path.read_text(encoding="utf-8", errors="replace")
    if "# protocol: not-a-forecast-arm" in src:
        continue
    try:
        doc = ast.get_docstring(ast.parse(src)) or ""
    except SyntaxError:
        doc = ""

    missing = []
    if not re.search(r"\b(MO_80_quarterly_honest_backtest|MO_27_retailer_sales_forecast|mo_panel)\b", src):
        missing.append("harness parity: import MO_80 / MO_27 / mo_panel (their import asserts forecast parity)")
    if not re.search(r"PREDICTION", doc, re.IGNORECASE):
        missing.append("a PREDICTIONS section in the module docstring, written before the run")
    if not re.search(r"history[ _-]?band", src, re.IGNORECASE):
        missing.append("a breakout by history band (<13 / 13-25 / 26-51 / 52+ wks)")
    if missing:
        problems.append(f"{name}:\n  - " + "\n  - ".join(missing))

if problems:
    reason = (
        "Run blocked by the experiment protocol (docs/FORECAST_TEST_PLAN_V12.md).\n"
        + "\n".join(problems)
        + "\nFix the script (the new-experiment skill has the template), or if it is not a "
        "forecast arm add the line `# protocol: not-a-forecast-arm`."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
sys.exit(0)
