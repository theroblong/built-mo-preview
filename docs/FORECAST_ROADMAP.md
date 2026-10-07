# Forecast improvement roadmap

Approved by Jason on 2026-10-07 and revised the same day. It sits alongside the protocol in
`docs/FORECAST_TEST_PLAN_V12.md`, which still governs every experiment: harness parity,
predictions first, all three levels, history bands, PRIOR WORK and a skeptic review.
Evidence: MO_127 and MO_128, plus the skeptic reviews (live notes in
`agents/project_memory.md`, 2026-10-07).

**Guiding principle (Jason):** the model learns seasonal turns and growth from existing and
future data. No forced patches, no arbitrary ceilings, no stopping training short.

## Step 1. Fix the yardstick
- **Cutoff weekday.** Q3 2026 is `2026-06-29`, a Monday, in `MO_80:206`. Change it to
  `2026-06-28`. All SPINS weeks end on Sunday. Add an assertion that every cutoff is a
  panel week. This is Rob's harness, so it needs his OK.
- **More origins.** Use about 20 monthly rolling origins instead of 7 quarterly cutoffs.
  At portfolio × month, n=9–21 is noise.
- **New series.** Score them too, so "portfolio" means the planning total.
- **History length.** Count it as calendar span with real distribution (e.g. TDP > 1),
  not row count. Today the Walmart PUFF 1.41oz relaunches are labelled 52+.
- **Fitted inputs.** Rebuild every one from data up to each cutoff (index, scalers,
  anchors).
- **Noise floor.** Run the same configuration across seeds and origins. A change smaller
  than the noise is not a result.

## Step 2. Fair training
These caps become learned or tuned:

| Today | Becomes |
|---|---|
| `n_estimators` cap of 800 | A very high cap (e.g. 20,000). Early stopping uses patience scaled to the learning rate, on a time-based validation block (the last 13 weeks before the cutoff). Then refit on all data with the best iteration. |
| `va = tr.tail()` (`MO_80:365`), which takes the last series rather than the latest weeks | A time-based split. Check `MO_26` too. |
| yoy_ratio clip 0.5–2.0 (`MO_27:571`) | Removed. Growth is handled by the target (Step 3). |
| `SEASONAL_BLEND_WEIGHT` 0.10 | Learned, or tuned |
| `RECENCY_LAMBDA` 0.02, `MIN_SERIES_WEEKS` 13, `LAPSE_WEEKS` 9 | Tuned on the backtest |
| `hist[n-52]` year-ago, which is misaligned for series with gaps | A calendar-aligned year-ago lookup |

Keep one loose, logged safety rail: a forecast of at most 3× the series maximum.

## Step 3. MO_129: Connor's anchor, plus learned corrections and seasonality
- **Target.** Each future week relative to a trailing anchor: Base U/S/W (L4W) × current
  doors. The alternative is a velocity × doors target with retransformation-bias
  correction (blocker 0.2).
- **Seasonality is learned, pooled across all series.** Features: anchor week-of-year,
  target week-of-year, horizon, channel, pack, brand, doors, promo and price. Each year of
  new data adds more turns. Leaf regularization shrinks thin groups toward the pooled
  pattern. This replaces the separate STL index (the old Step 4).
- **Forecast form.** Direct multi-horizon, not recursive (MO_103).
- **BAR weight.** BAR rows get a tunable sample weight, not a hard exclusion.
- **Comparison.** Against L4W, L12W, flat and the shipped model: all three levels, by
  band, by quarter, with turn quarters (Q1, Q4) reported separately.

## Step 4. Structure first, then Optuna on the winner
1. Settle the big structural choices with a small factorial at default settings. These are
   the target, anchor window, direct vs recursive and training window.
2. Run Optuna (TPE) on the winning structure.
   - **Objective:** the honest rolling-origin 13-week error at account × month and item ×
     week. Not one-step CV (MO_28).
   - **Search space:**
     - learning_rate 0.01–0.1, with trees set by early stopping
     - num_leaves 15–255, min_child_samples 10–500
     - feature/bagging fraction 0.5–1.0, lambda L1/L2 0.001–10
     - early-stopping patience
     - objective (quantile / l2 / tweedie)
     - training window, recency weight, BAR weight
3. Prune: score each trial on 3–4 origins first, and run all origins only for promising
   trials.
4. Confirm on held-out origins that tuning never saw. Tune on origins through Q1 2026,
   then confirm on Q2–Q3 2026.
5. Use Optuna parameter importance to freeze the settings that don't matter.
6. For the final model, lower the learning rate and let early stopping choose the trees.

## Step 5. Compute (RunPod)
- **Now.** Run Optuna trials and multi-origin backtests in parallel workers with shared
  Optuna storage. CPU cores matter most for LightGBM at this size.
- **After Step 3/4.** Run one bounded deep-model challenger on the same harness: TFT,
  DeepAR or N-HiTS, or a Chronos-2 fine-tune, with doors as a known covariate. Expect
  modest gains (about 1,500 PUFF series, under 3 years).

## Shipping option, after Step 1 confirms it
Connor-style velocity × doors (L4W) for established items, last value for new items, and no
STL seasonal. ML enters as the corrections layer when it beats that layer honestly.
