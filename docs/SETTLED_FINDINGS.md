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

### Added 2026-10-10 from MO_134 (recursive fair settings; 18 origins; README 235), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss % (lower is
better) at item x week / account x month / portfolio x month, existing series, 13+ week series
unless stated; * = interval excludes zero. Pre-registered P1-P7 in f1a2ed2.
- **(a) Removing the 0.5-2.0 year-over-year clip is harmful, but the size is an artifact.**
  Current recursive model 35.46 vs no clip 48.70 (+13.24). 95% of that comes from 116
  series-origins whose year-ago week predates distribution (1-20 units at TDP 0.0-0.3, ratios
  200-1,375); one Publix series is 45% and the top 20 series are 90%. Where year-ago TDP was at
  least half of current (3,820 series-origins) no clip costs only +0.14. The clip binds for 59% of
  series (median ratio 1.33), so it acts as a crude guard against distribution change. Do not
  quote 48.7 as the cost of removing it. Next test: a per-store (TDP-normalized) year-over-year
  ratio (MO_135). The fair-settings arm (no clip + calendar year-ago + 3x safety rail) 37.78 is
  significantly worse than the current model only at item x week (+2.32 [+0.7, +3.8]*).
  *Skeptic: SURVIVES WITH CAVEATS.*
- **(b) Calendar-aligned year-ago ties:** -0.05 [-0.3, +0.1]. Production's row anchor
  `hist[n-52]` is 51 weeks back even without gaps (MO_27:570, MO_80:790), an off-by-one; fixing it
  ties. *Skeptic: SURVIVES.*
- **(c) Tree cap of 20,000 makes no difference** (+0.00; median forecast change 1e-4). 9 of 18
  origins trained past 6,000 trees, so P3 half-fails as registered. The `hit_cap` flag
  under-reports (MO_80:386 tests best >= cap; 10 of 18 fits stopped at 5,963-6,000). Fix on the
  report side (editing `train_like_production` busts the model cache). *Skeptic: SURVIVES.*
- **(d) Recency weight 0.02 and blend weight 0.10 are "not beaten", not "best".** Item x week:
  recency 0 / 0.01 / 0.02 / 0.04 = 35.67 / 35.57 / 35.46 / 35.69; blend 0 / 0.05 / 0.10 / 0.20 /
  0.30 = 35.73 / 35.51 / 35.46 / 35.75 / 36.38. No blend difference is significant; blend 0.30 wins
  4 of 5 history bands at band-separated portfolio x month (only the 52+ band makes 0.10 win
  pooled); the recency sweep is non-monotone (0.01 significantly worse, 0 and 0.04 not), which is
  training-path noise. *Skeptic: SURVIVES WITH CAVEATS.*
- **(e) The recursive model passes the ORIGINAL production-decision rule against the served direct
  model, but this does not support switching production.** Overall: recursive 35.46 / 22.89 /
  13.75 vs served direct 40.53 / 24.59 / 13.17 (item x week -5.07 [-12.46, -0.76]*; all 5
  criteria pass). Criterion 4 (seasonal bias) passed by 0.0012 (Jan-Mar 2026 bias 0.9012). The win
  is all in the 2025 origins: 2024-12 to 2025-10 the recursive model is better by -12.08* / -8.48*
  / -5.33* (three values as logged); 2025-11 to 2026-05 it is WORSE (+1.87 / +5.17 [+0.8,
  +11.3]* / +6.59, account x month), ahead at only 1 of the last 6 origins (post hoc split). The
  win comes from the under-13 and 52+ week bands; Walmart is -2.2 of the -5.07. The fair-settings
  arm does not pass criterion 1. Pre-registered predictions: P1 FAILS (clip matters), P2 HOLDS, P3
  half-fails, P4 FAILS (0.02 not uniquely best), P5 HOLDS, P6 HOLDS, P7 FAILS. *Skeptic: SURVIVES
  WITH CAVEATS.* Do NOT switch production on this evidence.
- **(f) No recursive variant beats last week carried forward on 13+ week series.** Last value
  32.59 / 21.12 / 12.84 vs current recursive model 35.46 / 22.89 / 13.75 (+3.63*; last value
  better at 16 of 18 origins). Pre-registered P6 HOLDS. *Skeptic: SURVIVES.*
- **Decision (Jason, 2026-10-10):** accuracy for 2026-2027 matters most to BUILT; consistency is
  valued; 2025 answers "would it have worked" (limited PUFF history). Production Decision
  Amendment 1 (`docs/PRODUCTION_DECISION_PREREG.md`, bad2659, written before any forward week is
  scored): evidence order is forward weeks, then recent backtest dates (2025-12 on), then 2025 as
  a no-harm check only (within 2 points at account x month). Replace the status quo only if
  better at account x month and band-separated portfolio x month on recent dates and not worse at
  item x week; consistent at 5 of 6 recent dates at account x month; seasonal bias rule; forward
  confirmation after at least 3 scored saves; tie-break consistency then simplicity. Named
  candidates: 5-seed direct average (direct_avg5), recursive + fixed direct (rec_dir5), served
  direct (status quo), recursive, L4W velocity x stores, last week carried forward.
- **EXPLORATORY, post hoc, NOT a finding (6 overlapping 2026 origins, 2025-12 to 2026-05,
  existing series):** direct_avg5 is best at account x month (16.2) and portfolio x month (6.5);
  recursive + fixed direct (rec_dir5) beats last week carried forward at account x month at 6 of 6
  dates (17.2 vs 19.9); recursive alone is worst (22.5 / 14.1; 0 of 6 vs last value). In 2025
  recursive beat direct; in 2026 direct beats recursive. Not significance-tested; the forward
  tracker is the test.
- **Corrections to Claude's preliminary statements (withdrawn after the skeptic):** "removing the
  clip makes forecasts much worse (48.7)", "current settings are best", and "the recursive model
  passes the rule, which supports switching".

### Added 2026-10-12 from MO_135 (per-store year-over-year ratio; 18 origins; README 236), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss % (lower is
better) at item x week / account x month / portfolio x month, existing series. Pre-registered
P1-P5 in 6c5332e. Recent = 6 overlapping origins, 2025-12 to 2026-05 (exploratory).
- **(a) A per-store year-over-year ratio gives no accuracy gain; the protection against the
  no-clip blowups comes from the store-count gate, not the ratio (gate-only test pending).**
  No overall harm: per-store ratio without clip 35.49 vs current model 35.46 at item x week
  (P1 HOLDS), and no detectable difference: per-origin recent account x month, rec_vel minus rec,
  -1.24 / +1.70 / -0.18 / +0.51 / +0.53 / -0.56 (3 of 6 each way; P2 FAILS, +0.08). But the
  mechanism claim FALLS: the blend fires on about 30% of series-origins; the distribution-index
  gate above 1.0 (MO_80:803-811, seasonal-trend fallback :861) removes 89.3% of MO_134's no-clip
  excess, and where the per-store ratio fires on those series it is still worse than the clipped
  ratio (+0.23 at item x week). Confound: ratio, calendar alignment and gate changed together.
  Next test: units ratio + store-count gate, no clip. *Skeptic: SURVIVES WITH CAVEATS (no harm
  and no difference survive; the mechanism falls).*
- **(b) Block-bootstrap intervals on fewer than 10 origins are invalid in MO_80** (4 blocks of 3
  over 6 origins gives only 10 distinct resamples, MO_80:1147-1153). Use per-origin values and
  the exact sign test (MO_133 rule e-ii); do not quote the printed intervals for recent-origin
  comparisons. *Skeptic: confirmed.*
- **(c) The 30% seasonal pull (blend weight 0.30) is a level shift, not a shape change.**
  rec_vel_w30 over rec is a near-uniform 3-8% upward shift. Jan-Mar 2026 bias 0.968 vs 0.901
  (P5 holds literally) but Oct-Dec 2025 bias 1.111 vs 1.058, which would fail production
  criterion 4 against rec. Do not cite as a seasonal improvement. *Skeptic: FALLS as a seasonal
  fix.*
- **(d) direct_avg5 fails Amendment 1 consistency (4 of 6 recent dates at account x month vs 5
  required); criterion 4 passes by only 0.0007.** Recent: direct_avg5 28.79 / 16.17 / 6.45 vs
  served direct 32.42 / 16.99 / 8.26 (band-separated pm -1.18, cw -3.63); 2025 no-harm passes.
  It loses 2025-12 (+2.65) and 2026-01 (+1.79) (5 of 6 without Walmart). Oct-Dec 2025 bias
  1.0993; 3 of 5 single seeds would fail. Its lead is in young bands (am under-13 -4.79, 13-25
  -3.11, 26-51 -0.19, 52+ +0.19). rec_dir5 and velw30_dir5 fail criterion 1; vel_dir5 and
  velw30_dir5 are not named candidates in `docs/PRODUCTION_DECISION_PREREG.md`. No production
  switch. Related: recursive-alone settings tested are exhausted on 13+ week bands (0-1 of 6 vs
  last value at account x month; under-13 band excepted); combination wins over last value (6 of
  6) depend on Walmart (4 of 6 without; lead -2.64 to -1.31); direct_avg5's 2025 'best at pm' is
  pooled cancellation (+2.44 worse than last value within bands). *Skeptic: SURVIVES WITH
  CAVEATS.*
- **Corrections to Claude's preliminary statements (withdrawn after the skeptic):** Jan-Mar 2026
  under-forecast went "from 10% to about 3%" (a level shift, not a seasonal fix) and the per-store
  ratio is "a safe replacement for the clip" (the gate does that job).

### Added 2026-10-12 from MO_136 / MO_136b / MO_137 (category, other-retailer, 26-week and post-expansion fade signals; README 237), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss % (lower is
better) at item x week / account x month / portfolio x month, existing series. Pre-registered
predictions: MO_136 in bf33de5, MO_137 and its 'beats' definition in e80fd81; `all_avg5` and
`fade_avg5` named in `docs/PRODUCTION_DECISION_PREREG.md` before results. Recent = 6 overlapping
origins, 2025-12 to 2026-05 (exploratory; sign-test p-values optimistic).
- **(a) MO_136 category, other-retailer and 26-week signals: no pass. The category portfolio gain
  is Walmart-only.** Recent: direct_avg5 28.79 / 16.17 / 6.45; cat2 28.93 / 16.08 / 5.62;
  xret2 29.47 / 16.28 / 6.95; l262 29.16 / 15.81 / 6.63; all_avg5 28.85 / 16.04 / 5.83 (parity
  exact). Category pm-by-band -0.76 at 5 of 6 dates, but Walmart alone is -1.47 and without
  Walmart -0.17 (seed noise); account x month wins 2 of 6. Other-retailer signals hurt: 13-25
  week band worse at 16 of 18 dates (+0.95 vs noise +0.10 to +0.35); account x month 1 of 6 is
  Walmart-driven (5 of 6 without Walmart). 26-week signals: no effect. all_avg5: pm-by-band
  -1.62 at 6 of 6 dates (dates overlap), robust across seeds, halves without Walmart (-0.81),
  per-date band wins 13-25 weeks 4 of 6 and 26-51 weeks 3 of 6; '2025 no harm' hides a 26-51
  week band loss (+1.9 am), 72% from one Walmart item (08-40229-30558 at 2025-07, all_avg5 226k
  vs 362k, actual 418k, caused by the other-retailer signals). No production switch:
  all_avg5 fails consistency (3 of 6 at am) and criterion 4 (Oct-Dec 2025 bias 1.1019, margin
  0.002; 1.073 without Walmart would pass), so Walmart decides the outcome. 'Keep category,
  drop other-retailer' is NOT supported. *Skeptic: SURVIVES WITH CAVEATS (C2 category-to-pm,
  C3 other-retailer hurts, C5 and C6 with the Walmart splits; C7 'keep category, drop
  other-retailer' FALLS as worded).*
- **(b) MO_137 post-expansion fade signals: no pass.** Recent with Walmart: direct_avg5 28.79 /
  16.17 / 6.45; fade_avg5 28.71 / 16.48 / 6.71 (am worse; wins 2 of 6; pm-by-band -0.21 is one
  date, 2026-01). P3 FAILS, P5 FAILS (Walmart recent am 16.60 -> 19.10), P2 holds literally
  (Walmart Oct-Dec 2025 bias 1.210 -> 1.196), P4 holds (all-origin cw 34.08 vs 34.15). Fails
  criterion 4 (Oct-Dec 2025 bias 1.1005 vs served 1.0617). 'Helps without Walmart' is NOT
  settled: within-band am -0.11 (4 of 6), Target + Sam's are 56% of the gain, it reverses in
  2025 (worse without Walmart 9 of 12 origins, better at Walmart 9 of 12). 'Fade except Walmart'
  would be post hoc. Walmart loss mechanism: the signals remove an offset between under-forecast
  young items and over-forecast established items in the account total (2026-01 total bias 0.991
  -> 0.917 while cw -1.47 and within-band am -3.07 improve). *Skeptic: only C1 (parity) and C2
  (P3 fails) stand; C3 FALLS as worded; C4 number survives, mechanism rewritten; C5 FALLS.*
- **(c) Reporting rule: always report results without Walmart and within history bands per date,
  because pooled account totals can be right by offsetting item errors across item ages.**
  Walmart (27% of recent volume) decided the MO_136 category result, the other-retailer
  account-level result, the no-switch outcome and the MO_137 comparison. Also check a sub-group
  split (Target and Sam's) and the 2025 origins before calling a gain consistent. The underlying
  defect to examine next is age-dependent bias (young and growing items under-forecast,
  established over-forecast). *Skeptic: supported by C2, C5, C6 (MO_136) and C3, C4 (MO_137).*
- **(d) Walmart grows in step-change expansions followed by velocity fade (descriptive, MO_136b;
  not skeptic-reviewed on its own).** Expansion 2025-08-17 (about 100k to about 190k a week, TDP
  about 340 to about 600), fade about 40% through Q4 at flat TDP (117k by late December), second
  expansion 2026-01-18 (TDP 736 -> 1,104; about 250k), fade to about 214k by late April. Walmart
  counted once (38 series, RMA). H1 and H3 fail, H2 is not Walmart-specific (43% vs 46%), H4
  holds (Oct-Dec 2025 every model over-forecast Walmart, 1.13 to 1.27). The MO_137 skeptic
  qualified the implication: 'history cannot anticipate the next expansion' and 'Walmart needs
  planned-expansion inputs from BUILT' are hypotheses, not shown.
- **Corrections to Claude's preliminary statements (withdrawn after the skeptic):** MO_136:
  category signals help portfolio totals "in every item-age group" and "keep category, drop
  other-retailer". MO_137: the fade signals "help every retailer except Walmart (6/6)" and
  Walmart's loss "comes from missing the January expansion".

### Added 2026-10-12 from MO_137b / MO_138 (item-age bias diagnostic and age x weeks-ahead correction; README 238), PENDING review
Each proposal carries the skeptic (opus/high) verdict line: SURVIVES WITH CAVEATS overall; MO_138
fails. Numbers are average miss % (lower is better) at item x week / account x month / portfolio x
month, existing series. MO_138 design, 'beats' definition and predictions P1-P5 committed in 111f842
before the run; `cal` named in `docs/PRODUCTION_DECISION_PREREG.md` before results. MO_137b outputs
were written before its commit (62d15b6), after two buggy runs, so its hypotheses are NOT proven
pre-registered: descriptive only. Recent = 6 overlapping origins, 2025-12 to 2026-05 (exploratory).
- **(a) MO_138 age x weeks-ahead correction (multiply direct_avg5 by factors learned only from
  earlier forecasts): no pass. Lagged cumulative factors carry seasonal misses forward.** Recent:
  direct_avg5 28.79 / 16.17 / 6.45; cal 28.87 / 16.76 / 6.96; cal_age 29.04 / 16.58 / 6.43. P2, P3,
  P4 FAIL (P3: <13-week cw 52.74 -> 56.20; P4: 2025 am 24.51 -> 28.90); P1 (recent <13 bias 0.865 ->
  0.992) and P5 hold. cal is worse in the <13 and 13-25 week bands and better in 26-51 (am 14.1 ->
  12.4) and 52+; without Walmart am is worse on all 6 dates; 2025 harm is largest in 52+ (am 29.4 ->
  35.1); Oct-Dec 2025 bias 1.099 -> 1.220. The factors absorbed the portfolio-level seasonal miss
  (all-band weeks 10-13 factor 2.09 at 2025-03 -> 0.95; 52+ relative factor stable 0.96-1.10), kept
  by a cumulative learning window with no recency weighting; an in-sample oracle would cut 2025 am
  24.51 -> 19.95 (diagnostic only). *Skeptic: C1 (no leakage) SURVIVES; C2 SURVIVES WITH CAVEATS; C3
  as originally worded ("age bias is unstable") FALLS and is rewritten here.*
- **(b) The recent young-item under-forecast is Walmart-specific (new items in Walmart's January
  2026 expansion); the 2025 young-item under-forecast is general (descriptive, MO_137b).**
  Recent <13-week bias 0.865; three Walmart items (08-40229-30652, 30680, 30678) are 71% of the
  1.17M net shortfall (top 5 items 87%); without Walmart 0.976 with no weeks-ahead slope; Walmart
  young items 70% of rows under, median actual/forecast 1.38. 2025 holds without Walmart (0.805,
  0.842 -> 0.764 with weeks ahead; median young item 1.077). 'Last value / L4W over-forecast young
  items' is recent only (2025 0.965 / 1.009). 28.7% (recent) / 16.1% (2025) of age-group error
  cancels inside account totals (13-48% per date). Outside Walmart, recent <13: 49% of rows under,
  51% over; median ratio 0.978 vs ratio of sums 1.156. 'Not a fixable bias' is WITHDRAWN: it is the
  existing open blocker "Retransformation bias" (below; direct model is q50 on log1p, MO_132:170),
  and the first test is its named remedy (Duan smearing or tweedie; MO_139). 'Forecast totals
  directly / mean objective' is an untested hypothesis and must be read against MO_107
  (hierarchical top-down fails) and the PROVISIONAL objectives tally (flat beats quantile, l2,
  huber, poisson, tweedie, mape). *Skeptic: D1 SURVIVES WITH CAVEATS; C4 holds only for recent <13
  outside Walmart; C5 FALLS as an implication.* Idea to verify, not a finding (Jason): BUILT often
  ships to wholesale distributors, so planned-expansion inputs may not exist for many accounts;
  NetSuite shipments might lead SPINS sell-through.
- **(c) Process rule: commit diagnostic scripts before running them too.** MO_137b was run before
  its commit (outputs 13 s earlier, after two buggy runs), so its hypotheses cannot count as
  pre-registered. Extends the pre-registration rule from experiments to diagnostics.
- **Corrections to Claude's preliminary statements (withdrawn after the skeptic):** new items are
  under-forecast 13-15% "consistently" (recently three Walmart items; outside Walmart it held in
  2025, not recently); the factors were unstable because the age bias drifts (it was the Q1-2025
  seasonal miss carried forward); "a trade-off, not a fixable bias" with totals forecast directly
  (overreach; retransformation-bias remedy first); MO_137b run before commit (process slip).

### Added 2026-10-12 from MO_139 (Duan smearing and Tweedie for the units direct model's log-scale bias; 5 seeds; 18 origins; README 239), PENDING review
Each proposal carries the skeptic (opus/high) verdict line: DOES NOT SURVIVE as first written; the
corrected reading is below. Numbers are average miss % (lower is better) at item x week / account x
month / portfolio x month, existing series. Design, 'beats' definition and predictions P1-P5 committed in
9b4dc6c before any run; `smear_avg5` and `tweedie_avg5` named in `docs/PRODUCTION_DECISION_PREREG.md`
before results. Recent = 6 overlapping origins, 2025-12 to 2026-05 (exploratory). Parity: the smearing
arm's plain path equals MO_133 `direct_fixed` exactly for all 5 seeds (the Tweedie arm has no parity anchor).
- **(a) MO_139 Duan smearing as designed (unweighted mean of exp(log residuals) on the 13-week check
  period, by item age and weeks ahead, capped 0.8-1.6) fails; volume-weighted smearing is untested.**
  Recent: direct_avg5 28.79 / 16.17 / 6.45 (bias 0.970); smear_avg5 48.98 / 33.01 / 27.73 (1.277). 2025:
  38.40 / 24.51 / 11.29 vs 58.14 / 45.08 / 37.03. All 18: 34.15 / 20.85 / 9.17 vs 54.08 / 39.78 / 32.95.
  Account x month wins 0/6 recent dates (also without Walmart and within bands); recent bias by item age
  1.259 / 1.283 / 1.276 / 1.395. The factor is at the 1.6 cap on 41% of rows (36% by volume; 78% at
  2025-12, 77% at 2026-03, 17% at 2026-05); mean factor 1.14 at 1 week ahead (6% capped) to 1.45 at 13
  weeks ahead (56% capped). Diagnostic on scored actuals (check residuals not saved): unweighted mean
  (1+actual)/(1+forecast) 1.27 at 1 week ahead to about 4 at 13 weeks ahead, while the volume-weighted
  ratio is 1.005-1.055 at every step; "drift" is NOT supported. Grouping mismatch: weeks since launch for
  smearing vs history band for scoring; the "check period" at h weeks ahead is the last h forecast
  starting points only. *Skeptic: C1 parity SURVIVES; C2 SURVIVES WITH CAVEATS (this estimator fails,
  not smearing in general); C3 SURVIVES WITH CAVEATS (cap share and low-volume ratios yes, drift no).*
- **(b) Tweedie (raw units, power 1.5) vs median-on-log for the units direct model: better on 2025 dates,
  worse on recent dates, so decide by forward weeks (`tweedie_avg5` added to the forward set).**
  Recent: tweedie_avg5 33.70 / 19.40 / 10.74 (0.941); 2025: 36.72 / 23.91 / 9.89 (0.936) vs direct_avg5
  38.40 / 24.51 / 11.29. 2025 gain is broad (cw 8/12 dates, within-band pm 9/12) but small at account x
  month (7/12; 5/12 without Walmart); both Tweedie and smearing lose to flat in 2025 at cw and am. Recent
  loss: cw worse without Walmart on 6/6 dates; the recent am loss rests on 2026-03 (and 2025-12);
  within-band pm worse regardless. The recent <13-week total (bias 1.021 from 0.865) is cancellation:
  Walmart 0.872, all other retailers 1.083 (direct_avg5 without Walmart 0.976). Reversal, Tweedie minus
  direct_avg5 at cw without Walmart (<13 / 13-25 / 26-51 / 52+): recent +3.71 / +2.65 / +3.99 / +4.70;
  2025 -1.31 / -0.69 / -3.58 / -1.18. Neither objective is clearly better. *Skeptic: C4 partly FALLS; C5
  FALLS as written (reverses by period). P2 holds only as written (one-sided; intent fails); P5's bias
  half fails without Walmart.*
- **(c) Process rule: bias predictions are two-sided around 1; act on smoke-test warnings before
  spending.** P2 ("<13-week bias at least 0.95") passed at 1.259 only because it was one-sided. The
  laptop smoke test (2025-01, seed 42) already showed the overshoot (total smear / base 1.249) and was
  not flagged before the worker spend was approved.
- **Corrections to Claude's preliminary statements (withdrawn after the skeptic):** the smearing
  overshoot came from small noisy items and drift (cap shares and low-volume ratios yes, drift no);
  Tweedie "fixed the new-item total" (Walmart 0.87 and the rest 1.08 cancel); the median-on-log approach
  is "the more accurate choice" (only on recent dates; on 2025 dates Tweedie wins every item-age group
  at item x week without Walmart); the open blocker "should be narrowed" (no: it concerns the velocity
  models, untested here).

### Added 2026-10-13 from MO_140 (fixed product attributes added to the 5-seed direct model) and MO_142 / MO_142b (Meijer brief v2 data; README 241), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Numbers are average miss % (lower is better) at
item x week / account x month / portfolio x month, existing series. Recent = 6 overlapping origins, 2025-12 on
(exploratory). MO_140 predictions P1-P5 committed in f71db5a before any run; MO_142 P1-P6 in 1003c88 and
MO_142b Pb1-Pb3 in d40e3ce before their runs.
- **(a) MO_140 (PROVISIONAL): static product attributes (product line, protein/sugar/calories, retail price
  per bar, exclusive-to-a-retailer flag) do not improve the fixed direct model for existing series.**
  Recent: direct_avg5 28.79 / 16.17 / 6.45 (bias 0.970); attr_avg5 28.79 / 16.30 / 6.65 (0.975). Account x month:
  all 18 dates 20.85 -> 21.05; 2025 24.51 -> 24.77; recent without Walmart 16.00 -> 16.23; better on 2 of 6
  recent dates (p=0.69), 1 of 6 without Walmart. Gains in young bands (under 13 weeks am 45.7 -> 45.2, pm 17.0
  -> 16.2; 13-25 weeks am 20.2 -> 19.8, pm 9.9 -> 9.4) are offset by worse older bands (26-51 pm 7.6 -> 8.1; 52+
  pm 6.7 -> 7.3). The under-13 item x week gain (52.7 -> 52.0) is 89% Walmart from two Sour Puff items
  (08-40229-30652, -30680, first sold 2025-12-28), fades by April-May 2026 and reverses in 2025. P1-P5 HOLD as
  written (P3 only with Walmart; ex-Walmart 0.12). Under Amendment 1 of `docs/PRODUCTION_DECISION_PREREG.md`: no
  pass, production unchanged. Caveats: brand-new items (no history at the forecast date) are forced to zero and
  not scored, so "new items borrow from similar products" is untested; attributes are a July 2026 snapshot;
  price per bar maps almost one-to-one to bars per unit, so it stands in for pack size (price itself untested;
  consistent with MO_96); exclusive flag mis-joined for UPC 08-40229-30413. Parity 0.000000. Code
  `scripts/MO_140_attributes.py`, worker jobs `jason-mo140-001` to `-003`, log `outputs/mo140_run.log`.
  *Skeptic: SURVIVES WITH CORRECTIONS.* *Reopen if:* a cold-start test (items with no history at the forecast
  date) or time-varying price data.
- **(b) MO_142 / MO_142b (PROVISIONAL; descriptive, not a forecast arm): in Meijer's own 280 stores (SPINS
  MEIJER CORP - RMA), the April 2026 Peanut Butter Cup (first sold 2026-04-19) and Cookies N Cream (2026-04-26)
  4-packs were mostly incremental in their first three months; the older three main 4-packs gave up roughly
  10-40 per 100 new packages; this is within the normal Food-channel range.** Launch cannibalization rate =
  (category-adjusted expected minus actual weekly base units of existing BUILT items) / new items' weekly base
  units; 13 weeks before vs weeks 2-14 after; placebo at fake launch dates; MO_142b judges existing items per
  store selling. Central estimates 0.37 (units) and 0.34 (per store), noise about +/-0.3, so roughly 60-90% new
  to BUILT; each older item gave up 12-16% of expected. Two items cannot be separated. Cookie Dough (April 2025)
  0.37 (weeks 2-14) -> 0.11 (15-27) -> 0.21 (28-40): the dip fades. Both launches were in April after the Q1
  peak with heavier promotions (seasonal timing untested). Other Food launches: median 0.47, middle half
  0.03-1.01; 11 of 28 single-launch rates below 0 or above 1; use the median, not the pooled rate. Placebo
  median absolute loss: Meijer 11.6%, Food 11.3% (12.1% per store); Mass 64.9% (42.8% per store), Drug 39.7%,
  Club 48.5%. Predictions: P1 HOLDS (0.369), P2 HOLDS, P3 holds trivially, P4 FAILS at the boundary (0.369 =
  Food 25th percentile), P5 HOLDS (-2.21, 90% -2.44 to -1.98), P6 HOLDS (-1.16, 12 brands), Pb1 FAILS (Mass
  placebo 42.8%), Pb2 HOLDS (0.343), Pb3 HOLDS (Food pooled per store 0.585, 28 events). Own performance: base
  units per Meijer store per week 1.7 (Q4 2023) -> 17.4 (Q3 2026, 10 weeks); share of bar units 0.4% -> 2.6%;
  per item per store selling peaked 5.6 (Q2 2025) -> 3.7 (3.8 without the August launches). Singles: two in
  about 15-20 stores Oct 2023-Apr 2024, then 1-2 stores. Not measurable with launch before/after data:
  Mass-channel launches (store expansions) and 4-count vs 1-count cannibalization (structural zeros; Publix
  July 2024 contradicts it). Code `scripts/MO_142_meijer_brief_v2.py`, logs `scripts/outputs/mo142_run1.log`
  and `mo142_run2.log`. *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* a planned singles test at Meijer, or 13+
  weeks after the August 2026 launches (SPINS through early December 2026).
- **(c) MO_142 price sensitivity (PROVISIONAL): a promotion response, not a shelf-price response.** ln(units
  per store selling) on ln(price paid per bar), item and week fixed effects, clustered by item, last 104
  weeks. BUILT at Meijer -2.21 (leave-one-out -2.11 to -2.37; the interval is too narrow, 8 items); BUILT about
  twice the typical protein-bar competitor; competitive-set median -1.16. Peer Food 4-count -2.64
  (leave-one-retailer-out -2.14 to -2.93) vs 1-count -1.02 (-0.78 to -1.19). Units on both sides bias every
  estimate negative; the ranking is fair. Regular price per bar: BUILT $2.28, Barebells $2.50, Quest $2.32, Pure
  Protein $1.73, Clif Builders $1.66. Keep price and cannibalization unlinked. The first brief's -0.489 differs
  in geography and method. *Skeptic: accepted (C7).*
- **(d) Do not reuse from the first Meijer brief:** MO_55's 46.9% (share of model-flagged pairs, not a measured
  loss) and "singles fully incremental / check-lane go".
- **Corrections (overturned by the skeptic):** C3, that Meijer is "more
  incremental" than other Food launches and shows a by-year trend (it is within the normal Food range); C5, that
  4-count packs cannibalize differently from 1-count packs (not measurable).

### Added 2026-10-13 (afternoon) from MO_141 / MO_141b (shipments forecast), MO_143 / MO_143b (singles analogs), MO_144 / MO_144b (new item x retailer series) and MO_145 (neural timing; README 242), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Miss = average miss % (lower is better); levels: item x
week (cw), account x month (am), portfolio x month (pm); recent = 6 overlapping origins, 2025-12 on (exploratory).
Predictions were committed before each run (MO_141 2cfb8c8; MO_143 8241e11 and MO_143b 33215d6; MO_144 bcdf014;
MO_144b 6f900c9; MO_145 6ced2bd).
- **(a) MO_141 / MO_141b (PROVISIONAL): monthly forecasts of billed shipments for the four data-dark retailers.**
  Scored from each account's regular-ordering start, through Jul 2026, 3-month totals. ALDI (regular since 2025-08,
  7 dates): average of the last 6 months 15.3% (bias 1.09), of the last 3 months 19.0%, a usable placeholder. WinCo
  (23 dates): avg6 45.2% (bias 0.84), seasonal_trend 46.7%, avg3 52.6%, last month 78.4%; the ranking is unstable, so
  WinCo is not plannable from shipments alone. H-E-B (regular since 2025-11, 4 dates): too few to rank. Trader Joe's
  June 2026 (2.52 million bars, 27 orders over 9 days to 6 distribution centers, about $3.4M) is a one-time
  load-in, excluded. The "replenish" method was dropped as not a valid test (it under-forecasts by construction), so
  prediction P3 is untested. Caveats: August 2026 may be incomplete; WinCo avg6 bias was 0.69 (Jul 2024-Jun 2025)
  vs 0.95 (Jul 2025-Jun 2026). Superseded: the first run's ALDI 40.4% (scored before the account stocked). Code
  `scripts/MO_141*.py`, log `scripts/outputs/mo141_run.log`. *Skeptic: SURVIVES WITH CORRECTIONS.* *Reopen if:*
  open sales orders or buyer order plans become available, or H-E-B has 12+ regular-ordering months.
- **(b) MO_143 / MO_143b (PROVISIONAL; descriptive analog, not a forecast arm): singles at Meijer.** Target and
  Walmart are the only analogs that added singles after established 4-packs (every other Food account had singles
  first). When Target put singles in most stores for the 2025 holidays (Nov 2 - Dec 28, about 70% of stores), its
  4-packs sold somewhat less than expected; the size cannot be pinned down. Between none and just under half of the
  singles bars came out of 4-packs, and in every version most were additional (4-pack change +3.8% to -19.5%
  depending on the comparison weeks; share of singles bars from 4-packs -0.04 to 0.46). One retailer, one season;
  Walmart is not measurable; not a forecast for Meijer checkouts. Benchmarks (units per store selling per item per
  week, medians): grocers excluding Meijer 3.3 (15 accounts), convenience 2.0 (Wawa 4.5), Target 4.8, Walmart 3.2;
  singles cost about 13% more per bar ($2.50 vs $2.22 at Target). Meijer scenarios (4 checkout singles x 280 stores)
  of about 2,200-5,400 singles bars a week and net +6% to +28% BUILT bars at Meijer are a what-if, not a forecast.
  Predictions: first run P1 FAILS, P2 HOLDS, P3 FAILS, P4 FAILS, P5 HOLDS, P6 FAILS; second run Pb1 HOLDS (one
  pulse), Pb2 FAILS (vacuous), Pb3 HOLDS (its 0.16 is not robust). Do not cite the first-draft -9.8% / 16% figures,
  "Mass 3.8", or a check-lane "go". Code `scripts/MO_143*.py`, add-on
  `docs/briefs/meijer_v2/Meijer_Singles_Addendum_2026-10-13.*`. *Skeptic: SURVIVES WITH CAVEATS* (add-on:
  SURVIVES WITH CORRECTIONS). *Reopen if:* a planned singles test at Meijer with store-level sales data.
- **(c) MO_144 / MO_144b (PROVISIONAL): forecasts for brand-new item x retailer series (absent at the forecast
  date).** An account-level arrival allowance with median launch curves (B2) improves the company-wide monthly
  forecast (portfolio x month: recent 10.12 -> 6.50, all 11.65 -> 9.42) and leaves retailer x month essentially
  unchanged (recent -0.45). The portfolio gain was not predicted in advance (the prediction covered account x
  month), so it is exploratory. Item-level launch sizing from history fails even with the true launch timing and
  presence (C2: recent miss 128%, 1.61x actual; C: 169%, 1.89x). Cause: history lags launch-size swings driven by
  store counts (launch ages 2-5: Walmart 33 -> 80 -> 18-39 stores; Publix 71 -> 17; Target 69 -> 43), not simply
  "recent launches are smaller". An account-level allowance for new items captures the portfolio effect now; sizing
  individual launches would need BUILT's launch list (item x retailer x expected launch date), which Connor keeps
  and has offered to feed in (open with BUILT, wiki/18), plus his own starting store-count assumptions; not a new
  data feed. Predictions: MO_144 P1 HOLDS, P2 HOLDS, P3-P5 FAIL; MO_144b Pb1-Pb3 FAIL, Pb4 HOLDS. Caveats: B's
  near-perfect recent bias is partly offsetting errors (0.42x in 2025, 1.49x recently with mean curves); "launch =
  first sale" mislabels some trickle scans (not driving the result). Code `scripts/MO_144*.py`, logs
  `scripts/outputs/mo144_run.log` and `mo144b_run.log`. *Skeptic: SURVIVES WITH CAVEATS (MO_144 and MO_144b).*
  *Reopen if:* Connor's launch list becomes available, or an arrival rate that adapts to the launch wave.
- **(d) MO_145 (PROVISIONAL; timing only, not accuracy): neural forecasting models (NHITS, TCN, TFT) on the
  RunPod GPU.** One forecast date (2025-01-01), 1,040 series, 200 training steps each, NVIDIA RTX A4500: fit time
  3.62 s / 2.94 s / 6.57 s and peak GPU memory 0.085 / 0.038 / 0.594 GB; all three run without error. A full 18-date
  neural test is minutes of GPU per job and memory is not a constraint. This says nothing about forecast accuracy.
  RunPod had not posted a cost yet (re-check from RunPod data only). Job `jason-mo145-001`. *Skeptic: not run
  (timing and memory only; predictions P1-P3 HOLD).* *Reopen if:* never as an accuracy claim; superseded by the
  full neural test.
- **Corrections (overturned by the skeptic or found afterward):** MO_144 arm C failed first because of Claude's
  construction flaw (pooling units per distribution point across retailers of very different scale), not because
  launch plans lack value; Claude's "recent launches are simply smaller" reading; Claude's wording of what it would
  take ("BUILT launch plans with authorized store counts"), corrected against README update 215 ("the door-count ask is UNANSWERABLE") and MO_95 (Brian has
  no data source for it; the oracle test gave 0.6 points, pre-fix benchmark, provisional); MO_143's published
  -9.8% / 16% Target figures and "grocer 3.4" (included Meijer); MO_141's ALDI 40.4%; and a PDF export bug (stale
  Word documents reused) that left an early-draft main brief PDF in commit 2b5f40a, regenerated in c1e980d.

### Added 2026-10-14 from MO_146 (neural forecasting models; README 243), PENDING review
- **(a) MO_146 (PROVISIONAL): neural global models (N-HiTS, TCN, TFT; one network across all item x retailer
  series; 5 seeds each; 18 forecast dates) do not beat the 5-seed fixed direct model, and their 50/50 blend with it
  is not a neural win.** Recent account x month: direct_avg5 16.17; nhits5 18.82, tcn5 17.98, tft5 18.85,
  neural_avg 17.91; dir_neural (0.5 direct + 0.5 neural average) 15.18 (5 of 6 dates), but 0.5 direct + 0.5 L4W
  velocity x stores gives 15.23 (5 of 6) and 0.5 direct + 0.5 L12W 15.09: the gain is generic averaging. The
  young-band portfolio gain comes from the last-value fallback used where no neural forecast existed (series under
  15 weeks); a blend using neural only where it exists is +0.82 worse band-separated. dir_neural is worse at
  portfolio x month in every established band (13-25 9.9 -> 10.9, 26-51 7.6 -> 8.8, 52+ 6.7 -> 7.8) and at Walmart
  (16.6 -> 17.6), and fails the seasonal check (Oct-Dec 2025 bias 1.118 vs 1.099). Leakage and harness parity
  checked (direct reproduces 16.17). P1-P5 hold as written (P2 as a tie). Code `scripts/MO_146_neural_backtest.py`
  (4d9ffd4; fixes before results bf969d6, 3dd13dc); forecasts kept at dev/aevah-jobs/mo146/aevah-results/
  jason-mo146-004..006; `outputs/mo146_neural.json`. *Skeptic: DOES NOT SURVIVE (as a neural win).* *Reopen if:*
  more history per series, exogenous inputs (distribution, price, promotions) in the neural models, a graph
  neural network or RNN/TFT variant, or MO_147 (pre-registered blends under Amendment 2) shows a neural blend
  beating direct + L4W. Also reopens MO_125 ("ship alone, not blended") and MO_126's band-blend condition.

### Added 2026-10-14 from MO_147 / MO_148 / MO_150 / MO_151 / MO_152 (README 244, 245), PENDING review
Each proposal carries the skeptic (opus/high) verdict line. Miss = average miss % (lower is better); levels: item x
week (cw), account x month (am), portfolio x month (pm); recent = 6 overlapping origins, 2025-12 on (exploratory).
Predictions were committed before each run (MO_147 02e9585, originally d701799; MO_148/149 731b278, originally
06abc56; MO_150 d3cbf91, originally acd5fc7). MO_149 (recent sales rate x stores as a model input) is NOT scored yet and has
no entry here.
- **(a) MO_147 (PROVISIONAL): 50/50 blends of the 5-seed fixed direct model (direct_avg5) with simpler methods do not
  pass the switching rules (Amendment 1 + Amendment 2 criterion 7); they trade portfolio x month accuracy in established
  bands for account x month accuracy.** Recent cw / am / pm (bias): direct_avg5 28.79 / 16.17 / 6.45 (0.970); dir_l4w
  (recent 4-week sales rate x stores) 26.96 / 15.23 / 7.04 (0.995); dir_l12w 27.64 / 15.09 / 6.46 (1.004); dir_flat15 (flat
  fallback for series under 15 weeks only) 28.32 / 15.77 / 7.21 (0.995); dir_neural_only 27.01 / 15.47 / 7.11 (0.963);
  dir_neural 26.87 / 15.18 / 7.21 (0.983; reproduces MO_146). Criterion 7 (portfolio x month within band, recent, change vs
  direct): dir_l4w +1.71 (26-51) / +1.64 (52+); dir_l12w +2.26 / +1.62; dir_neural_only +0.63 (13-25) / +1.24 / +1.09;
  dir_neural +0.95 / +1.24 / +1.09; dir_flat15 passes 7 but fails consistency (4 of 6) and holiday bias. Oct-Dec 2025
  bias: direct 1.099; l4w 1.121; l12w 1.159; flat15 1.116; neural_only 1.102; neural 1.118. Losses broad: dropping any
  one date or retailer leaves the 26-51 band worse (l4w at least +0.92); ex-Walmart l4w 26-51 +2.16, 52+ +1.35. L4W and
  L12W carry no seasonal adjustment. Predictions P1, P2, P3, P5 HOLD; P4 FAILS (l12w +0.06). Disclosure: MO_146's skeptic
  had already seen some headline numbers for l4w, l12w and flat blend; predictions were placed on unseen items only.
  `outputs/mo147_blends.json`, `scripts/outputs/mo147_run.log`. *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* forward
  dates (dir_l4w, dir_neural and dir_flat15 forward-saved at the next registration, description only) show at least 5 of 6
  wins and Oct-Dec 2026 bias no worse than direct's. Do not pre-register a blend tuned to flip one date. MO_126's band-blend
  reopen condition is technically met but those arms fail other criteria, so MO_126 is unchanged.
- **(b) MO_148 (PROVISIONAL): separate models for each product line (line_avg5) and a no-BAR model for PUFF + SOUR PUFF
  (nobar_avg5) are worse than the pooled direct_avg5 at recent dates; BAR history helps PUFF.** Recent cw / am / pm
  (bias): direct_avg5 28.79 / 16.17 / 6.45 (0.970); line_avg5 29.43 / 17.04 / 6.80 (0.971); nobar_avg5 29.26 / 17.03 / 6.85
  (0.981). 2025 cw / am / pm: direct 38.40 / 24.51 / 11.29; line 38.34 / 24.84 / 11.60; nobar 38.31 / 24.71 / 11.25. On
  rows the line models actually forecast, am 16.25 vs 15.29; ex-Walmart 17.65 vs 16.00. Per-origin am wins: line 2 of 6,
  nobar 2 of 6 (ex-Walmart 0 and 1 of 6). Loss is in core PUFF (cw 26.97 -> 27.68 line, 27.81 nobar), spread across Sam's,
  Target, Publix, Albertsons and Wegmans; Walmart is the only offset; the 52+ band is worse at am on 5 of 6 recent origins.
  Both fail criteria 1, 2, 4 and 7. Predictions P1 and P5 HOLD; P2 FAILS (+0.88); P3 FAILS (PUFF cw +0.84 worse); P4
  UNTESTABLE (SOUR PUFF is always the pooled-model fill-in at recent dates). Not caused by the fill-in, the duplicate-series
  rule or brand-transition series. Caveats: the BAR by-line cell is 0.09% of volume; the first-row line label is wrong for 190
  series (use the current label); nobar's SOUR PUFF gain is post hoc, Walmart-only, winter-only and reverses from 2026-03.
  `outputs/mo148_product_lines.json`, `scripts/outputs/mo148_score.log`; jobs `jason-mo148-001..007`; scoring 21307cd.
  *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* not stated by the skeptic. **This REVERSES the
  MO_121 bullet** in "Method rules" / "Current forecasting position" (marked there).
- **(c) MO_150 (PROVISIONAL): an average-uplift layer helps TOTAL units only at company x month; the promotion calendar
  adds no reliable gain.** Recent cw / am / pm (bias), total units: base_only 35.70 / 25.42 / 20.54 (0.795); avg_uplift
  38.74 / 23.89 / 11.12 (0.951); calendar_lift 37.02 / 23.31 / 10.84 (0.919). Within every history band at account x month
  avg_uplift is worse than base_only (+1.2 under 13 weeks, +1.3 13-25, +4.9 26-51, +0.4 52+) and it is worse at item x week.
  The calendar's gain is Target-driven (dropping Target halves it, -2.70 -> -1.30), beats avg_uplift on 5 of 6 recent origins
  but 6 of 12 in 2025, and a median uplift without the calendar (23.21 am) beats it. Alignment: SPINS uplift higher in-window for
  57.6% of 250 promotions (P1, needed 60%, FAILS; post hoc 66.4% excluding "before" weeks that are themselves promotion
  weeks). P2 HOLDS; P3 FAILS (1.53 not 3 at am; pm 20.5 -> 11.1); P4 FAILS (bias 0.919). Look-ahead: the calendar is the
  2026-09-30 snapshot, so the backtest is an upper bound; Walmart (24% of recent units) has no promotions in the calendar; 363 of
  1,648 series are covered (39% of recent total units). Recommendation: base x (1 + the item's median 26-week uplift), accuracy
  quoted at company x month only; calendar for what-if only; total-unit am (23-24) is much worse than base-unit am (16.2). Add
  any figure to `docs/ACCURACY_CLAIMS_REGISTER.md` section 2 before client use. `outputs/mo150_promo_layer.json`,
  `scripts/outputs/mo150_run.log`. *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* not stated by the skeptic (the look-ahead
  snapshot and the Walmart/Kroger mapping gaps are the known limits).
- **(d) MO_151 (PROVISIONAL, descriptive): which inputs drive the served v11d model, by current product line.** Mean
  absolute TreeSHAP (log scale, per series, unweighted), median models at 1, 4 and 13 weeks, anchor 2026-09-06; series BAR 46,
  PUFF 1,282, SOUR PUFF 276 (lapsed excluded). Recent sales level and trend: h1 85-87%, h4 71-75%, h13 44-53%. At h13:
  promotion history (promo_lift_n_events) 14-19%, retailer 10-11%, product 6-11%. The product-line label itself: 0.15-0.6% at
  h1, 0.4-1.6% at h4, 1.9-2.0% (PUFF, SOUR PUFF) and 7.8% (BAR) at h13, where it lowers every BAR series about 23% (signed mean
  -0.256 log) and raises PUFF and SOUR PUFF about 6%. promo_lift_n_events is an item-tenure proxy (Spearman 0.75-0.80 with weeks
  of history) and LOOK-AHEAD in the served model (MO_25:992-1018 computes it over each series' full history; the backtest
  rebuilds it per cutoff at MO_80:507); it pushes forecasts down on average. Volume-weighted reliance on recent sales is higher
  (PUFF roll4 + lag1 77 -> 88% at h1, 43 -> 56% at h13). Similar profiles do not prove the lines follow the same rules; MO_148 is
  the accuracy evidence for pooling. `outputs/mo151_inputs_by_line.json`. *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* the
  served model is retrained with per-cutoff inputs.
- **(e) MO_152 (PROVISIONAL, descriptive): how much each product line weighs in training the served v11d model.** The 1,604
  forecast series do not set the model's influence: it learned from 76,482 weekly training rows (58,371 at 13 weeks) across all
  2,117 series, including 513 no longer selling (96,369-row panel, the same one v11d trained on). Each row is one vote regardless
  of item volume (LightGBM quantile loss), times a recency weight (1 year old about 0.35, 2 years about 0.13). Share of training
  votes after recency, BAR / PUFF / SOUR PUFF: 1 week 6.9 / 88.2 / 4.9; 13 weeks 7.3 / 91.2 / 1.5; raw rows 17.5 / 80 / 2.6; units
  in those rows 3.1 / 93.1 / 3.7. PUFF dominates mainly through quantity (more retailers, so more rows); recency widens the gap.
  These shares describe what the lines share; product line is also an input, so BAR's own adjustment (about 23% lower at 13 weeks,
  MO_151) is set by BAR's rows alone and is consistent with the 2025 BAR wind-down, not shown to be caused by it. The served model
  learned from weeks up to 2026-06-07 and has not been retrained since. The early-stopping rows that set tree count are
  unweighted (12-15% SOUR PUFF, 1-2% BAR). `scripts/MO_152_training_weight_by_line.py`, `outputs/mo152_training_weight_by_line.json`;
  commits 9716089, 5fb3d66. *Skeptic: SURVIVES WITH CAVEATS.* *Reopen if:* the served model is retrained. Open question: are the 46
  BAR items still selling given the wind-down pattern of BAR items discontinued in 2025? Check before the December forecast.
- **Production caveat (open, not a finding):** the served v11d model was trained with look-ahead promotion, donor and
  competitor-gap inputs (README ~1983-1985); the backtest rebuilds them per cutoff, so backtest scores do not describe the served
  model exactly. Any retrain for the December forecast must compute them per cutoff.

## Open blockers (not findings; test plan Phase 0, `docs/FORECAST_TEST_PLAN_V12.md:42-44`)
- **Oracle doors reverse between levels.** They help at item-week (25.2 vs 33.4) and hurt
  at portfolio-month (19.2 vs 17.5). Unexplained.
- **Retransformation bias.** Velocity models run at 0.62–0.65 vs 0.886, because the median
  of log1p(velocity) × doors ≠ mean units. Fix with Duan smearing or tweedie before
  model-based velocity arms.
  Note 2026-10-12: MO_139 tested the units direct model only (Duan smearing as designed failed; Tweedie mixed by period); the velocity-model blocker itself is untested.
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
  **REVERSED by MO_148 (README 244)** on the corrected harness: BAR history helps PUFF; excluding BAR is ~0 on 2025
  origins and harmful on recent (+0.86 account x month). Original text above kept for the record; do not cite it.
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
  re-verify the Meijer cannibalization brief. *Addressed 2026-10-13 by MO_142 (own-store
  Meijer re-analysis and brief v2); see README 241.*
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
