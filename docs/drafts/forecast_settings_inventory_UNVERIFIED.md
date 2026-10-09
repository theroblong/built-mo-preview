# Forecast settings inventory -- RAW, UNVERIFIED (scout output, 2026-10-09)

> Do not cite. Built by a low-cost scout for the planned model guide + settings handbook
> (Jason, 2026-10-09). Known problems already spotted by the main session: "after the
> 2026-10-07 fix" labels are unreliable (e.g. RECENCY_LAMBDA was never varied; the
> seasonal-blend sweep and MO_29 tree probe ran on the pre-fix bench). Every row must be
> re-checked against code and README before the guide is written, then skeptic-reviewed.

## Settings (current values; code locations)
| Setting | Recursive (MO_26/MO_27) | Direct (MO_26D/MO_27D) | Where |
|---|---|---|---|
| learning_rate | 0.04 | 0.05 | MO_26 LGBM_BASE; MO_26D:75 |
| tree cap (n_estimators) | 6000 | 3000 | MO_26; MO_26D:71 |
| early stopping patience | 50 | 100 | MO_26; MO_26D:72 |
| early stopping min_delta | 0.0 | (LightGBM default) | MO_26 |
| validation weeks | 13 (then refit on all) | 13 (NO refit) | mo_panel FORECAST_CONTRACT; MO_26D |
| recency lambda | 0.02 | 0.02 | FORECAST_CONTRACT; MO_26D:70 |
| num_leaves / min_child_samples | 63 / 20 | 63 / 20 | LGBM_BASE |
| feature_fraction / bagging_fraction / bagging_freq | 0.8 / 0.8 / 5 | same | LGBM_BASE |
| reg_alpha / reg_lambda | 0.1 / 0.2 | same | LGBM_BASE |
| random_state | 42 | 42 | LGBM_BASE |
| objective / quantiles | quantile q10/q50/q90 | same | MO_26, MO_26D |
| target transform | log1p / expm1, clip >= 0 | same | MO_26, MO_27D |
| q90 calibration | x1.0124 | -- | MO_27 (MO_67b) |
| horizon | 13 weeks | 13 | FORECAST_CONTRACT |
| lapse weeks | 9 (forecast 0) | 9 (expected resume value) | FORECAST_CONTRACT; MO_27D |
| lapse resume probability / level / TDP multipliers | -- | table / 1.06 / by cause | mo_panel |
| seasonal blend weight | 0.10 | none | FORECAST_CONTRACT; MO_27:68 |
| seasonal mode | step | target-week sin/cos features | MO_27; MO_26D |
| ROUTER_SEASONAL | False | -- | FORECAST_CONTRACT |
| short-series band width | 0.45 | -- | FORECAST_CONTRACT |
| minimum series weeks | 13 (shorter -> last-value router) | short series trained natively | FORECAST_CONTRACT; MO_26D |
| seasonal index minimum series | 200 | -- | MO_27 |

## Slider candidates (scout's list, to be re-judged)
recency weight; seasonal blend; lapse weeks; learning rate + tree cap (pair); short-series band
width; seasonal mode; router seasonal; and (from MO_133) the model-vs-last-value combination weight.
