# Forecast v12 implementation plan — ship the velocity anchor

**Status:** plan, not shipped. Written 2026-10-07 off the 2026-10-06 measurement run.
**Audience:** Rob, and whoever picks this up next.

---

## The change in one line

Replace the recursive LightGBM loop as the primary forecast with a **trailing four-week
velocity times current distribution**, seasonally adjusted. Keep the model for what it
uniquely provides.

```python
velocity_4wk = sum(base_units[-4:]) / sum(tdp[-4:])    # = SPINS "Base U/S/W"
forecast     = velocity_4wk * tdp_last * seasonal_mult
```

No trees, no 56 features, no recursion, no training, for the base forecast.

## Why — measured, seven honest quarters, production-parity harness

| level | production today | `conn_L4W` | |
|---|---|---|---|
| item x retailer x week | 37.90 | **28.38** | −9.5 |
| account x month | 27.80 | **17.72** | −10.1 |
| **portfolio x month** | **20.07** | **10.71** | **−9.4** |

Portfolio-month bias moves from **0.920 to 1.029** — a systematic 8% under-forecast
becomes a 3% over-forecast. The mechanism: dividing by trailing distribution and
multiplying by *current* distribution captures door growth that an average of raw units
structurally misses, because the latest distribution level exceeds the window average
whenever an item is gaining placement.

It is also the first method measured all day to beat a flat carry-forward at the item-week
level (28.38 vs 32.8), which an earlier test that day had concluded was unbeatable.

### Where it came from

Rob's observation that the BAR-to-PUFF relation "feels like the sort of thing that's wired
into the excel book" -> reading Connor's `Retail_Build` formulas rather than cached values
-> finding his anchor is SPINS column R, "Base U/S/W" -> testing his architecture with his
own definition. None of it came from our modelling work.

### Why not a blend

A 25/75 blend of the model and the velocity anchor was tested. It wins portfolio-month by
0.47pp — on **21 observations** — and loses at item-week and account-month. `conn_L4W`
wins two of three levels outright. A blend also means maintaining both systems in lockstep,
which is precisely the failure mode that cost a day: three-way harness disagreement with
52.6% of model gain behaving differently in three places. Not worth 0.47pp.

### Why not Connor's own window

His default is twelve weeks (`Method` = L12W on all 3,472 rows), which scores **17.5 at
portfolio-month — worse than carrying last period forward (16.0)**. Twenty-four weeks is
24.6. Only the short window works. He has the right architecture with the wrong parameter.

---

## Steps

### 1. Velocity estimator in MO_27
New function, per series: `velocity_4wk * tdp_last * seasonal_mult`.
- `tdp` forward-filled; floor the denominator (`sum(tdp) > 0.05`) so a near-zero
  denominator cannot explode.
- Falls back to last observed value where velocity is undefined.
- Becomes the primary forecast path. The recursive loop is **demoted, not deleted**.

### 2. Prediction intervals — DECIDE BEFORE THE CHART
`conn_L4W` has no q10/q90; those came from the quantile models. Two options:
- **(a)** empirical residual quantiles by history band, taken from the backtest. More
  principled, new machinery, changes the schema's meaning.
- **(b)** keep the quantile models solely to derive a band *width*, applied around the
  velocity point estimate. Less principled, preserves the existing Druid schema and the
  chart's band.
Recommend (b) to ship, (a) as follow-up. **The band is visible on the Bracken chart, so
this cannot be deferred past step 6.**

### 3. What survives of the LightGBM model
Keep it for what a velocity anchor cannot do: **cannibalization rates, price elasticity,
SHAP explainability, scenario analysis.** These feed other Mo screens and are not replaced.
This is a demotion of the model's forecasting role, not a deletion of the model.

### 4. Seasonal mode — already patched
`anchor` form (`index(target)/index(anchor)`) is in MO_27 and MO_80. Worth **8.28pp at
portfolio-month** — the single largest item in the stack. Note this is far larger than the
1.17pp measured at item-week, because systematic bias compounds in aggregate rather than
cancelling. Keep.

### 5. BAR exclusion — deprioritised
Worth 0.54pp at portfolio-month *while the LightGBM path produces the forecast*. With
`conn_L4W` shipping it becomes irrelevant to the forecast and relevant only to the
cannibalization and elasticity models.

### 6. MO_80 parity
The backtest must use the identical estimator, declared through
`mo_panel.FORECAST_CONTRACT` / `PER_STEP_DYNAMIC` so the two cannot drift. This is the
guard's first real use.

### 7. Bracken chart
Regenerate from MO_27's local parquet (`MO_FORECAST_SOURCE=local`) so it can be reviewed
before anything reaches Druid.

---

## Validation gates — none of this ships without them

1. **Quarterly breakdown**, not the 21-observation portfolio-month mean.
2. **Q1 2026 inspected specifically** on the chart. That quarter is where the down-slope
   against a January that ramps every observed year was caught, and it is the sharpest
   available test of whether a change is real or arithmetic.
3. **Coherence re-verified** — item forecasts must sum to account and portfolio totals.
4. **Explain the oracle-doors reversal.** Perfect future distribution counts *help* at
   item-week (25.2 vs 33.4) and *hurt* at portfolio-month (19.2 vs 17.5). Unexplained, and
   in the same family as the estimator being shipped. Unexplained behaviour in a candidate
   is how two of the previous day's findings inverted.

## Open questions

- Does a **distribution forecast** help? Doors are carried flat today. Connor forecasts
  them (`Slotting Output`, points of distribution). Untested on our side.
- Does the window optimum vary by **history band** or **account**? Only L4/L12/L24/L52 were
  swept, globally.
- **Chain-linking BAR history onto PUFF** would give 43 of 75 matched pairs a year-ago
  comparison they lack. Method: rescale by the overlap-window ratio, never concatenate.
- The **`SPINS UPC` crosswalk** in `Item_Assumptions` is the authoritative Built-to-SPINS
  join and should replace our flavour-and-pack string matching.
