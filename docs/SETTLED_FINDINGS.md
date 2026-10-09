# Settled findings

**DRAFT 2026-10-07 — pending review by Robert and Jason. Not loaded into CLAUDE.md until reviewed.**
Spec: `docs/design/settled-findings-and-agents.md`. Extracted by sonnet from the README
(updates 1–228), project memory, `memory/`, and the test plan. Status assigned by opus.
Evidence lines spot-checked.

**Statuses**
- **SETTLED**: measured on the corrected harness (after MO_118, 2026-10-06), at all three
  levels, and by history band. Or a method rule learned from a reversal.
- **PROVISIONAL**: anything else. It was tested, so don't re-test casually. To re-test,
  meet its *reopen if*.
- **REVERSED**: overturned. Don't cite it, and don't re-derive it.
- **FACT**: a data, infrastructure or design fact that doesn't depend on the forecast
  harness. README 222: "panel-level findings are harness-independent and stand".

**Note:** every forecast-loop result dated before 2026-10-06 was scored on a configuration
production never runs (MO_118, 11.83pp), so it is PROVISIONAL at best. Very little meets
SETTLED yet.

**Using this list**
- New MO_127+ scripts cite related entries in a `PRIOR WORK` section, or write `none found`.
- A commit that records a reversal must update this file.
- Sources are `file:line`. The `scout` agent can pull the full context.

## Proposed changes, PENDING Robert + Jason review (2026-10-07)
These come from MO_127, MO_128 and the skeptic reviews (live notes, 2026-10-07). The entries
below them are deliberately unchanged until review.
- **MO_113 anchor seasonal mode → REVERSED.** Its gain used a full-panel seasonal index with
  look-ahead. With an honest index, anchor is the worst arm: 55.30 cell × week, 32.71
  portfolio × month (MO_127).
- **MO_125 conn_L4W 10.71 → REVERSED.** It relied on the look-ahead index. Honest
  (conn_L4W_off) vs flat:
  - portfolio × month 16.42 vs 15.99, and flat has the lowest error in 5 of 7 quarters
  - cell × week 32.53 vs 32.82
  - account × month 21.71 vs 22.93

  README 226's "seasonality matters far more once anchored" is reversed with it (MO_127).
- **README 223, "model beats flat at portfolio × month" → REVERSED.** Honest: model 17.32
  vs flat 15.99. This settles MO_92 vs README 223 in MO_92's favor (MO_127; skeptic,
  2026-10-07).
- **MO_126 → RE-SCOPED.** Honest conn_off minus model, cell × week, by band:
  +5.7 / −2.4 / −3.9 / −6.5. Against flat: +5.7 / +0.3 / +0.3 / −1.7. conn beats flat only
  at 52+ (MO_127).
- **MO_128 (PROVISIONAL).**
  - The L12W vs L4W window flips by quarter. L4W is best in 5 of 7 quarters, and L12W's
    104+ lead is Q1 2026 plus Sam's/Walmart. Don't route to L12W.
  - Amend "exclude BAR": the gain fades as BAR's training share falls (17.6% → 3.0%), and
    is ~0 in 2026.
  - Model bias on 52+ PUFF is ~0.55 in Q1 and ~1.07 otherwise. It is not a general growth
    under-forecast.
- **FACT addendum (seasonal index).**
  - No honest MO_59 index can exist at any 2025 cutoff (panel starts 2023-10-15).
  - Rebuilding it per cutoff on ~2 years inflates the range 1.5–2× (two-cycle STL absorbs
    growth) and jumps at the cutoff week.
- **FACT candidate (history length).** Count history as calendar span with real
  distribution, not rows. The Walmart PUFF 1.41oz singles are relaunches mislabeled 52+.
- **New method rule candidate (SETTLED).** Every fitted input (seasonal index, scaler,
  anchor) is rebuilt from data up to each cutoff.

### Added 2026-10-09 from MO_132 (Tier 1, 18 origins, all series; README 232), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss %,
existing series, item x week unless stated.
- **MO_103 "direct beats recursive" → REVERSED for the served direct model (MO_27D v11d).**
  Served direct is worse than the recursive model by -5.02 (12 of 18 origins) and worse than
  flat by -7.88 [-13.8, -4.7] (15 of 18, every quarter). *Skeptic: SURVIVES WITH CAVEATS (not
  every simple arm beats it, seasonal naive is worse; Walmart is 2.59 of the 7.88 gap; "served"
  = production minus donor features, lapsed 0).* **Not reproduced for the repaired
  `direct_fixed`:** it ties recursive at item x week (-0.67 [-3.3, +3.9]), wins horizons 1-6,
  loses horizons 7-13, and wins at portfolio x month (-4.48). *Skeptic: SURVIVES WITH CAVEATS
  (the two fixes, calendar and refit, are bundled; gain concentrated in winter origins).*
- **MO_104 "SES ties flat" → reconfirmed under parity** (MO_132 ses arm 32.48 vs flat 32.59
  at item x week; the velocity version ses_vel 32.46 ties too). *Skeptic: "MO_104 (SES ties
  flat): reconfirmed (−0.12, not significant)."*
- **MO_125 conn_L4W reversal → supported** (MO_132: conn_L4W 32.93 / 20.69 / 12.61 vs flat
  32.59 / 21.12 / 12.84, a tie). *Skeptic: "MO_125 conn_L4W: the proposed reversal is supported
  (not significant at all three levels)."*
- **Open blocker "model worse than flat on 52+ weeks" → reproduced:** recursive 28.69,
  `direct_fixed` 29.62, flat 25.85. *Skeptic: reproduced.*
- **Not for the list:** the shape claims (C4) and the velocity-view claims (C5) DO NOT SURVIVE
  the skeptic; only "shape skill is weak overall" stands.
- **New method rule (a), propose SETTLED.** Never mix laptop and worker LightGBM results in
  one comparison; run every arm of an experiment on the same machine. Cross-machine item-level
  differences are about 7% median (aggregates within about 0.1-0.8); deterministic flags on
  both machines do not fix it (parity jobs -003/-004). *Skeptic verdict on this rule: not
  separately reviewed (measured in the parity jobs, not a MO_132 claim); same-machine seed
  noise below is skeptic-checked.*
- **New method rule (b), propose SETTLED.** Direct-model numbers need seed averaging before
  they are quoted to a decimal: a seed-7 retrain moved item forecasts by a median of 10-11.5%;
  aggregates moved +/-0.15 (item x week), +/-0.9 (account x month), +/-0.6 (portfolio x
  month). *Skeptic: measured by the skeptic (blocks 1-6 x 3 seeds plus one seed-7 retrain at
  2025-12).*
- **New method rule (c), propose SETTLED.** Shape scores must report false calls, a chance
  baseline and origin-level confidence intervals. *Skeptic: from the C4 DOES-NOT-SURVIVE
  verdict (turns metric ignored false calls: 25 called for 12 hits; direct_fixed's interval
  [43.5, 59.9] includes chance).*
- **Exploratory, NOT a finding:** the 50/50 recursive + `direct_fixed` average (32.18 / 20.29
  / 10.47) is post hoc; it is registered as a forward challenger (`rec_dirfix`), not settled.

### Added 2026-10-09 from MO_133 (combinations, seed averaging, shape; 18 origins; README 234), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss %, existing
series, item x week unless stated; * = interval excludes zero; ns = not significant.
- **(a) Seed averaging of the direct model: small gain.** Five-seed average (direct_avg5) vs one
  seed: -0.62 [-0.8, -0.4]*, 13+ weeks only -0.63*, all history bands; every single seed scored
  34.70-34.90 vs 34.15 for the average. *Skeptic: SURVIVES.*
- **(b) Recursive + fixed direct (50/50, rec_dir5) beats the current recursive model at item x
  week, including established series:** -3.42*, 13+ weeks only -3.48 [-5.7, -0.6]*. At portfolio
  x month the gain (-3.29*) is not significant when scored within history bands (-2.23 [-5.2,
  +1.5] ns). Same origins and data as the design, so not out-of-sample (fresh seeds and machine
  only). *Skeptic: SURVIVES WITH CAVEATS.*
- **(c) No combination beats last week carried forward on established series.** rec_dir5 vs last
  value, 13+ weeks only: +0.14 / -0.39 / -1.34 (item x week / account x month / portfolio x
  month), all ns. The gains are confined to young items (under 13 weeks and 13-25 weeks); the 52+
  band ties (-0.28 / -0.43 / -0.96 ns). The pre-registered P4 (rec_dir5_flat beats last value at
  item x week and account x month) FAILED (-1.07 [-1.8, +0.0]). Claude's preliminary statement
  that the combination "beats last value at the planning levels" is withdrawn. *Skeptic: the
  "combos beat last value" claim DOES NOT SURVIVE.* Do not cite as a gain over last value.
- **(d) Start-anchoring the forecast shape adds no detectable difference** (anchored minus
  unanchored rec_dir5: +0.01 / +0.03 / +0.68 ns). *Skeptic: SURVIVES as "no detectable
  difference".*
- **(e) Method rules, propose SETTLED.** (i) Report band-separated portfolio x month and
  13+-weeks-only results next to every pooled number. (ii) Shape scores use a majority-direction
  baseline (not 50%), and for fewer than 10 origins report per-origin values and an exact sign
  test (the block bootstrap degenerates: 6 origins gave 10 distinct resamples). *Skeptic: from
  the must-fix list after the MO_133 review; the "2026 worse than chance" shape claim DOES NOT
  SURVIVE (41 real moves, intervals include chance); the 2026 account x month shape result
  (direct_avg5 and rec_dir5 rank correlation above zero in 6 of 6 origins, exact sign test
  p=0.016) SURVIVES WITH CAVEATS.*
- **(f) Open blocker "model worse than flat on 52+ weeks" stands:** rec_dir5 26.5 vs last value
  25.8. *Skeptic: stands.*
- **EXPLORATORY, post hoc, NOT a finding:** in the 6 overlapping 2026 origins (two years of
  history, including the winter dates the skeptic flagged) most combinations lead last value at
  every level (rec_dir5 28.5 / 17.2 / 8.9 vs 30.4 / 19.9 / 13.1); in the 12 origins of 2025 they
  tie. Not significance-tested; the forward tracker is the test.

## Open blockers (not findings; test plan Phase 0, `docs/FORECAST_TEST_PLAN_V12.md:42-44`)
- **Oracle doors reverse between levels.** They help at item-week (25.2 vs 33.4) and hurt
  at portfolio-month (19.2 vs 17.5). Unexplained.
- **Retransformation bias.** Velocity models run at 0.62–0.65 vs 0.886, because the median
  of log1p(velocity) × doors ≠ mean units. Fix with Duan smearing or tweedie before
  model-based velocity arms.
- **The model is worse than flat on 52+ wk series** (34.7 vs 29.9, item-week), where it
  should be strongest.

## Method rules: SETTLED (each learned from a reversal)
- **Score every arm at all 3 levels.** Anchor seasonal mode was 1.17pp at item-week and
  8.28pp at portfolio-month (README 226, :114).
- **Break every arm out by history band.** The pooled conn_L4W result hid a 7pp loss
  (<13 wks) and a 12.5pp win (52+) (README 227).
- **Assert harness parity at import.** The backtest refreshed roll/wow features that
  production freezes: 11.83pp, and 2 conclusions inverted (MO_118, README.md:353).
- **Teacher-forced evaluation can't answer questions about a recursive forecast.**
  MO_27b's "+8.53pp hurt" was a trough artifact; recursive showed −2.65pp help
  (README.md:2277).
- **Never compare a median-across-series number to a volume-weighted one.** State the
  metric and the population every time (README.md:746).
- **Never call a mechanism on one fold.** A linear_tree single-fold "win" reversed across
  all 4 folds (README.md:1128).
- **Decompose any "seasonal" miss** into existing-series error vs cells unseen at forecast
  time. A median 14.4% of T+3 volume comes from unseen cells (MO_91/92, README.md:1426).
- **Re-derive the q90 conformal constant every retrain.** It was 1.0124× at v3 and
  1.0059× at v4 (MO_67).
- **Only cite ROBUST causal verdicts.** Of 140 significant events, 29% ROBUST and 62%
  FRAGILE (MO_60, README.md:5858).
- **Drift: judge slope, not level.** The Bulk-Growing "drift" was year-1 data maturity, not
  drift (MO_68).

## Current forecasting position (corrected harness): PROVISIONAL
- **MO_126 · route the anchor by history band.** conn_L4W vs model by band:
  - <13 wks: +6.95 (worse)
  - 13–25: −3.64
  - 26–51: −6.18
  - 52+: −12.49 (better)

  Same shape at portfolio×month. Route <13 → last value (production, validated) and 26+
  → conn_L4W. *Reopen if:* the 13–25 boundary sweep, or a blend in that band
  (README 227).
- **MO_125 · conn_L4W** (trailing velocity × current doors × seasonal) beats flat and the
  model pooled at all 3 levels, e.g. portfolio×month 10.7 vs 16.0 / 11.8, with bias
  1.029. Ship alone, not blended. *Caveat:* portfolio-month n=21. Superseded in part by
  MO_126's band split.
- **README 223 · the model beats flat only at portfolio×month** (4.2pp, 26% relative).
  Account×month is the uncomfortable middle (flat 23.1 vs model 24.7). Not split by band
  (README.md:290).
- **Exclude BAR from training:** −1.34pp, all 7 quarters. Exclusion is preferred over
  per-brand models (−1.14pp). Pooled; levels not stated (README.md:328).
- **Seasonal multiplier: anchor mode is best** under the corrected harness (40.08 vs
  41.25 shipped). Chain: README 219 claim → 220 "catastrophic" → 222 parity fix
  re-reversed it.
- **MO_115 · base units per store per week** has more repeatable YoY seasonality than raw
  units (+0.249 → +0.367; Kroger −0.393 → +0.424). Kroger's "chaos" was distribution
  growth. FACT-grade (panel).

## Forecasting, before the correction: PROVISIONAL (*reopen if*: re-run under parity, by band)
- **MO_79 · cold start:** naive_last wins every band and 3 of 4 cutoffs. The lifecycle
  ramp loses in every band (+21–23% bias), and the donor surrogate's edge is a confound.
  MO_126 later re-validated last-value for <13 wks.
- **MO_107 · method-selection oracle** is only 2.38pp above flat. Routing among
  *existing* methods captured none of it. Hierarchical top-down fails. Croston doesn't
  apply (0% intermittent). Note: MO_126's band routing of a *new* estimator is a
  different question.
- **The tally of what flat beats** (README.md:1709):
  - 6 seasonal arms, raw week_of_year, TDP projection, lifecycle ramp, donor surrogate,
    hierarchical allocation
  - targets: log1p, ratio13, ratio52, differencing
  - objectives: quantile, l2, huber, poisson, tweedie, mape
  - models: Ridge, Lasso, N-BEATS
- **MO_103 · direct beats recursive at every horizon** (32.83 vs 36.44, flat 32.95).
  Recursion does *not* compound error; it costs a roughly constant ~3.5pp.
- **A short-horizon hybrid** (model → flat at k) is worse than both, and k has no stable
  crossover. Drop it, don't tune it.
- **MO_104 · SES ties flat** (α → 1). **MO_95/105 · the TDP-unfreezing oracle ceiling**
  is 0.6pp, replicated portfolio-wide.
- **MO_97/98 · linear_tree** is +3.51pp worse. **Capping each forecast at 1.5× the series
  max** is −0.45pp across all folds. *Reopen if:* testing 1.2–1.3× caps.
- **MO_27g · TDP projection** moved the flattening ratio 0.062 → 0.064: the loop can't be
  patched. Consistent with replacing it (conn_L4W).
- **MO_28R · Optuna headroom** (2.6pp) was measured on the recursive objective. It doesn't
  transfer to direct or anchor architectures.
- **MO_29 · early stopping** fires at about 4,593 trees (lr 0.04, 63 leaves). Any nonzero
  min_delta is worse. Set n_estimators by compute budget. *Reopen if:* 3-fold CV confirms.
- **Q4 2025 miss** (~41%): lag52 under-anchors a brand 3–5× bigger than a year earlier.
  It needs a velocity-per-TDP view (README.md:3063).
- **MO_76 · macro (FRED/EIA) features:** no single winner, and the group gain sits in one
  window. Archived. *Reopen if:* 2+ more years of data.

## Features and Mo signals: PROVISIONAL (earlier 28-feature model; current v9 has 56 features)
- **MO_52–57 · feature engineering closed on the MO_53 28-feature champion** (CV 6.448%).
  Tested and rejected:
  - holiday flags (+0.05–0.15pp, MO_54)
  - Fourier encoding (+0.16pp)
  - lag2 and lag3
  - built_tdp_share
  - brand-split donor counts
  - percentage promo thresholds
  - static cannibal_prob

  *Reopen if:* a different model or architecture, or a re-score by band × level.
- **MO_96 · do not re-add** pack_count, own-brand donor features, or built_tdp_share:
  three implementations negative (README.md:1226). *Open:* pack as a prior on growth
  (a target change).
- **MO_41/50/56 · Mo signals are lagging indicators.** AR lags already encode them, and
  they hurt wMAPE pooled. Use them for explainability and scenarios, not accuracy.
  *Reopen if:* <13 wk band, where MO_51 found +1.3pp in a low-data cutpoint
  (README.md:7231).
- **Feature hygiene:**
  - price guardrails on $/bar, not raw ARP
  - cannibal signal = `cannibalization_rate_weekly` with null → 0
  - elasticity as `arp_pct_change × coef`
  - clip pct_chg to [−1, 2]
  - focal pct_chg columns are structurally NULL; drop them

## Elasticity, promo, causal: PROVISIONAL
- **MO_44:** portfolio ATE −0.34 (CI −0.37 to −0.31), 4/4 refutations.
  **MO_61:** elasticity varies 2.5–3.5× by pack, maturity and season. The mid-pressure
  ε ≈ −1.0 is n=790, so treat with caution.
- **MO_16/44:** AHOLD positive elasticity is a CRMA aggregation artifact, not fixable by
  features. Vitamin Shoppe's positive ε is real (clearance).
- **MO_70:** promo lift is under-predicted about 2× (structural). The fix is UI
  disclosure. **BSTS:** price-event direction is right 63% of the time on clean moves,
  but magnitude is worse than naive, so claim direction only.
- **MO_20/73 · lift ladder:**
  - discount depth: <10% → 20%, 10–20% → 31%, 20–30% → 46%, 30%+ → 76%
  - c-store singles are flat
  - grocery 12pk hits a cliff at 30%
- **MO_55:** the zero-sum portfolio cannibalization layer moves 1.18% of units. Its value
  is unvalidated. *Open:* thresholds (30% / 20% / wsl ≤ 26).

## REVERSED: do not cite
- **"5× (or 6×) better than foundation models"** (MO_62). The Mo number was a hardcoded,
  leaked constant. Honest rerun: 1.1pp, and flat beats both Mo arms volume-weighted
  (MO_106, README.md:728). Still in the FP&A report and the Mo Chat glossary (:6447).
  Also re-verify the 8× / 6× / 10–30× architecture multiples before citing.
- **MO_63's 2.02–5.71% CV and the "accuracy compounds over time" claim**
  (README.md:6441, :6764). Teacher-forced: one-shot predict with actual lags. Same class
  as the retired 3.4–4.3%. Still in the Mo Chat glossary.
- **Retired accuracy figures:**
  - 2.3% (Kroger, teacher-forced) → 13.8% recursive (README.md:3259)
  - 15.5–15.7% headline: 6 of 7 quarters were leaked
  - honest: 32–41% (README.md:1943)
- **"4.15% teacher-forced vs 37% recursive" as a modelling insight.** Contamination plus
  freeze is an accidental level anchor (MO_118, README.md:385).
- **MO_117 two-stage "closed on 0.61pp"** and **MO_123 "L4W loses 17pp"** (straw man).
  Both overturned by MO_125.
- **"91.9% BAR exit rate" / brand predicts exit** (README 221). An artifact; 13-wk
  survival is 99.5% (README.md:333).
- **"Halves naive error"** (MO_92) was withdrawn (README.md:1502). Not reconciled:
  MO_92's "flat beats the model at portfolio-month" vs README 223's model +4.2pp there.
- **"Coherent" TDP unfreezing** was a free win at Kroger only (README.md:838). **SES beats
  flat by 1.7pp** (README 206) didn't replicate.
- **geography_raw as a feature** (README 190/194): phantom AK/HI rows. Filter them
  instead (README.md:2770).
- **Meijer = MULO CRMA** (README 159): wrong. Meijer is RMA CONVENTIONAL|FOOD. *Open:*
  re-verify the Meijer cannibalization brief.
- **"Index built from 3 series" / "October peak is a CRMA artifact"** (ANO-08): both wrong
  (ANO-10).
- **Lifecycle ramp, donor surrogate, TDP projection as #1 fix**: all rejected
  (MO_79, MO_27g).

## FACT: data, panel, infrastructure, design
- **SPINS semantics:**
  - `total_units = units`; base + units_promo is wrong on 67% of rows (README.md:6927)
  - `units_promo` is not incremental; `incr_units` is
  - `base_units` is the MRM baseline; say "SPINS-defined baseline"
- **Panel rules (`scripts/mo_panel.py`):**
  - RMA priority over CRMA (CRMA was a ~7.3× double-count: 515.7M → 70.5M bars/yr)
  - exclude military
  - drop zero-volume geographies
  - promo nulls → 0 only if no promo ran
- **Brand and flavour:**
  - filter `parent_brand = 'BUILT'`, not `source_brand` (2 vs 146 UPCs)
  - feature: `spins_flavor_canonical`
  - never `spins_flavor_mapped`
- **Growth is distribution:** 61% of 52-wk growth is new series, and continuing series grew
  1.46×/yr. TDP grew 7.9×, all of it in the launch ramp. Flat × growth double-counts.
- **No series had 104+ weeks** at the Q4 2025 cutoff. ETS, Theta, MSTL and SARIMA fail
  outright.
- **YoY seasonal shape barely repeats:** median r = +0.079, and only 4% of series exceed
  0.6. The seasonal index is volume-weighted over all qualifying series (peak wk10
  +0.199, trough wk52 −0.190). Single-series STL is unstable. Version-control the index
  CSV.
- **Constant-leaf GBDTs can't extrapolate** above their training max (39% of Q1 2026
  volume). `monotone_constraints` is unusable with the quantile objective.
- **BUILT's "~7%"** is total (bias) error: we're at 0.3–1.6% on that measure, against
  ~36% per-item wMAPE. *Open:* BUILT's exact definition.
- **The door-count / planned-distribution data ask is dead:** a 0.6pp ceiling, and BUILT
  ships to warehouses.
- **Costco CRX:**
  - a separate Circana product (pallet multiples of 525)
  - MVM can't be derived from CRX rows (promo and sales sit on separate rows) → join a
    promo calendar
- **Retailer data classes:** 1 SPINS, 2 Circana/Costco, 3 own-portal, 4 dark (estimate;
  never fabricate ACV). PRIVATE LABEL isn't a brand.
- **Druid:**
  - only `REPLACE … OVERWRITE WHERE` is safe on spins_full
  - top-level ORDER BY is `__time` only (sort in Python)
  - EXTERN and the Lookup API are forbidden
  - numerics arrive as object dtype → `to_numeric`
  - write timestamps as ISO strings
  - `SELECT * LIMIT 1` before new scripts
- **Code traps:**
  - `max(0, nan)` = 0, and NaN is truthy (`str(nan or "UNKNOWN")` = "nan")
  - a bare `except: pass` hid a Druid 400
  - MIN_WEEKS at extract hid 7,291 series → filter downstream
- **MO_27 production:**
  - the <13 wk rule is a method router, not a coverage gate
  - `LAPSE_WEEKS = 9` → forecast 0
  - no ETS in production, and MO_75 doesn't exist
  - coherence clamp total ≥ base (MO_58); re-verify each retrain
- **MO_62/65 benchmarks used MIN_HISTORY = 52.** They say nothing about cold start.
- **Product design:**
  - Mo never shows empty results
  - FULL / PARTIAL / EARLY tiers (13+ / 8–12 / <8 wks)
  - training ≠ inference population
  - build Druid feature tables, never raw rows
- **Mo Chat:** tool use needs a 7–9B+ model. Mistral 7B is limited to 1 tool call.
