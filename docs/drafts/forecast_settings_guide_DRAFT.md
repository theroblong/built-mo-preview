# Forecast settings guide (DRAFT v2, internal; not yet cleared for BUILT)

Written 2026-10-12 for business analysts, FP&A and accounting. Values verified against the code
(scout, 2026-10-12). v1 was skeptic-reviewed (opus/high) and rewritten to fix four cards that
stated the opposite of the evidence; v2 is the corrected version. This guide quotes **no absolute
accuracy figures** (`docs/ACCURACY_CLAIMS_REGISTER.md`). Test results appear as directions or
differences. **Older test** marks results from before the 2026-10-07 backtest fix (indicative only).
**Exploratory** marks results from only the 6 most recent forecast dates (no significance test).

## How to read this

Mo has two forecasting models. Both use the same machine-learning engine (LightGBM: thousands of
small decision trees, each correcting the errors of the ones before it) and the same 56 inputs.
They differ in how they reach weeks 2 to 13:

- **Recursive model:** predicts next week, feeds that prediction back in, repeats.
- **Direct model (what production serves today):** a separate model for each week ahead.

| Group | What it controls | Should BUILT adjust it? |
|---|---|---|
| A. How the model learns | The training engine | No. Tuned by Aevah; changes need a full re-test |
| B. How the forecast is shaped | Rules applied around the model | Some, as Aevah sliders with a measured effect |
| C. Which model, or mix of models | Model choice | Decided by the pre-registered rule; shown, not adjusted |
| D. What the forecast covers | Scope and definitions | No. Know them when reading numbers |

---

## A. How the model learns

### A1. Learning speed
- **What it does:** how big a correction each new tree may make. Smaller steps learn more
  carefully but need more trees.
- **Current:** recursive 0.04, direct 0.05.
- **What we found:** never tested on its own. An older tuning search (12 trials) included it but
  was paused.
- **Advice:** leave. A candidate for the planned tuning run, always paired with A2.
- Source: MO_26:220, mo_panel.py:75; MO_26D:75.

### A2. Maximum number of trees, and when to stop
- **What it does:** the model keeps adding trees until it stops improving on a held-back 13-week
  check period ("patience" = how many trees in a row may fail to improve), or hits the cap. For the
  recursive model, the check period scores **one-week-ahead** predictions made with actual recent
  sales, not the full 13-week forecast. So the stopping point is not tuned to 13-week accuracy.
- **Current:** recursive cap 6,000, patience 50; direct cap 3,000, patience 100.
- **What we found:** under the current cap, 10 of 18 test dates stopped at or just below 6,000.
  Raising the cap to 20,000 let 9 of the 18 train further, but forecasts barely moved (median change
  0.01%). The direct cap has never been tested.
- **Advice:** leave.
- Source: MO_26:212, :397; MO_26D:71-72. Evidence: MO_134 (README 235).

### A3. Tree size and sampling (complexity controls)
- **What it does:** how detailed each tree may be (up to 63 end points, at least 20 sales records
  per end point), how much each tree sees (a random 80% of inputs and of rows), and penalties that
  discourage over-fitting.
- **Current:** identical in both models.
- **What we found:** not tested since the backtest fix.
- **Advice:** leave. This is what the planned tuning run (Optuna) would search.
- Source: MO_26:221-228; MO_26D:75-77.

### A4. Random seed
- **What it does:** training has a random element (A3's sampling). The seed fixes it, so a run
  repeats exactly **on the same computer**. Different computers differ slightly even with the same
  seed, so every comparison uses one machine.
- **Current:** 42 in both.
- **What we found:** retraining the direct model with another seed moved item-level forecasts by a
  median of 10-11.5%. Averaging 5 seeds gave a small, consistent improvement.
- **Advice:** not a slider. Serve the average of several seeds rather than one.
- Source: MO_26:228; MO_26D:77. Evidence: README 232, 234.

### A5. Check period and final retraining
- **What it does:** the last 13 weeks are held back to decide when to stop adding trees; the model
  should then be retrained on everything, including those weeks.
- **Current:** the recursive model retrains on everything. **The direct model as served does not**
  (its training data ends at the start of its check period, 2026-06-07), so it never learned from
  the most recent quarter. It also counts "8 weeks ahead" as 8 rows of data, which lands on the
  wrong calendar week wherever an item has missing weeks. The "fixed direct" model corrects both.
- **What we found:** the fixed version (5 seeds averaged) scored better at item level in 2025, on
  the recent dates and overall.
- **Advice:** fix with the next model switch (C1).
- Source: MO_26:502-518; MO_26D:135-136, :144. Evidence: README 232-234.

### A6. Weight on recent weeks
- **What it does:** recent weeks count more in training. Each week's weight is
  e^(-0.02 x weeks ago): 26 weeks ago counts 59%, a year ago 35%, two years ago 12%.
- **Current:** 0.02 in both.
- **What we found (recursive model only):** 0, 0.01 and 0.04 all scored a little worse than 0.02
  (0.1-0.2 points at item level). Only 0.01 passed the significance test, which with no pattern
  across the values is most likely training noise. The direct model's value has never been varied.
- **Advice:** a possible slider ("how fast should the model forget?"), but with no measured benefit,
  there is no reason to move it today.
- Source: MO_26:371, :509 (hard-coded), mo_panel.py:73; MO_26D:70, :149-150. Evidence: MO_134.

### A7. Low, central and high forecasts
- **What it does:** each model produces three forecasts per item, per retailer, per week: a low
  (10th percentile), a central (50th) and a high (90th). The model learns on a log scale so large
  and small items are treated fairly.
- **Read with care:**
  - Ranges are per item, per week. **Adding up item highs does not give a portfolio high**; items
    rarely all run high at once.
  - New items (B5) get a fixed range of +/-45% around last week, not a learned one.
  - Lapsed items on the direct model get a range from zero to their full expected level.
- **Current:** the recursive model stretches its high forecast by a small factor (x1.0059). That
  factor was set in May 2026 on an older version of the model and should be re-derived at every
  retrain. The direct model has no stretch.
- **What we found:** how often the current models' actuals land above the high or below the low
  has **not been measured**.
- **Advice:** leave; measure range coverage before showing ranges to BUILT as "80% ranges".
- Source: MO_26:99, :323, :382; MO_26D:69, :153; MO_27:808-811; outputs/mo67_calibration_constants.json.

### A8. Inputs held at forecast-date values
- **What it does:** recent-sales trend inputs and store count (TDP) are kept at their forecast-date
  values for all 13 weeks. Price is held at the last observed price.
- **What we found:**
  - Letting the sales-trend inputs update each week (from the model's own predictions) made
    forecasts much worse, by about 12 points at item level (MO_118). Holding them is a deliberate
    brake.
  - Store count made little difference even when the test used the actual future store counts
    (older test; under 1 point).
- **Advice:** leave. Known changes in store count (expansion plans, new retailers) belong in
  planning inputs, not in this setting.
- Source: MO_27:647-657, :818, mo_panel.py:43, :53. Evidence: README 209, 222.

---

## B. How the forecast is shaped

### B1. Forecast length
- **What it does:** how many weeks ahead each forecast covers.
- **Current:** 13 weeks, both models.
- **Advice:** leave. Longer horizons need their own testing.
- Source: mo_panel.py:64; MO_26D:68.

### B2. Seasonal index (recursive model)
- **What it does:** both models see the week of the year as an input. In addition, for items
  **without** a usable same-week-last-year (B3), the recursive model nudges each week by the change
  in an average seasonal index from the week before ("week-over-week" form). Items with a usable
  year-ago week get their seasonality from B3 instead.
- **What we found:**
  - Earlier tests that favored this form used a seasonal index built with data from after the
    forecast date (a look-ahead).
  - When the index was rebuilt using only data available at each forecast date (older test,
    MO_127), the model with the seasonal step did **worse** than with it switched off: about 2
    points worse at item level and slightly worse at account level. At portfolio level it looked
    better in total, but only because errors in different item age groups cancelled; within each
    age group it was about the same or worse. Most of the item-level harm came from new items,
    where the index is now switched off (B5).
- **Advice:** under review. The evidence so far says the index step does not help. It stays in
  production until a dedicated test on the current setup decides.
- Source: MO_27:766-805, mo_panel.py:49. Evidence: README 220, 222, 229 (MO_113, MO_127).

### B3. Seasonal pull toward last year (recursive model)
- **What it does:** how much the forecast leans toward "the same week last year, scaled by this
  item's growth" instead of the model's own projection.
- **Current:** 10%.
- **What we found:** 0%, 5%, 10%, 20% and 30% were all close.
  - At **30%**, forecasts came out a little lower in 2025 (1-5%) and up to 3% higher in 2026.
  - Oct-Dec 2025 over-forecasting was smaller.
  - Week-by-week item forecasts were about 1 point worse (significant on the recent dates).
  - Monthly totals improved in 4 of 5 item age groups, but only on the 6 recent dates and not
    significantly. Over all 18 dates, monthly totals were slightly worse.
  - The group that got worse is established items (52+ weeks), the largest by volume, worse at
    every level and in every period.
  - An earlier statement that 30% "raises everything 3-8%" came from a different version (30% pull
    plus a per-store growth ratio) and is withdrawn.
- **Advice:** keep 10%. A slider is possible later, but today more pull has no proven benefit and
  hurts established items.
- Source: MO_27:68, mo_panel.py:66. Evidence: MO_134 (README 235), MO_135.

### B4. Growth cap for the seasonal pull (recursive model)
- **What it does:** the "growth" in B3 compares one recent week with the same week a year earlier
  (not year-to-date). That ratio is capped between half and double.
- **Current:** 0.5 to 2.0.
- **What we found:**
  - Removing the cap looked very harmful. Almost all the harm came from ~116 item-date combinations
    whose year-ago week was before the item was really in stores (a handful of units, so growth
    looked like 200x to 1,375x). The cap binds for 59% of items.
  - A version that also skipped the comparison when the item was in too few stores a year ago
    (and measured growth per store) removed most of that harm, with no overall accuracy change.
  - The "year ago" week is actually 51 weeks back (an off-by-one); fixing it made no difference.
- **Advice:** not a slider. Replacing the cap with the store-count rule needs one more test: the
  store-count rule alone, with no other change.
- Source: MO_27:570-574. Evidence: MO_134, MO_135 (both skeptic-reviewed).

### B5. New items (under 13 weeks of sales)
- **What it does:** the recursive model does not forecast items with under 13 weeks of history at a
  retailer. They get last week's sales carried forward, with a fixed +/-45% range. The direct model
  forecasts them like any other item.
- **What we found:**
  - Carrying the last value forward won in every age group and 3 of 4 test dates against the
    alternatives tried (older test, MO_79).
  - Over all 18 test dates (Dec 2024 to May 2026), this rule beat the 5-seed direct model on these
    items at every level. That lead comes from 2025: on the 6 recent dates the direct model was
    better at item and portfolio level and tied at account level. Date by date, the rule won 10 of
    18 and none of the 5 dates in 2026.
  - Adding the seasonal index to new items made them worse, because of a defect that inflated new
    items by 10-30%. It is switched off.
  - The +/-45% width has never been tested.
- **Advice:** under review. Keep for now; the recent dates favor letting the direct model forecast
  new items, which the next model decision (C1) would settle. The 13-week threshold is a possible
  slider once tested at other values.
- Source: MO_27:491, :533-541, mo_panel.py:67-68, :79-86; MO_26D:104-105. Evidence: MO_79, MO_129, MO_135.

### B6. Lapsed items (9 weeks without sales)
- **What it does:** after 9 weeks with no sales at a retailer, an item counts as lapsed. The
  recursive model forecasts zero. The direct model forecasts the chance it comes back times its
  expected level (in older data, 365 of 878 lapses resumed, at about 1.06x their old level).
- **What we found:** 9 weeks was chosen at a natural gap in the data (very few items go silent for
  5-8 weeks and come back). Other thresholds have not been tested.
- **Advice:** a possible slider ("how long before we stop expecting sales?") after a test.
- Source: mo_panel.py:65, :583-586, :674; MO_27:486-487; MO_27D:171-177. Evidence: README 201.

### B7. Safety cap on runaway forecasts
- **What it does:** caps any forecast at a multiple of the item's own best week.
- **Current:** none in production.
- **What we found:** an older test (4 dates) found a cap at 1.5x the item's highest week helped;
  1.5x was the tightest value tried. Since the fix, a 3x cap was tested only bundled with other
  changes.
- **Advice:** candidate guardrail; needs its own test.
- Source: MO_80:101, :864-868. Evidence: README 211, MO_134.

---

## C. Which model, or mix of models

### C1. Model choice and combination weight
- **What it does:** which model production serves, or how two models are averaged (for example 50%
  recursive + 50% fixed direct).
- **Current:** the direct model as served (with the A5 flaws).
- **What we found (exploratory, forecasts made December 2025 to May 2026):**
  - The fixed direct model (5 seeds averaged) is the only candidate ahead of the served model at
    account x month, but it won on only 4 of 6 dates; the rule needs 5.
  - The 50/50 combination beat last value carried forward on all 6 dates, but is slightly behind
    the served model at account x month.
  - The recursive model alone trails last value.
  - No candidate has passed the pre-registered rule (`docs/PRODUCTION_DECISION_PREREG.md`,
    Amendment 1). Saved forecasts become scorable when SPINS data reaches 2026-12-06.
- **Advice:** not a slider. Aevah shows which model is serving, why, and how it compares with L4W
  velocity x stores and last value carried forward.
- Evidence: MO_133, MO_134, MO_135.

---

## D. What the forecast covers

- **Units forecast:** SPINS base units (SPINS's modeled sales without promotions). Promotion lift is
  not in the base forecast. SPINS restates past weeks, by up to 35 weeks back.
- **Dollars:** forecast units x the last observed price, held flat.
- **Not covered:** item-retailer combinations that don't exist yet (new distribution). These are
  roughly 14% of a quarter's volume and need planning inputs.
- **Scope:** military accounts excluded; Alaska and Hawaii dropped; regional markets (RMA) used
  rather than the overlapping CRMA geographies.
- **Model age:** the served direct model's training data ends 2026-06-07.

---

## Slider shortlist (for Aevah)

| Slider | Default | Measured effect so far | Ready? |
|---|---|---|---|
| Seasonal pull (B3) | 10% | 30%: weekly detail worse; monthly totals better on recent dates only (not significant) | Not yet |
| Weight on recent weeks (A6) | 0.02 | Other values slightly worse (recursive) | Yes, but low value |
| New-item threshold (B5) | 13 weeks | Rule won in 2025, lost on 2026 dates; other thresholds not tested | Needs test |
| Lapse weeks (B6) | 9 weeks | Not tested | Needs test |
| Safety cap (B7) | none | Older test only | Needs test |
| Model choice / mix (C1) | served direct | Exploratory | Shown, not adjusted, until the rule decides |
