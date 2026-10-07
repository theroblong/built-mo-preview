---
name: project_ml_architecture_roadmap
description: "Strategic ML architecture vision beyond MO_50 — layered forecast, Mo Intelligence practical impact, champion-challenger, degradation monitoring"
metadata: 
  node_type: memory
  type: project
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

Strategic direction established 2026-07-07 after MO_50 results confirmed M1 (demand foundation) beats all richer feature sets at portfolio level.

**Why Mo Intelligence needs a better story:**
BUILT has an edge no one else has — SPINS competitive data (competitor TDP, velocity, price) combined with their own multi-SKU portfolio. The stock market analogy applies: quants using only price momentum lose to those incorporating fundamentals. BUILT + SPINS gives signal that single-source models can't replicate. The goal is to make Mo Intelligence *practically impactful* (actionable decisions) not just *novel* (impressive charts).

**Layered forecast architecture (target state):**

Layer 1 — Structural / Seasonal (interpretable, fully explainable):
- STL decomposition of category-level volume → seasonal index
- Apply index to SKU baseline
- Handles: New Year health spike, summer softness, holiday patterns
- Aligns with Brian's existing seasonal adjustment factors
- Works for new SKUs (borrows category seasonal curve when SKU has <52w)

Layer 2 — Distribution forecast (TDP × velocity decomposition):
- TDP trajectory: logistic growth for new SKUs; AR for mature
- Velocity per TDP as separate explainable component
- Answers: "is growth TDP-driven or velocity-driven?" — the key FP&A question
- New product growth: similar-launch lookup (find analogous SKU/channel/pack ramps in SPINS history)

Layer 3 — Competitive adjustment (Mo Intelligence — time-varying):
- rolling_cannibal_pressure → demand drag factor (already in MO_46)
- rolling_elasticity → price sensitivity multiplier (already in MO_46)
- Promo lift model → event-driven upside (MO_49 foundation)
- Category share dynamics from SPINS competitor data
- This is the unique BUILT edge — only they can compute this

Layer 4 — Residual learning (LightGBM on whatever Layers 1-3 miss):
- SHAP explains contribution; should be small if Layers 1-3 are well-specified
- If Layer 4 contribution is large → signals that Layers 1-3 are under-specified

**Explainability / auditability requirements (non-negotiable):**
- Every layer must have a clear, isolated contribution measurement
- Feature attribution: SHAP for LightGBM; decomposition for STL/Prophet
- Run-to-run comparison: model_history.json tracks champion, each run's metrics
- Causal analysis (MO_43/44) supplements but doesn't replace the forecast story

**Category concatenation approach (MO_52 target):**
- Aggregate SPINS data across competitor + BUILT SKUs at channel×retailer level
- Compute category-level seasonal STL decomposition
- Use category seasonal index as a feature in LightGBM (borrowed seasonality)
- Enables new product forecasting without 52w history: SKU borrows category curve
- Prophet/STL handle the structural component; LightGBM fits the competitive residual

**Champion-challenger / model history:**
- model_history.json appended per training run: version, date, feature_set, val_wmape, test_wmape, n_series, champion_flag
- If new model >0.5pp worse than champion → warning + retain champion pickle
- Always run M1, M5b, best-variant in parallel; serve champion externally; expose comparison in HTML report
- Degradation triggers: val wMAPE >6%, feature mean drift >2σ, coverage drop (rolling_cannibal_pressure below 20%)

**Rolling CV (stability over single cutpoint):**
- 3 cutpoints: Jun 2025, Sep 2025, Dec 2025
- Average wMAPE across cutpoints is the stable headline metric
- Defends model to Bracken/Jeff skeptics ("does it hold up across periods?")

**MO script results:**
- MO_51 DONE (2026-07-07): Best reg params: α=0.3, λ=0.3, num_leaves=63 → 3.571%. SHAP pruning: M1+week_of_year = 3.556% best pruned set. Rolling CV champion: M1+topK avg 7.8% across 3 cutpoints. CRITICAL FINDING: at Jun 2025 cutpoint (108 series, lower data), M5b Rolling (13.9%) beats M1 (15.2%) by 1.3pp — Mo signals win in early-lifecycle / cold-start regime.
- MO_53 DEFINITIVE CHAMPION: 28 features, avg CV 6.448%. Feature engineering stopping point confirmed.
- MO_59 DONE (2026-07-08): STL (statsmodels, period=52, robust=True) + PELT changepoints. Portfolio seasonal index saved to `mo59_seasonal_index.csv`. §28 in HTML report.
- **Layer 1 WIRED (2026-07-09):** STL seasonal index applied as post-forecast multiplier in MO_27 for series lacking lag52 (50.6% of series, 1,264). YAGO blend unchanged for mature series (49.4%). Two independent complementary seasonal signals. Ablation confirmed stl_seasonal_index has zero LightGBM importance alongside week_of_year — correctly placed as post-processing, not feature. 28-feature MO_53 champion preserved.
- MO_60 REBUILT + DONE (2026-07-20 VA7): Causal sensitivity analysis — stress-test MO_72's 140 SIGNIFICANT events across 9 parameter variants (3 Pearson × 3 ARP tolerance). Results: 40 ROBUST (29%), 13 MODERATE, 87 FRAGILE (62%). 26 ROBUST + correct direction = safe to cite. BJS Double Choc 4pk: 9/9 ROBUST (−35.6% price → +215.5% demand). Outputs: `causal_impact_sensitivity.parquet`. Next: merge into Druid causal_impact_scores. NOTE: earlier MO_60 (synthetic control + DiD) was superseded by this approach.
- MO_61 UPDATED + DONE (2026-07-20 VA8): EconML LinearDML HTE elasticity. BUILT UPCs only; 48,160 fitting rows; schema fixed (arp_pct_change computed from arp_wow_delta/arp_lag1). Results: 12-pack ε=−0.63 vs single ε=−0.18 (3.5× gap); early-launch ε=−0.35 vs mature ε=−0.11 (CI crosses zero); Q2 most elastic; mid-cannibalization ε=−1.01 (790 obs, wide CI). §30 in HTML report.
- MO_62 DONE (2026-07-08): Foundation model zero-shot benchmark. 100 series, Oct 2025 holdout, 13w horizon. Results (median wMAPE): Chronos 27.7%, Granite TTM 27.7%, Moirai 32.3%, TimesFM 38.1% vs Aevah 6.1%. Foundation avg 31.5% = 5.1× worse. All local inference, Apache 2.0. §31 in HTML. Marketing notes: "Foundation Model Gap" section + horserace visual + LightGBM removed + LLM/SLM agnostic + sovereign AI.
- MO_63 DONE (2026-07-09): Rolling cross-validation — 6 expanding-window cutpoints (Sep 2024–Dec 2025). Same 28-feature MO_54 champion at every cutpoint. Results: median wMAPE 2.02–5.71% across all periods; accuracy range 3.69pp; Mar 2025 hardest (5.71%, Jan health spike fading); Dec 2025 best (2.02%, 442 series, portfolio most mature). Avg gap vs. naïve last-value: +33.1pp. Accuracy improves Sep 2024→Dec 2025 (2.82%→2.02%) as YAGO lag52 becomes available — directly validates "accuracy compounds" marketing claim. §32 in HTML.

**How to apply:** When building any new MO script, check which layer it belongs to. Layer 1-3 improvements are highest priority — they have the clearest story for Brian/FP&A. Layer 4 (LightGBM tuning) is secondary. Never add a feature without measuring its isolated contribution (ablation or SHAP).
