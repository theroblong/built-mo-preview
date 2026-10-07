# Forecast v12 — structured test plan

**Written 2026-10-07.** Supersedes the "replace the recursive loop" framing in
`FORECAST_V12_IMPLEMENTATION_PLAN.md`, which was based on a pooled comparison that the
band breakdown has since refined.

**Purpose.** Fully test two things before changing production: **source_brand
stratification** and **integration of the trailing-velocity estimator (`conn_L4W`)**.

---

## Why a plan rather than more experiments

2026-10-06 produced thirteen scripts and three reversals. Two were caused by the backtest
harness having silently diverged from production; one by scoring a candidate only at the
item-week level. The design below is shaped to make those failure modes impossible rather
than to catch them afterwards.

### Protocol — applies to every arm, no exceptions

1. **Harness parity is asserted, not assumed.** Every run imports
   `mo_panel.FORECAST_CONTRACT` / `PER_STEP_DYNAMIC` and calls `assert_forecast_parity()`.
2. **Every arm is scored at all three levels** — item x week, account x month,
   portfolio x month — plus bias at portfolio x month. A candidate measured only at
   item-week understated its value sevenfold on 2026-10-06 (the anchor seasonal form:
   1.17pp at item-week, 8.28pp at portfolio-month).
3. **Every arm is broken out by history band** (<13 / 13-25 / 26-51 / 52+ weeks). The
   pooled number hid that `conn_L4W` loses by 7pp on new items and wins by 12.5pp on
   established ones.
4. **Predictions are recorded in the script docstring before it runs**, so a result can
   falsify them.
5. **No conclusion from a single pooled mean.** Quarterly breakdown required; the
   portfolio-month mean rests on 21 observations.
6. **An unexplained behaviour blocks shipping**, even a favourable one.

---

## Phase 0 — blockers (must resolve before Phases 1-3 are interpretable)

| # | item | why it blocks |
|---|---|---|
| 0.1 | **Oracle-doors reversal.** Perfect future distribution helps at item-week (25.2 vs 33.4) and *hurts* at portfolio-month (19.2 vs 17.5). | Same family as the estimator being shipped. If distribution handling behaves unpredictably across levels, every `conn_L4W` result is suspect. |
| 0.2 | **Retransformation bias.** MO_117's velocity models ran at bias 0.62-0.65 vs single-stage 0.886, because the median of `log1p(velocity)` x doors does not reconstruct the mean of units. | Any arm that *forecasts* velocity rather than averaging it inherits this. Fix (Duan smearing or a tweedie objective) before Phase 3's model-based velocity arms. |
| 0.3 | **Why is the model worse than flat on 52+ week series?** 34.7 vs 29.9 at item-week, on the cohort with the most history and a usable `lag52`. | If the model is actively harmful where it should be strongest, stratification may be treating a symptom. |

---

## Phase 1 — source_brand stratification, full factorial

**Hypothesis to test:** brand matters as a *stratifier* (measured −1.14pp, all 7 quarters)
rather than as a feature (ranks 54/56 on both gain and true SHAP).

### Dimensions

| dimension | levels |
|---|---|
| **granularity** | pooled · exclude-BAR-only · per `source_brand` (3) · per Connor `Majority Type` (5: Puff, Sour Puff, Chunk Puff, Bar, Duos Puff) |
| **what is stratified** | training set only · + seasonal index · + velocity window |
| **minimum rows guard** | 500 / 2,000 / 5,000 — below the guard, fall back to pooled |

### Constraints, stated up front
- SOUR PUFF has **927 training rows**; Chunk Puff **12 items**, Duos Puff **9**. Finer
  granularity will hit the guard, and that is itself a result.
- `Majority Type` comes from Connor's `Item_Assumptions` tab and is finer than our
  `source_brand`. Join on **`Majority Type`, never the item-code prefix** — `BRB0229` is a
  Puff (3 such cases).
- **Prefer exclusion to stratification** where the measurement is close: three model
  artifacts to version and keep in lockstep is the failure surface that cost 2026-10-06.

### Stop rule
If exclude-BAR-only captures ≥80% of the best stratified arm's gain, stop and ship
exclusion. Do not build per-brand artifacts for the remainder.

---

## Phase 2 — the velocity estimator, integration modes

**`conn_L4W` = `sum(base_units[-W:]) / sum(tdp[-W:]) x tdp_last x seasonal_mult`**
(= SPINS "Base U/S/W", the anchor Connor's workbook uses, verified from its formulas.)

### Four integration modes — this is the central question

| mode | description | status |
|---|---|---|
| **A. replacement** | velocity anchor for all series | measured; **refuted by band breakdown** (loses 7pp on <13wk) |
| **B. router by history band** | last-value <13wk, velocity 26+, boundary to be swept | **the leading candidate** |
| **C. fixed blend** | `w * model + (1-w) * velocity` | measured pooled; wins portfolio by 0.47pp on n=21, loses at finer levels. Re-test **per band** — a blend may win where the router boundary is ambiguous (13-25wk). |
| **D. as a FEATURE** | feed `velocity_4wk` and `tdp_last` to the model instead of blending outputs | **UNTESTED and the most natural answer to "make the model better"**. Note `velocity_per_tdp` already exists as a feature at rank 12, but is computed with current-week units and frozen at inference — a properly lagged, correctly-anchored version is a different thing. |

### Sub-dimensions
- **window**: 4 / 8 / 12 / 26 / 52 weeks, and whether the optimum varies by band
  (L12W scores 17.5 at portfolio-month, worse than flat's 16.0 — only the short window
  works pooled, but this has not been swept per band)
- **doors**: flat · damped trend · model-projected · oracle (ceiling only, not shippable)
- **seasonal**: on / off. Worth **5.72pp** on the velocity anchor against ~1pp on the
  trained model — seasonality matters far more once the level is anchored correctly.

### Stop rule
If mode D (as a feature) matches mode B (router) within 0.5pp at all three levels, prefer
D: one estimator, one artifact, and it keeps improving with training.

---

## Phase 3 — combined, and the continuous-learning question

1. Best Phase 1 arm x best Phase 2 arm, measured together. **Candidates measured alone
   have twice behaved differently in combination.**
2. **Learning-curve test.** Re-run the best arms on truncated history (1 year, 18 months,
   2 years, all) and plot the model-versus-anchor gap against history length. This
   directly tests whether the model is handicapped by *current* data rather than
   permanently — the panel is dominated by ramping PUFF and dying BAR, and PUFF is
   accumulating the history BAR used to have. **A fixed formula cannot benefit from that;
   a trained model can.** If the gap narrows with history, the model's forecasting role
   should be preserved regardless of today's standings.

---

## Phase 4 — validation gates before any production change

1. Quarterly breakdown, not the 21-observation portfolio-month mean
2. **Bracken chart regenerated from MO_27's local parquet**, with **Q1 2026 inspected
   specifically** — that quarter is where a forecast sloping down against a January that
   ramps in every observed year was caught, and it is the sharpest reality test available
3. Coherence re-verified: item forecasts sum to account and portfolio totals
4. All Phase 0 blockers closed
5. MO_27 and MO_80 changed in the **same commit**, parity asserted at import

---

## What is NOT in scope

- Replacing the trained model. It remains the source of **cannibalization rates, price
  elasticity, SHAP explainability and scenario analysis**, none of which a trailing
  velocity provides, and all of which feed other Mo screens.
- Chain-linking BAR history onto PUFF (43 of 75 pairs would gain a year) — separate track.
- GPU work (TFT, N-HiTS). Worth noting those now compete against a much stronger baseline
  than they would have on 2026-10-05, which makes that a more honest test.

## Known result this plan supersedes

The band breakdown inverts the pooled conclusion: `conn_L4W` loses by **7pp on <13-week
series** and wins by **12.5pp on 52+ week series**. A velocity estimate needs a stable
denominator; for a four-week-old item `sum(tdp[-4:])` is small and noisy. Any plan built
on the pooled number alone would have shipped the estimator into the cohort it is worst at.
