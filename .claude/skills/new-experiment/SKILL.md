---
name: new-experiment
description: Scaffold a new MO_NNN forecast experiment script that follows the test-plan protocol (harness parity, predictions recorded first, all three aggregation levels, history-band breakout). Use whenever creating a new scripts/MO_*.py that compares forecast arms, anchors, models, features or routing rules.
---

# New forecast experiment

Every forecast arm follows the Protocol in `docs/FORECAST_TEST_PLAN_V12.md`. Each rule exists
because skipping it once produced a wrong conclusion that later reversed. The
`protocol_gate.py` hook refuses to run an MO_127+ script that is missing any of these:
- the harness import
- PREDICTIONS
- a history-band breakout
- PRIOR WORK

Building them in from the start avoids a blocked run.

## Steps

1. **Number it.** Next free number: `ls scripts/MO_*.py | sed -E 's/.*MO_([0-9]+).*/\1/' | sort -n | tail -1`, plus 1.
   Also check the newest `## README update` for higher MO numbers. Results can land in
   the README before the script is pushed (MO_126 did), so take the higher of the two.
   Name: `scripts/MO_<N>_<snake_case_question>.py`. Output: `outputs/mo<N>_<slug>.json`.

2. **Write the docstring before any code**, in this order:
   - `MO_<N> - <the question, phrased as a question>`
   - WHERE THIS CAME FROM: which prior MO result or client input motivated it
   - PRIOR WORK: first ask the `scout` agent what `docs/SETTLED_FINDINGS.md` and the
     README already say about this question. Cite each related entry by MO number, with
     its status:
     - **SETTLED:** explain why re-testing is justified.
     - **PROVISIONAL:** say which reopen-if condition this experiment meets.
     - **Nothing related:** write `none found`.
   - ARMS: one line each. Name the production arm explicitly as the reference.
   - LEVELS: cell x week · account x month · portfolio x month, plus bias at portfolio x month
   - `PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:` numbered, each one
     falsifiable, plus what it would mean if a prediction fails.

3. **Use the shared harness. Never rebuild it.** Importing MO_80 runs
   `assert_forecast_parity()` against `mo_panel.FORECAST_CONTRACT`:
   ```python
   import MO_80_quarterly_honest_backtest as M
   importlib.reload(M)
   assert M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
   ```
   Set any `MO_*` environment variables *before* the import. Take series keys from `M.GROUP_COLS`
   and categoricals from `mo_panel.CAT_COLS`. Do not retype them.

4. **History bands.** Use exactly these, so results are comparable across scripts:
   ```python
   BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]
   ```
   Print and save a **BY HISTORY BAND** table for every arm at every level.

5. **Score bottom-up** so the three levels reconcile. Report wMAPE per arm per level per
   band, and bias at portfolio x month. Never draw a conclusion from a pooled mean alone.

6. **Close the loop in the output.** After the run, print each prediction with HOLDS or FAILS.
   An unexplained behaviour (e.g. the model losing on 52+ wk series) is reported as a
   blocker, not footnoted.

7. **Record it.** Add the result to the README as the next `## README update N` entry
   (finding · table by band · procedural lesson), and add decisions and open questions to
   `agents/project_memory.md` in the same commit. The commit hook requires the memory file.

A script that is not a forecast arm (data audit, plot, ingest check) is exempt. Mark it
with the line `# protocol: not-a-forecast-arm` so the exemption is visible in review.

Reference implementations: `scripts/MO_122_naive_vs_model_by_segment.py` (predictions),
`scripts/MO_123_anchor_window_by_history.py` (bands, harness import).
