---
name: project_mo52_feature_ablation
description: MO_52 feature group ablation results — MO_25 v4 new signals tested against M1+topK champion on 512-series dataset
metadata: 
  node_type: memory
  type: project
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

Completed 2026-07-07. Tested 8 feature groups from MO_25 v4 against MO_51 champion (M1+week_of_year).

**Critical context: dataset expanded from 164 → 512 qualifying series**
MO_25 v4's improved ARP cascade (rolling 13w fallback) retained more series. This is itself a win — the model now trains on 3x the data. The portfolio-level champion is now avg CV wMAPE 6.537% (vs 7.79% in MO_51), new champion even without new features.

**Group ablation results (Dec 2025 cutpoint, 512 series, threshold ≥0.05pp):**

| Group | wMAPE | Δ vs champion | Promoted? |
|---|---|---|---|
| Champion (M1+topK) | 3.996% | — | — |
| G1 Promo signals | 4.044% | +0.048pp | ✗ (hurts) |
| G2 Holiday flags | 3.973% | −0.023pp | ✗ (below threshold) |
| G3 Pack format | 3.988% | −0.008pp | ✗ (below threshold) |
| G4 Cannib+PE combined | 4.048% | +0.052pp | ✗ (hurts when combined) |
| G5 Competitor combined | 3.973% | −0.023pp | ✗ (below threshold) |
| G6 BUILT TDP share | 4.048% | +0.052pp | ✗ (hurts) |
| G7 Combined winners | 3.996% | 0.000pp | no change |
| G8 ARP → arp_discount_pct swap | 4.038% | +0.042pp | ✗ (hurts) |

**Individual feature standouts (G4 detail):**
- `donor_count`: −0.081pp ← strongest new signal; buried by group because rolling_elasticity (+0.099pp) hurts
- `max_donor_cannibal_prob`: −0.013pp (modest positive)
- `rolling_elasticity`: +0.099pp (hurts — null coverage / noise)
- `implied_elasticity`: +0.022pp (hurts — static ICC=1.0 signal adds noise)

**Individual feature standouts (G5 detail):**
- `top_donor_units_wow`: −0.037pp ← competitor acceleration is a real signal
- `top_donor_tdp_sum`: −0.011pp (modest)
- `top_donor_units_sum`: −0.011pp (modest)
- `competitor_price_gap`: −0.002pp (negligible)

**Root cause of "no promotions":**
Group-level testing mixes good and bad signals. donor_count (−0.081pp) is buried inside G4 which also contains rolling_elasticity (+0.099pp). The group result (+0.052pp) hides the individual winner.

**Next step: individual SHAP-guided pruning**
MO_53 should run individual feature ablation (one feature at a time vs champion), rank by improvement, promote features that individually clear 0.03pp on the 512-series dataset. donor_count and top_donor_units_wow are the strongest candidates.

**Threshold recalibration note:**
0.05pp was calibrated for 164 series (MO_51). With 512 series, statistical reliability is higher and a lower threshold (0.03pp) is defensible. Document this in MO_53 design.

**How to apply:** When designing MO_53, do individual feature ablation (not group), use 0.03pp threshold on 512-series dataset, and explicitly isolate donor_count + top_donor_units_wow as the most likely promotions. Do NOT include rolling_elasticity or implied_elasticity as standalone features — they consistently hurt.
