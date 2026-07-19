---
name: project-mo54-holiday-ablation
description: MO_54 holiday binary flag ablation — all flags hurt, week_of_year sufficient, 28-feature champion confirmed
metadata:
  type: project
---

MO_54 (`scripts/MO_54_holiday_ablation.py`) tested 6 binary holiday flags + `holiday_week` integer baseline individually against the 28-feature MO_53 champion. Completed 2026-07-07. Zero flags promoted.

**Results (Dec 2025 cutpoint, champion baseline 3.963%):**
- `is_labor_day_week`: +0.145pp
- `is_new_year_week`: +0.135pp
- `is_superbowl_week`: +0.122pp
- `is_memorial_day_week`: +0.115pp
- `is_thanksgiving_week`: +0.112pp
- `is_christmas_week`: +0.066pp
- `holiday_week` (integer 0–6): +0.046pp

**Why all hurt:** `week_of_year` (continuous 1–52) is already in the champion. LightGBM trees can split directly on specific weeks (1–2 for New Year, 47 for Thanksgiving, etc.). Binary flags add zero incremental information and compete for feature fraction against useful features.

**Conclusion:** MO_53's 28-feature set is the confirmed stopping point for feature engineering. The January protein bar spike is real but already captured. Holiday re-encoding hypothesis definitively closed.

Binary flags retained in MO_25 parquet output as audit columns (potential future use in neural architectures without tree splits).

**Why:** New Year protein bar spike was observed in charts and confirmed by Brian as a real seasonal pattern. The hypothesis was that the ordinal integer code (0–6) conflated it with lower-magnitude events. The test proved `week_of_year` already handles this without any additional encoding.

**How to apply:** Do not add holiday binary flags to LightGBM feature sets when `week_of_year` is already included. This finding applies across any tree-based model trained on SPINS weekly panel data.

Next step: MO_55 — portfolio cannibalization constraint post-processing layer.

[[project_portfolio_cannibalization]]
[[project_mo53_individual_ablation]]
