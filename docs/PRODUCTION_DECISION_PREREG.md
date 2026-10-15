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

## Amendment 1 (2026-10-10, Jason; written before any forward week is scored)

Jason: "Since our forecast accuracy matters most for 2026 and 2027 ... I do favor the model that
is consistently accurate but being accurate for 2026 and 2027 is probably most important to
BUILT's business. They want to see that our model would have worked for 2025 (understanding that
PUFF history was very limited), but they really want to know how well it will work and improve
going forward." Why: before late 2025 no item had two years of history and BAR was still being
replaced by PUFF, so 2025 forecast dates describe a different business. This amendment replaces the
rule above for all future decisions; it is written before any saved forecast has been scored.

**Evidence, in order of weight**
1. Forward weeks: forecasts saved before their outcomes existed (`forecasts_registered/`).
2. Recent backtest: forecast dates 2025-12 onward (the first dates with two years of history),
   extended as new dates become scorable.
3. 2025 forecast dates: a "would it have worked" check only (no-harm), not a ranking.

**Replace the status quo X with candidate Y only if ALL hold**
1. **Recent accuracy:** on the recent forecast dates, Y is better than X at account x month and at
   portfolio x month scored within history bands, and not worse at item x week (point estimates;
   with 6 overlapping dates, intervals are reported but not required to exclude 0).
2. **Consistency (Jason's priority):** Y beats X at account x month on at least 5 of 6 recent
   forecast dates (or the same share as more dates arrive).
3. **2025 no-harm:** on 2025 dates, Y is not worse than X by more than 2 points at account x month.
4. **Seasonal turns:** per calendar year, |bias - 1| <= 0.10 or no worse than X's.
5. **Forward confirmation:** once at least 3 saved forecast dates are scored on real weeks, Y is
   not worse than X on them; if it is, the switch waits.
6. **Tie-break:** between candidates that pass, prefer the more consistent (more per-date wins),
   then the simpler.

**Added 2026-10-12, before MO_136 results exist:** the fixed direct model with 5 seeds averaged plus the MO_136 signals (category/competitor, other-retailer, 26-week history), code `all_avg5`; and any single MO_136 signal group that beats its 2-seed baseline, re-run with 5 seeds before it can be compared under this rule.

**Added 2026-10-12, before MO_137 results exist:** the fixed direct model with 5 seeds averaged plus the MO_137 expansion-fade signals, code `fade_avg5`. Results are also reported without Walmart (description only; the rule itself is unchanged).

**Added 2026-10-12, before MO_138 results exist:** the fixed direct model with 5 seeds averaged, multiplied by item-age x weeks-ahead correction factors learned only from earlier forecasts (MO_138), code `cal`.

**Added 2026-10-12, before MO_139 results exist:** the fixed direct model with 5 seeds and Duan smearing by item age and weeks ahead (`smear_avg5`), and the same model trained with a Tweedie objective on raw units (`tweedie_avg5`) (MO_139, fixing the log-scale bias).

**Forward set for the next saved forecast (2026-10-12, Jason):** save `direct_avg5` (fixed direct, 5 seeds), `rec_dir5` (recursive + fixed direct) and `tweedie_avg5` (fixed direct trained on raw units with a Tweedie objective, 5 seeds; better than direct_avg5 on 2025 dates, worse on recent dates in MO_139) alongside the served model, L4W velocity x stores and last value, so forward weeks can separate them.

**Added 2026-10-13, before MO_140 results exist:** the fixed direct model with 5 seeds plus fixed product attributes (product line, nutrition, price per bar, exclusivity), code `attr_avg5`.

**Added 2026-10-13, before MO_146 results exist:** neural global models trained on all series at each forecast date (neuralforecast, 13-week horizon, 5 seeds averaged each): N-HiTS (`nhits5`), TCN (`tcn5`), TFT (`tft5`); their average (`neural_avg`); and a 50/50 blend of the fixed direct model and the neural average (`dir_neural`). Results are also reported without Walmart (description only; the rule itself is unchanged).

## Amendment 2 (2026-10-14, Jason; written before MO_147 results exist)

Added to the Amendment 1 rule, after MO_146 showed a pooled within-band score hiding losses in established bands
(the young-item band's gain masked worse portfolio months for items with 13+ weeks of history):
7. **No established band worse:** on the recent forecast dates, Y is not worse than X at portfolio x month within
   each established history band (13-25, 26-51 and 52+ weeks), scored separately; a gain in the under-13-week band
   cannot offset a loss in any of them.

**Added 2026-10-14, before MO_147 results exist:** 50/50 blends of the fixed direct model (`direct_avg5`) with
L4W velocity x stores (`dir_l4w`), with L12W (`dir_l12w`), and with last value carried forward for series under
15 weeks of history only (`dir_flat15`); the neural-only blend (neural average only where a neural forecast exists,
`dir_neural_only`); and `dir_neural` as written in MO_146.

**Added 2026-10-14, before MO_148 / MO_149 results exist:** one fixed direct model per product line (BAR, PUFF,
SOUR PUFF), 5 seeds averaged (`line_avg5`); one fixed direct model trained without BAR history for PUFF and SOUR
PUFF items, BAR items on the production model (`nobar_avg5`); the fixed direct model with L4W and L12W velocity x
stores as inputs, 5 seeds averaged (`l4wf_avg5`). All judged under Amendment 1 + 2.

**Added 2026-10-15, before MO_155 results exist:** the fixed direct model with the five promotion-history inputs
computed as of each training week instead of once per forecast date (`asof_avg5`, 5 seeds; MO_155). It is a correctness
fix: MO_155's own decision rule decides whether the as-of construction is used for tuning and the December retrain; any
switch of the served model still follows Amendment 1 + 2.

**Added 2026-10-15, before any MO_154 result exists (Optuna):** the fixed direct model (MO_132 run_direct, refit,
calendar targets) tuned by Optuna (TPE, MedianPruner) over learning_rate [0.02, 0.10], num_leaves [15, 255],
min_child_samples [5, 200], feature_fraction and bagging_fraction [0.5, 1.0], reg_alpha and reg_lambda [0.001, 10],
recency weight [0, 0.05], and three calendar-only inputs for the target week (month; Thanksgiving/Christmas/New Year
week; ISO weeks 1-4), each on or off. Objective: account x month miss % on the tuning dates plus 50 x the excess of
|bias - 1| beyond 0.10 for each Jan-Mar and Oct-Dec window. Study A tunes on the first 15 forecast dates and keeps
2026-03/04/05 out of tuning; Study B tunes on all 18. Promotion statistics as of each week if MO_155 adopts them. The
top settings of each study are re-run with 5 seeds as `tuned_a_avg5` and `tuned_b_avg5` and judged under Amendment 1 +
2; Study A must also not be worse than direct_avg5 by more than 0.3 at account x month on the held-out dates.

**Amended 2026-10-15 (Jason approved the staged plan; written before any MO_154 tuning result exists; the only runs so
far are a laptop smoke test of two trials, used for timing):** Study B is dropped. One honest study replaces Study A, in
three stages. Search space, objective (account x month miss + 50 x seasonal-bias excess), calendar options and the
honest harness are unchanged. Promotion statistics per forecast date (`--promo-asof 0`; MO_155 did not adopt the
as-of version). MO_156 macro inputs are not in the search. Tuning dates = the first 15 forecast dates (2024-12 ..
2026-02); 2026-03/04/05 stay held out and are never used to choose anything.
1. **Stage 1, broad search (6 dates):** 2024-12, 2025-03, 2025-06, 2025-09, 2025-12, 2026-02 (covers both Jan-Mar
   windows and the Oct-Dec window). About 120 trials, run as 3 independent TPE searches (sampler seeds 1, 2, 3) of
   about 40 trials each; each search's first trial is the production settings (parity check, P1).
2. **Stage 2, refine (15 dates):** the 10 best distinct Stage 1 settings by objective, plus the production settings,
   are re-scored on all 15 tuning dates (seed 42). Then about 30 new TPE trials on the 15 dates, run as 2-3 searches
   that start from the re-scored trials as history (no re-computation); pruning after the first batch of 6 dates.
3. **Stage 3, final check (18 dates, 5 seeds):** the 3 best Stage 2 settings by 15-date objective, each with seeds 42,
   1, 2, 3, 4 on all 18 dates. The winner `tuned_avg5` is the one with the lowest 5-seed objective **on the 15 tuning
   dates only**. Only then is it scored on the held-out 2026-03/04/05 dates (P3) and judged by Amendment 1 + 2 against
   `direct_avg5`.
- **Decision:** the December retrain uses the `tuned_avg5` settings only if P3 holds and it passes Amendment 1 + 2;
  otherwise the production settings stay.
- **Budget:** at most $50 compute in total (Jason, 2026-10-15), with the balance checked (compute_budget) before each
  stage. If measured trial times run long, trial counts are cut to stay in budget; they are never raised without Jason.
- **Predictions (replacing MO_154 P2 and P5; P1, P3 and P4 unchanged):** P2 the best Stage 2 setting beats the
  production settings' 15-date objective by at least 0.5. P5 the Stage 1 screen is informative: across the 10
  re-scored settings, the rank correlation between their 6-date and 15-date objectives is at least 0.5.

**Named candidates (before their forward results exist):** fixed direct model with 5 seeds averaged
(`direct_avg5`), recursive + fixed direct (`rec_dir5`), served direct (status quo), recursive,
L4W velocity x stores, last week carried forward. The Sept 6 save holds a single-seed fixed direct
(`direct_fixed`) and its recursive combination (`rec_dirfix`); the next save adds the 5-seed versions.

## Explainability requirement
Whatever production serves, Aevah shows which model it is, why it was chosen (this rule and
the scores), and how it compares with L4W velocity × stores and last week carried forward.
