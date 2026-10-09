# Pre-registered rule: which forecast model should production serve?

**Written 2026-10-09, before the remaining tests (MO_134 fair settings, neural models,
tuning).** Jason: "evaluate all tests first. My hunch is to go back to recursive but I want to
take a scientific approach to validate that decision too." Production keeps serving the
current model until this rule picks a replacement.

## Candidates
| Name (plain) | Code | Notes |
|---|---|---|
| **Current production (status quo)** | direct model as served (MO_26D/MO_27D v11d) | Known training defects (no retraining on the last 13 weeks; row-based targets) |
| Recursive model | MO_26/MO_27 | Jason's hunch |
| Direct model, fixed, 5 seeds averaged | MO_133 `direct_avg5` | |
| Recursive + fixed direct (50/50) | MO_133 `rec_dir5` | Best combination so far |
| L4W velocity × stores | `conn_L4W` | The current planning method, as a reference and fallback |
| Any later challenger | MO_134+, neural, tuned | Must be named here before its results exist |

## Evidence, in order of weight
1. **Forward weeks** (strongest): forecasts saved before the outcomes existed
   (`forecasts_registered/`, first scorable when SPINS reaches 2026-12-06). Saved so far:
   served direct, recursive, flat, L4W, MO_130, blend, fixed direct, recursive + fixed direct.
2. **The honest backtest** (all 18 monthly forecast dates, Dec 2024 to May 2026, one
   machine per comparison, skeptic-checked).

Backtest results already known when this rule was written (MO_132/MO_133) are listed in
README updates 231 to 233; the rule is written for what comes next and does not get to
reinterpret them.

## Rule: replace the status quo X with candidate Y only if ALL hold on the backtest
1. **Item level:** Y beats X at item × week with a 95% margin of error excluding 0.
2. **No planning-level harm:** Y is not significantly worse than X at account × month or at
   portfolio × month, with portfolio × month **scored within history bands** (so errors in
   one band cannot cancel another).
3. **Established items:** on items with 13+ weeks of history, Y is not worse than X by more
   than 0.5 points at item × week.
4. **Seasonal turns:** for each calendar year, Y's Jan–Mar and Oct–Dec bias satisfies
   |bias − 1| ≤ 0.10, or is no worse than X's.
5. **Robustness:** the item-level win holds without the three winter forecast dates
   (2025-11, 2025-12, 2026-01) and without the single largest account.
6. **Tie-break:** when two candidates both pass and differ by less than their margin of error,
   prefer the simpler one (one model over a combination; fewer settings), per Jason.

## Then confirm forward
After the switch, the forward tracker keeps scoring the new model against the old one and
the challengers on every new SPINS week. If the forward results reverse the decision beyond
the margin of error (once at least 3 forward cutoffs are scored), the switch is reviewed.
No fixed calendar window (Jason: "use all of the data").

## Explainability requirement
Whatever production serves, Aevah shows which model it is, why it was chosen (this rule and
the scores), and how it compares with L4W velocity × stores and last week carried forward.
