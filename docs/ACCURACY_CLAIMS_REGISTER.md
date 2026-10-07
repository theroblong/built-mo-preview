# Accuracy claims register

Started 2026-10-07. Owner: Jason + Robert. Internal.

Every forecast-accuracy number that goes into anything someone else will read (Mo Chat,
reports, decks, briefs, wiki, marketing) comes from **section 2** of this file, stated the
way **section 1** describes. Section 3 lists the numbers we no longer use and why.
Section 4 tracks where those old numbers still appear and which have been corrected.

## Messaging stance (Jason, 2026-10-07)

- **Demand velocity forecasting is the current main focus and working deliverable.**
- Forecast accuracy is still being dialed in. The next steps are separating product lines
  (BAR / PUFF / SOUR PUFF), chaining BAR→PUFF history for preserved flavors, and trying
  TFT and other learned sequence models. PUFF and SOUR PUFF do not yet have 3 years of
  SPINS history.
- Until those settle, **accuracy should not be the headline** of client or marketing
  material. Lead with the other features and benefits: velocity × distribution insight,
  cannibalization, price elasticity, explainability, one shared forecast. Cite accuracy
  only with its context (section 1).
- Correct the files in section 4 **as needed and with newer data**, not all at once.
  Track every correction here. The exception is Mo Chat (priority 1), because it actively
  quotes the old numbers to users.

## 1. Explaining metrics to a non-data-science audience

The audience is mostly CFO and FP&A people. They know statistics and data analysis, but
not data-science shorthand. **Never use an acronym like wMAPE without saying what it
means**, and always say what a percentage actually communicates.

**Every accuracy number states five things:**
1. **What it measures**, in plain words: "average forecast miss", not "wMAPE".
2. **Level**: one item at one retailer per week? One account per month? The whole
   portfolio per month? Errors shrink as you add up, because misses in opposite
   directions cancel. The same forecast scores roughly 28% at item level and 11% at
   portfolio level.
3. **How far ahead**, e.g. 13 weeks.
4. **Compared with what**: usually "repeat recent sales" (flat), or BUILT's current
   process.
5. **Test and sample**: an honest holdout (see below), the period, and how many
   observations. A small sample gets said out loud.

**Plain-language glossary**, usable verbatim with clients:

| Term | Say this |
|---|---|
| **wMAPE** (weighted mean absolute percentage error) | "Average forecast miss, weighted by volume." Add up how far off each forecast was, in either direction, and divide by total actual sales. **20% means the misses add up to one fifth of what actually sold.** Lower is better. Big items count more than small ones. Avoid "80% accurate"; say "an average miss of 20%". |
| **Bias** | "Whether we run high or low overall." Total forecast ÷ total actual: **1.03 = 3% too high; 0.92 = 8% too low.** A forecast can be unbiased overall and still miss a lot item by item, because highs and lows cancel. |
| **pp** (percentage points) | The difference between two percentages. Going from 20% to 10% error is **10 points**, which is a **50% reduction**. Say which one you mean. |
| **Flat / naive baseline** | "Assume sales stay where they were recently." The yardstick: a forecast is only worth having if it beats this. |
| **Holdout / backtest** | "We rewound to an earlier date, forecast from there, and compared with what actually happened." **Honest** = the model saw nothing after that date. |
| **One-step / "teacher-forced"** | Forecasting only next week, given the real sales up to this week. Scores look excellent but **do not describe a 13-week forecast**. Never quote these as accuracy. |
| **Median vs volume-weighted** | The median is the typical item, so small items count as much as big ones. Volume-weighted is closer to the business total. The two can differ by 10+ points, so never compare one with the other. |
| **Velocity / Base U/S/W** | "Base units sold per store per week": sales normalized for how many stores carry the item. |
| **TDP / distribution** | "How widely the item is carried" (total distribution points). |

## 2. Current numbers (as of 2026-10-07)

> ⚠️ **Do not quote any figure in this section outside the team yet** (skeptic check,
> 2026-10-07, key claims verified against the files):
> 1. **"Production" 20.1% is the configuration shipped *before* 2026-10-06**, with
>    target-only seasonal (MO_125:27, :93). What ships now (step-over-step seasonal,
>    `scripts/MO_27_retailer_sales_forecast.py`:794-800) **has never been scored at
>    portfolio × month**.
> 2. **Possible look-ahead in the seasonal index.** It was built 2026-10-01 from series
>    with 104+ weeks (`scripts/outputs/mo59_seasonal_index_meta.json`) and applied at every
>    historical cutoff, while flat gets no seasonal adjustment. Without seasonality, the
>    velocity method scores **16.4 vs flat 16.0** at portfolio × month (README 226). Its
>    advantage there is therefore all seasonal, and has to be re-tested with an index built
>    only from pre-cutoff data.
> 3. **At portfolio × month, flat beats the model in every history band**
>    (`scripts/outputs/mo126_band_breakdown.json`; the generating script is not committed).
>    The velocity method beats flat only for items with 26+ weeks of history.
> 4. The 32–41% item-level figure (MO_80) predates the harness parity fix (MO_118).
>
> Honest position for now: **no accuracy figure for the forecast as it ships today has
> been measured on the corrected test setup at all three levels.**

All figures are **average forecast miss (volume-weighted)** on holdouts unless noted.
**None of the improved estimators has shipped yet.**

| What | Item × retailer × week | Account × month | Portfolio × month | Source |
|---|---|---|---|---|
| Pre-2026-10-06 production config (target-only seasonal, full index) | — | — | 20.1% (bias 0.92) | MO_125, README 226 — superseded |
| Velocity anchor `conn_L4W`, no seasonal (candidate, **not shipped**) | 32.5% | 21.7% | 16.4% (bias 1.00) | MO_127 honest; the earlier 28.4 / 17.7 / 10.7 used the look-ahead index |
| Flat baseline ("repeat recent sales") | 32.8% | 22.9% | 16.0% | MO_127 |
| Production model (step mode), honest index | 38.6% | 26.8% | 17.3% | MO_127 (800-tree cap; see roadmap step 2) |

**Caveats that travel with these numbers:**
- Portfolio × month rests on **21 observations**.
- **The candidate does not win everywhere (MO_126).** On items with under 13 weeks of
  history it is worse (54.9% vs 48.0% for the model). On items with 52+ weeks it is much
  better (22.2% vs 34.7%). Production handles new items with "last value" (validated).
  Four validation gates must pass before shipping (README 226; docs/FORECAST_TEST_PLAN_V12.md).
- The full 13-week honest holdouts for the older model (MO_80, 7 quarters) were
  **32–41%** at item level.
- **Versus off-the-shelf AI forecasting models (MO_106, the honest rerun of MO_62):**
  100 mature items, typical-item (median) miss: Mo 26.6%, Amazon Chronos 27.7%, flat
  26.9%. Volume-weighted: flat 33.8% beats Mo 39.4%. **We are roughly level with them,
  not 5x better.**
- **BUILT's own "7–10%"** is Connor's estimate. Its metric, level and horizon are
  unknown, so **do not put it side by side with ours** until we know what it measures.
  The pooled total error (0.3–1.6%) is not comparable either: monthly misses cancel in
  a total.

## 3. Retired figures: never quote these as accuracy

| Figure | What it actually was | Retired by |
|---|---|---|
| **4%**, **4.3%**, 4.15%, 3.4–4.3% | One-step-ahead ("teacher-forced"), given actual recent sales | Feature contract audit, README 222 |
| **2.0–5.7%** (MO_63 rolling CV) | Same one-step setup (actual lag values in the test inputs) | Same |
| **6.1%** / 6.14% | MO_62 hard-coded a number from the MO_38 backtest, which was itself leaked; Mo was never run | README 217 |
| **5.1×**, 4.5×, 6.2×, "4–6× better than foundation models" | Derived from the 6.1% | README 217; honest gap is ~1 point |
| 15.5–15.7%, and the Oct 2025 "6.1% / 29 weeks" backtest row | Leaked: the model scored quarters it was trained through | README 202 / 222 |
| 0.3–1.6% "total error" | Pooled total; misses cancel. A bias check, not accuracy | Pooled-total-error rule |

## 4. Where retired figures still appear

Priority: **1** = actively told to users now · **2** = client-facing document ·
**3** = internal, or a historical record (annotate rather than rewrite).

| # | Location | Retired figure(s) | Pri | Status |
|---|---|---|---|---|
| 1 | Mo Chat `_DATA_GLOSSARY`: customer-built-mo-api `app/routers/mo_chat.py` ~L2201–2222 (last changed 2026-09-24) | 2.0–5.7%, "4–12× better than Excel"; 6.1% and "5.1× worse" foundation models; it is told **"cite these figures"** | **1** | **Corrected 2026-10-07** (approved by Jason, Rob agrees): wording from `docs/drafts/mo_chat_accuracy_wording_DRAFT.md`, with no percentage for Mo's own forecast and the optional line left out; L2185–2195 baselines fixed; macro section's "6.313% vs 6.505%" replaced with plain words. Live once the Mo API is redeployed. |
| 2 | FP&A report `docs/built_demand_intelligence_report_v2.4.0.html` (generated by `scripts/MO_36_report.py`, L477) | Backtest table row Oct 2025 = 6.1% (leaked); §31 foundation benchmark | 2 | Open |
| 3 | `mockups/aevah_forecast_horserace.html` | "4% accuracy target" vs 7–10% vs 46–118% | 2 | Open |
| 4 | `mockups/mo_exec_brief.html` | "4% target error rate vs BUILT's 7–10%" | 2 | Open |
| 5 | `mockups/bracken_forecast_project_plan.html` | "Oct 2025 backtest showed 6.1% error" | 2 | Open |
| 6 | customer-built-doc `wiki/13-competitive-landscape.md` L114 | 6.1% vs 31.5% (5.1×) | 2 | Open |
| 7 | `docs/aevah_marketing_notes_internal.md` | 4.3%, 6.1%, 4.5×/6.2×/5.1× | 3 | Open (internal, but feeds marketing) |
| 8 | `docs/aevah_llm_vs_ensemble_talking_points.md` | 5.1× | 3 | Open |
| 9 | `mockups/mo_competitive_landscape.html` (internal) | 4% wMAPE, 6.1%, 5.1× | 3 | Open |
| 10 | `docs/mo_python_ml_register.md` | 6.1%, "4–6× more accurate" | 3 | Open: annotate as superseded |
| 11 | `mockups/mo_data_model.html`; wiki `02-data-architecture.md` L414 | "6.1% wMAPE on holdout" | 3 | Open |
| 12 | wiki `19-data-refresh-safety.md` L230, L394 | 6.1% used as the **retrain pass/fail threshold**, which makes it the wrong baseline for the gate | 3 | Open: the gate needs an honest baseline |
| 13 | wiki `03-ml-pipeline.md` L243; `08-roadmap.md` L580, L640 | 6.1%, 4.3% in experiment-history tables | 3 | Historical: annotate only |

Checked, no retired figures: `mockups/meijer_cannibalization_brief.html`.

## Change log

- 2026-10-07: Section 2 updated to MO_127 honest (no look-ahead) numbers; MO_128 long-history PUFF results in docs/exec_summary_2026-10-07_for_rob.md.
- 2026-10-07: Mo Chat glossary corrected (location 1).
- 2026-10-07: Register created (Jason's decision: track corrections, update files later
  with newer data, de-emphasize accuracy while forecasting is dialed in; explain metrics
  in plain language). Locations 1–13 found by search across FirstAgent,
  customer-built-doc and customer-built-mo-api.
