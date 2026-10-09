# Forecast pre-registration: forward tracking of five contenders

> **STATUS (updated 2026-10-09): forecasts SAVED, decision rule WITHDRAWN.**
> - Forecasts were saved at the 2026-09-06 cutoff (commit 9748e46) with contenders
>   `served_v11d` (the direct model BUILT is served), `recursive` (formerly called "champion"),
>   `flat`, `conn_L4W`, `mo130` and `blend`. Scorable once SPINS reaches 2026-12-06.
> - Challengers `direct_fixed` and `rec_dirfix` (0.5 recursive + 0.5 `direct_fixed`) were added
>   at the same cutoff (commit d216860), with the prediction recorded in MO_131
>   `ADD_PREDICTIONS`. They are scored only against this and later cutoffs.
> - The 6-cutoff decision rule below is WITHDRAWN (skeptic: unsound). It will be rewritten
>   under MO_132 principles: all data, always-valid intervals, no arbitrary windows (Jason).
>   The scoring section stays in force; no decision rule is active.
> - The contender table and predictions below describe the original five and are kept as
>   registered; "champion" there means the `recursive` model.

Registered 2026-10-08 by Jason, for review by Robert. Tool:
`scripts/MO_131_forward_tracker.py`. Forecasts are stored in `forecasts_registered/`.

## Why this exists

MO_129 and MO_130 used every historical test date (origin) to design and compare
forecasts. The 13-week horizons overlap, so no untouched history is left for a clean
confirmation (MO_130 skeptic review, 2026-10-08). The honest test is SPINS weeks that
nobody has seen yet. This document fixes the contenders, the scoring and the decision rule
**before** those weeks arrive. The commit that adds each registration file is the
timestamped proof that its forecasts came first.

## The five contenders (frozen)

All five are produced by `MO_131 register` at the newest data week. Lapsed series (no data
for 9 or more weeks at the cutoff) are forecast at 0 by every contender. Series that first
appear after the cutoff are scored at 0 for every contender (nobody can forecast them).

| Name | Definition |
|---|---|
| **champion** | The shipped model's design: `MO_80.run_production`, the production-equivalent MO_27 path (step-over-step seasonal, new-item rule without the seasonal multiplier, production training: 13-week holdout, recency 0.02, lr 0.04, cap 6000). Forward forecasts use production's donor features, which carry no look-ahead going forward. |
| **flat** | The last reported week's base units at or before the cutoff (MO_129). |
| **conn_L4W** | Sales per store per week over the last 4 calendar weeks × current store count (MO_129). Falls back to flat if there is no usable store count. |
| **mo130** | MO_130 v8: anchor + learned corrections, velocity target, recency 0.02, series-group early stopping, out-of-time level recalibration, min-rows 13 (`MO_131.MO130_SETTINGS`). |
| **blend** | 0.5 × mo130 + 0.5 × flat. Found post-hoc in the MO_130 review, so it is registered here instead of claimed. |

The code version is the git commit recorded in each registration's `.meta.json`. **No
contender may change after registration.** New challengers (e.g. a fixed MO_130) may be
registered at any time. They are scored only on cutoffs registered after them.

## Scoring (MO_80 yardstick v2)

Run when all 13 forecast weeks of a registration are in the panel (`MO_131 score`):
- **Levels:** item × week, account × month, portfolio × month (complete months only), and
  over/under bias.
- **History bands:** new, lapsed, low store count, under 13 weeks, 13–25, 26–51 and 52+.
- **Headline:** existing items. The planning total including new items is reported
  alongside.
- **Seasonal bias, per calendar year and two-sided:** January–March and October–December
  target weeks, checked as |bias − 1|, never pooled across years.
- **Margins of error:** moving-block bootstrap over scored cutoffs (block = 3), once 3 or
  more are scored.

## Decision rule (WITHDRAWN 2026-10-09, kept for the record; do not apply)

The rule is evaluated after at least **6 scored cutoffs spanning at least 6 months**.

A challenger **replaces the champion** only if all four conditions hold:
1. It beats the champion at item × week, with a 95% CI excluding 0.
2. It beats the champion at account × month, with a 95% CI excluding 0.
3. It is not significantly worse at portfolio × month.
4. For each calendar year with scored January–March or October–December weeks, its
   |bias − 1| is ≤ 0.10, or no worse than the champion's.

If several challengers qualify, prefer the simplest: flat, then conn_L4W, then blend, then
mo130. If none qualifies but flat or conn_L4W beats the champion at item × week and
account × month (CIs excluding 0), the recommendation is to switch to that simple method.
**Jason and Robert decide**; the scoreboard informs.

## Predictions (recorded before any outcome exists)

| # | Prediction |
|---|---|
| P1 | flat and conn_L4W tie at item × week (difference < 1 point). |
| P2 | mo130 ties flat at all three levels (CIs include 0). |
| P3 | blend beats flat at account × month by at least 1 point, with a CI excluding 0. |
| P4 | The champion trails flat at item × week. |
| P5 | January–March 2027 target weeks: flat, conn_L4W and the champion have bias below 0.90; mo130 and blend fall within 0.90–1.10. |

## Operating notes

- **At each SPINS refresh:**
  1. `python3 scripts/MO_131_forward_tracker.py register`, then commit
     `forecasts_registered/<date>.*` immediately.
  2. `... score`, then commit `forecasts_registered/scoreboard.json` and the
     `*.scored_rows.parquet` files.
- **Production training:** a registration takes about 10 minutes on the M3 laptop.
- **The first registration has a caveat:** it covers data through 2026-09-06 (panel built
  2026-10-01) and was made 2026-10-08. Those later weeks had happened in reality but were
  not in our data.
- **SPINS restates recent history** (1–7% of base units, up to 35 weeks back). Each
  registration scores against the panel as loaded at scoring time, the same for every
  contender.
