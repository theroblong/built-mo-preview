---
name: project_mo56_candidate
description: "MO_56 DONE 2026-07-07: time-varying Mo signals correctly implemented, still rejected — MO_53 28-feature set confirmed as final stopping point"
metadata:
  node_type: memory
  type: project
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

**Status: DONE (2026-07-07) — 0 promoted, feature engineering loop closed.**

**What was tested:** `cannibal_rate` (from `cannibalization_rate_weekly`, null→0) and `price_elasticity_effect` (`arp_pct_change × ε`) individually and combined vs MO_53 28-feature champion. First run with conditional accuracy split (event-context vs stable).

**Champion baseline (Dec 2025):**
- Global: 3.961% | Event-context (wsl≤26 or |Δprice|≥5%): 2.657% | Stable: 4.184%
- Key: champion already better on event rows (2.657%) than stable (4.184%)

**Results (all hurt):**
- `cannibal_rate`: +0.104pp global, +0.073pp event, +0.109pp stable
- `price_elasticity_effect`: +0.092pp global, +0.082pp event, +0.093pp stable
- Both combined: +0.082pp global, +0.178pp event, +0.065pp stable

**Root causes:**
1. `cannibal_rate` is a lagging indicator — AR lags already encode cannibalization damage via lagged outcomes. Rate adds noise on top of the outcome already in training targets.
2. `price_elasticity_effect` has near-zero variance (mean=0.0003). ARP WoW changes average 0.33%; protein bar prices are extremely stable. For series with null elasticity, forced to 0.

**Architecture conclusion (IMPORTANT — drives future decisions):**
Mo signals are lagging indicators relative to AR. This is NOT a bug; it's the architecture. By the time you observe a high cannibal_rate, the decline is already in the lag1 target. Mo Intelligence belongs in:
- Explainability (event cards, SHAP, driver attribution)
- Early warning (event queue, rate forecast trends)
- Scenario planning (MO_55 portfolio adjustment, elasticity price scenarios)
NOT in wMAPE improvement.

**MO_53 28-feature set = confirmed final stopping point for SPINS LightGBM weekly demand forecasting.**

**Feedback rules added:** [[feedback_ml_feature_signals]] rules 6, 7, 8 (now documented as permanent guidance — don't retry these approaches)
