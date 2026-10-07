---
name: feedback_ml_feature_signals
description: "ML feature engineering lessons — built_tdp_share hurts, rolling_elasticity guardrail bug, promo % vs absolute $, brand-split donor signals"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

**Rule 1: Test TDP change signals, not TDP share ratio.**
The level (tdp, tdp_z8) already captures absolute distribution. Adding `built_tdp_share = focal_TDP / category_TDP` introduces a noisy denominator without new information — it hurt in ablation (+0.052pp). CPG research shows distribution *growth* predicts sales; the right signals are `tdp_wow_delta` and `tdp_4w_momentum`.

**Why:** User confirmed from prior studies that distribution expansion is a leading indicator — but the *share of category shelf* ratio dilutes this with denominator noise (all-brand TDP fluctuates from entries/exits).

**How to apply:** Use `tdp_wow_delta` and `tdp_4w_momentum` for model features. Keep `built_tdp_share` and `category_tdp_sum` as audit columns for FP&A explainability only.

---

**Rule 2: Apply price guardrails to $/bar (ARP / pack_count), not raw ARP.**
`MO_46 PRICE_GUARDRAIL = $0.05` was applied to raw ARP. A 4-pack at $10 ARP only needs $0.06 total range in a 13-week window to pass — trivially satisfied by scanner noise. Multi-packs were getting rolling_elasticity computed on mostly-flat price series. Fixed: compute `arp_per_bar = arp / pack_count`, apply guardrail to per-bar range.

**Why:** rolling_elasticity consistently hurt in ablation (+0.099pp). Root cause was the guardrail being too permissive for multi-packs. Affects any price-based quality gate.

**How to apply:** Any future price threshold/guardrail must normalize by pack_count. Same principle applies to TPR event detection and competitor_price_gap interpretation.

---

**Rule 5: Do NOT add holiday binary flags when week_of_year is in the feature set.**
MO_54 tested all 6 binary holiday flags (`is_new_year_week`, etc.) plus `holiday_week` integer — all 7 hurt the model (Δ +0.046pp to +0.145pp). Root cause: `week_of_year` (continuous 1–52) already encodes the seasonal pattern. LightGBM tree splits can isolate weeks 1–2 for the New Year spike directly from `week_of_year` — binary flags add redundancy that competes for feature fraction without new signal.

**Why:** The January protein bar spike IS real (confirmed from charts + Brian). But the model already captures it via `week_of_year`. Adding a binary flag that says the same thing in different form is pure noise.

**How to apply:** `week_of_year` is sufficient for all holiday and seasonal encoding in LightGBM models on SPINS weekly data. Binary holiday flags are retained in MO_25 parquet as audit columns — potentially useful for neural architectures (which don't learn splits automatically) or for feature importance explainability. Never add them to FEATURE_COLS when week_of_year is present.

---

**Rule 3: Use absolute dollar thresholds for promo ARP detection, not percentage.**
`arp_discount_pct` at 5% of $10 4-pack = $0.50 threshold — misses TPR events below that level. The nickel standard ($0.05 absolute) is the correct threshold, matching MO_17's guardrail. Use `arp_dollar_discount = arp_roll8_avg - arp > $0.05` for is_promo_arp detection.

**Why:** v4 promo signals (G1) all hurt (+0.048pp combined). Percentage-based threshold misclassifies quiet weeks as promo-free and misses real promotions.

**How to apply:** In MO_25, `arp_dollar_discount` (absolute $) is the model feature. `arp_discount_pct` (percentage) is audit only. Any future promo detection should use absolute dollar thresholds.

---

**Rule 6: Use `cannibalization_rate_weekly` (time-varying), not `cannibal_prob` (static), as the training feature.**
`scored_cannibalization.cannibal_prob` is a one-time classification score — constant per series, ICC=1.0. In a temporal model it has zero week-to-week predictive power. `cannibalization_rate_weekly` from MO_19 is the actual weekly rate (rises at sibling launch, decays as consumers habituate) and IS time-varying. In MO_50, the join produced 73% null because nulls were treated as missing instead of zero. **Null = no active cannibalization = 0 pressure, not missing data.**

**Why:** MO_41 ICC=1.0 confirmed static signals can't differentiate forecast weeks. MO_50 73% null killed the time-varying signal before the model saw it.

**How to apply:** In MO_56, aggregate `cannibalization_rate_weekly` to (focal, week) by summing rate across all active donors. Null → 0. This is `cannibal_rate_sum`. Never use `cannibal_prob` alone as a training feature in temporal models.

---

**Rule 7: Elasticity is a multiplier — use the interaction term, not the coefficient alone.**
`elasticity_coef` (ε) is static per (upc, retailer) — same ICC=1.0 problem if used standalone. Its information is realized only when price actually changes. The correct training feature is `price_elasticity_effect = arp_pct_change × elasticity_coef` — time-varying (nonzero only in price-event weeks), causally interpretable, and defensible to a CFO. Static ε as a standalone feature is useless in a temporal model.

**Why:** rolling_elasticity hurt in every ablation (+0.037–0.099pp). Root cause was partly the guardrail bug, but fundamentally the static ε adds no week-to-week information.

**How to apply:** Compute `price_elasticity_effect = arp_pct_change × elasticity_coef` per (upc, retailer, week) in MO_25. Test in MO_56 ablation on price-event weeks only (|arp_pct_change| > 5%). Never use ε alone as a model feature.

---

**Rule 8: Evaluate Mo signals on event-context series, not global wMAPE.**
Global wMAPE averages across ~2,200 stable mature series and ~300 event-context series. Mo signals add noise on stable series but should help on event-context series — new launches (wsl ≤ 26) and significant price events (|arp_pct_change| > 5%). Global average makes Mo look worse than it is; conditional evaluation gives the right signal.

**Why:** M1 (demand-only, 3.52%) wins globally because stable series dominate. The CFO cares most about forecast accuracy on launches and price events — exactly where Mo signals are designed to help.

**How to apply:** In any Mo feature ablation, always run a conditional split: (1) event-context series, (2) stable series. Report both. Don't suppress the global result but don't use it as the sole acceptance criterion.

---

**Rule 9: Fourier week encoding does NOT help LightGBM. See Rule 11 (MO_57 result).**
Pre-MO_57 prediction was wrong: Fourier encoding was expected to help seasonal transitions, but MO_57 showed it hurts (+0.162pp global, +0.214pp event-context). `week_of_year` integer is sufficient for tree models. Rule 11 supersedes this rule for LightGBM. Fourier encoding is only relevant for neural architectures where input space distance affects gradient updates.

---

**Rule 10: Price change bins as a 4-level categorical — test after continuous features are exhausted.**
All continuous price features have been rejected (MO_52 G1 +0.048pp, MO_53 `arp_dollar_discount` +0.052pp, MO_53 `is_promo_week` +0.023pp, MO_56 `price_elasticity_effect` +0.092pp). A 4-level categorical bin may capture non-linear regime semantics that continuous features cannot. But distribution imbalance is severe: ~90–95% of rows are "stable" (mean WoW ARP change = 0.33%). Test last in MO_57 ablation.

**Bin strategy (aligned with existing thresholds):**
- `0` stable: `|Δ$| < $0.05` AND `|Δ%| < 2%`
- `1` small discount: `$0.05–$0.25` drop OR `2–5%` change
- `2` significant discount: `> $0.25` drop OR `> 5%` (MO_56 event threshold)
- `-1` price increase: `> $0.05` rise
Encode as LightGBM `category` dtype. Evaluate conditional split (event rows vs stable) per Rule 8.

**Why:** LightGBM already does implicit histogram binning on continuous features. Manual bins add regime semantics — a 5% cut crosses a consumer-response threshold that the model may not discover from continuous variance. But if AR lags already absorbed the demand response (MO_56 conclusion), the bin will also be rejected.

**How to apply:** MO_57 ablation, individual test, conditional evaluation. Low confidence — expect rejection. Do not add alongside Fourier or lag features (test independently to isolate signals).

---

**Rule 11: Fourier encoding does NOT help LightGBM tree models — week_of_year integer is sufficient.**
MO_57 result: replacing `week_of_year` (integer 1–52) with `week_sin` + `week_cos` hurt by +0.162pp globally and +0.214pp on event-context rows. LightGBM tree splits can isolate "week 1" and "week 52" from integer features directly — they don't need the Dec→Jan adjacency to be encoded in the feature representation. Fourier encoding is a neural-network concern (where the distance metric matters), not a tree-model concern.

**Why:** Rule 9 (added pre-MO_57) was wrong in its prediction — it said Fourier "should help seasonal transitions." MO_57 proved week_of_year integer is sufficient. Retract the prediction in Rule 9; the rule is corrected here.

**How to apply:** Do NOT replace `week_of_year` with Fourier terms in LightGBM or other tree-based models. Fourier encoding is only relevant for neural architectures (LSTM, Transformer, N-BEATS) where the input space distance affects gradient updates.

---

**Rule 12: lag1→lag4 is the complete AR lag set — lag2 and lag3 add noise.**
MO_57 tested `base_units_lag2` (+0.065pp) and `base_units_lag3` (+0.087pp) individually — both hurt. There is no 2-week or 3-week inventory/promo cycle that the existing lag1→lag4 brackets miss. The model is already at full AR capacity with lag1, lag4, lag13, lag52. Note: lag2 showed marginal event-context improvement (−0.064pp) but below the 0.05pp event promotion threshold, and stable worsened +0.088pp (above the 0.05pp penalty cap).

**Why:** The gap between lag1 and lag4 appeared potentially useful theoretically, but training data shows the model already interpolates this from lag1 and the rolling averages (roll4_avg, roll8_avg cover the same time window as lag2/lag3).

**How to apply:** Do not add lag2, lag3, or any intermediate AR lags to FEATURE_COLS. Current lag set (lag1, lag4, lag13, lag52 + velocity_spm_lag52) is complete for weekly SPINS data.

---

**Rule 4: Track total donor pool size; brand-split counts hurt the model.**
`donor_count` (total donors, BUILT + competitor mixed) was the strongest individual signal (−0.081pp, promoted to champion in MO_53). Splitting into `competitor_donor_count` HURT (+0.090pp); `built_donor_count` also slightly hurt (+0.019pp).

**Why (MO_53 result):** The model uses `donor_count` as a competitive complexity / market segment indicator — how crowded is the space? Splitting into brand types loses the aggregate count stability and introduces 64% null coverage (competitor_donor_tdp_sum is 36% covered). The explanatory framing Jason prefers (competitor ≠ own-brand) is valid for the UI, but the ML model benefits from the aggregate count signal.

**How to apply in the model:** Use total `donor_count` as a model feature. Keep `competitor_donor_units_wow` and `built_donor_units_wow` as candidate signals for future ablation (both −0.018pp individual, below 0.03pp threshold). For Mo Chat and UI, still use the brand-split framing for explanations. Do NOT replace `donor_count` with `competitor_donor_count` — the aggregate is more stable.
