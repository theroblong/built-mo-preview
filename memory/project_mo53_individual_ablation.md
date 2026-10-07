---
name: project_mo53_individual_ablation
description: "MO_53 individual feature ablation — brand-split donor signals, TDP change, promo v2, elasticity guardrail fix; Section 22 of HTML report"
metadata: 
  node_type: memory
  type: project
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

Designed 2026-07-07. Depends on MO_25 v5 output and MO_46 guardrail fix.

**Design rationale (from user feedback + ablation findings):**
MO_52 tested features in groups → masked individual winners (donor_count −0.081pp buried in G4 +0.052pp combined). MO_53 tests every candidate one at a time vs the 26-feature champion (MO_52, avg CV 6.537%).

**Threshold: 0.03pp** (tightened from 0.05pp — justified by 3× series count: 512 vs 164).

**Key hypotheses being tested:**
1. **Brand-split donors**: Competitor donors (market share dynamics) ≠ BUILT sibling donors (intra-brand cannibalization = zero-sum). Separate signals expected to have different predictive value and direction.
   - `competitor_donor_count` — number of competitor brand donors
   - `built_donor_count` — number of BUILT sibling donors (own-brand cannibal risk)
   - `competitor_donor_units_wow` — competitor acceleration (market share timing)
   - `built_donor_units_wow` — sibling acceleration (cannibalization leading indicator)
2. **TDP change vs. level**: `tdp` and `tdp_z8` (level) already in champion. CPG research shows *growth rate* predicts unit sales — distribution expansion precedes sales gains.
   - `tdp_wow_delta` — WoW stores gained/lost
   - `tdp_4w_momentum` — 4-week distribution trend direction
3. **Promo signals v2 (absolute dollar)**: v4 `arp_discount_pct` at 5% = $0.50 for a $10 4-pack (too wide — missed nickel-level TPR). Fixed:
   - `arp_dollar_discount = arp_roll8_avg - arp > $0.05` — absolute threshold
   - `promo_lift_ratio = total_units / base_units − 1` — display lift independent of price
4. **Rolling elasticity v2**: MO_46 guardrail was applied to raw ARP ($0.05 range on $10 4-pack = trivial to pass). Fixed: apply `PRICE_GUARDRAIL` to `arp / pack_count` (true $/bar). May reduce null coverage but improve signal quality.

**MO_25 v5 changes that enable this:**
- `built_upc_set` captured from EDW → classifies donor_upc as BUILT or competitor
- `competitor_donor_count`, `built_donor_count` — split from `donor_count`
- `competitor_donor_*`, `built_donor_*` — brand-split weekly aggregates
- `competitor_price_gap` — now uses competitor donors only (v4 mixed BUILT siblings in)
- `tdp_wow_delta`, `tdp_4w_momentum` — new columns after arp rolling stats step
- `arp_dollar_discount` — absolute $ (model feature; `arp_discount_pct` demoted to audit)
- `promo_lift_ratio` — display lift ratio
- `competitor_donor_units_wow`, `built_donor_units_wow` — WoW diff by brand

**MO_46 fix:**
- Loaded pack_count from built_prepost_features in step 3b
- `arp_per_bar = arp / pack_count` computed on focal panel
- `_add_rolling_elasticity()` now applies guardrail to `arp_bar_v` (per-bar price range) instead of raw ARP range
- OLS still fit on `log1p(arp_v)` (raw) for interpretability

**Pipeline order:** MO_46 (fix guardrail) → MO_25 v5 (new columns) → MO_53 (ablation).

**MO_53 Results (completed 2026-07-07):**

| Feature | wMAPE | Δ vs champion | Promoted? |
|---|---|---|---|
| `donor_count` | 3.915% | −0.081pp | ✓ |
| `tdp_wow_delta` | 3.951% | −0.045pp | ✓ |
| `built_donor_units_wow` | 3.978% | −0.018pp | ✗ (below 0.03pp) |
| `max_donor_cannibal_prob` | 3.983% | −0.013pp | ✗ |
| `rolling_cannibal_pressure` | 3.981% | −0.015pp | ✗ |
| `holiday_week` | 3.973% | −0.023pp | ✗ |
| `promo_intensity` | 3.973% | −0.023pp | ✗ |
| `built_donor_count` | 4.015% | +0.019pp | ✗ (hurts mildly) |
| `competitor_donor_count` | 4.086% | +0.090pp | ✗ (hurts) |
| `tdp_4w_momentum` | 4.101% | +0.105pp | ✗ (hurts — redundant with rolling stats) |

**Brand-split finding (key):** `competitor_donor_count` HURTS (+0.090pp) while total `donor_count` (mixed) HELPS (−0.081pp, promoted). The model uses pool size as a competitive complexity signal, not brand breakdown. Splitting into competitor vs BUILT loses the aggregate count stability.

**New champion:** donor_count + tdp_wow_delta added to 26-feature set → 28 features, avg CV 6.448% (vs 6.537%, +0.089pp improvement).

**Rolling CV detail:**
- Jun 2025: 12.643% → 12.311% (−0.332pp — biggest gain in low-data / early-lifecycle regime)
- Sep 2025: 2.972% → 3.073% (+0.101pp — slight regression at mid-year)
- Dec 2025: 3.996% → 3.961% (−0.035pp)

**Rolling elasticity still hurts (+0.037pp)** even after MO_46 $/bar guardrail fix. Signal is inherently noisy at 13-week window grain with only 2-3 price events qualifying. Not promoted.

**MO_26 updated:** FEATURE_COLS now contains 28 features with donor_count + tdp_wow_delta added; removed implied_elasticity, max_donor_cannibal_prob, rolling_cannibal_pressure/trend/elasticity (validated as neutral/harmful across MO_50–MO_53).

**HTML:** Section 22 of built_demand_intelligence_report.html

**How to apply:** New champion FEATURE_COLS is in MO_26. Next: re-run MO_26→MO_27 to regenerate forecasts with the 28-feature champion. See [[project_mo52_feature_ablation]] for prior context.
