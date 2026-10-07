# DRAFT: Mo Chat accuracy wording (for Jason + Robert to approve)

Status: **draft, 2026-10-07. Nothing in Mo Chat has changed.**
Target: customer-built-mo-api `app/routers/mo_chat.py`, the `_DATA_GLOSSARY` text, lines
2185–2195 (baseline methods) and 2201–2222 (accuracy and foundation-model sections).
Rules applied: `docs/ACCURACY_CLAIMS_REGISTER.md` (numbers from section 2; plain language
per section 1; accuracy is not the headline).

Why it needs changing: Mo Chat is currently told to *"cite these figures"* when asked how
accurate the forecast is. Those figures are 2.0–5.7% (one-step-ahead, retired) and
"6.1%, 5.1× better than foundation models" (hard-coded from a leaked backtest, retired).
It also calls the 13-week moving average "the current Excel planning baseline", which
Connor's workbook shows is not how BUILT plans (README 224).

## Decisions for Jason + Robert before this goes in

1. **Give Mo Chat any accuracy percentage yet?** Revised 2026-10-07 after the skeptic
   check (see the register, section 2 warning): the ~20% figure was a configuration that
   no longer ships, and today's forecast has not been scored on the corrected test setup.
   **The draft now gives no percentage** for Mo's own forecast, only how to read accuracy
   and where the forecast is strongest and weakest.
2. **Mention the not-yet-shipped velocity method (~11% in testing)?** The draft leaves it
   **out** (21 monthly observations, 4 gates still open) and only says accuracy is being
   improved. Optional line provided below if you want it in.
3. **Name the four pre-trained models?** Kept as before; the comparison is now honest.

---

## Replacement for lines 2185–2195 (baseline methods)

```
  MA 13wk (13-week moving average): Simple average of the last 13 weeks of actual sales,
    repeated forward. No trend, seasonality or other inputs. A common spreadsheet method.
    (BUILT's own planning workbook works differently: it takes a recent sales-per-store
    rate and multiplies it by planned distribution.)
  ETS (exponential smoothing with trend): Weights recent weeks more and extends the recent
    trend forward. Watch out for distribution-driven growth: it keeps extending the trend
    after distribution stops growing, so it overshoots.
  Naive (last value): Repeats the most recent week's sales for every forecast week. The
    simplest yardstick; a forecast is only worth having if it beats this.
  Do not quote accuracy figures for these methods; use FORECAST ACCURACY below.
```

## Replacement for lines 2201–2222

```
FORECAST ACCURACY: how to answer "how accurate is the forecast?" or "can I trust this?"
  Lead with what the forecast is for (planning demand at account and portfolio level,
  explaining what drives it), then give the figures WITH their context. Never use the
  term "wMAPE" without explaining it, and always say what a percentage means.

  What we measure: "average forecast miss, weighted by volume". Add up how far off each
  forecast was, over or under, and divide by total actual sales. 20% means the misses
  add up to one fifth of what actually sold. Lower is better.

  The level matters: misses partly cancel when you add up, so the same forecast scores very
  differently by level. Always say which level a figure refers to.

  Accuracy figures for the current forecast are being re-measured after a correction to
  how forecasts are tested, so do not quote a percentage for Mo's own forecast yet. If
  asked, explain:
  - Misses are much larger for one item at one retailer in one week than for an account
    or the whole portfolio by month, because week-to-week item sales are noisy. Treat
    item-week forecasts as direction; plan at account or portfolio level.
  - Newer items (under about 13 weeks of history) are the hardest to forecast. For them Mo
    relies on the most recent sales, which tested as the most reliable approach.

  Accuracy is actively being improved: modeling BUILT's product lines (BAR, PUFF, SOUR
  PUFF) separately, carrying BAR history forward for flavors that continued as PUFF, and
  testing newer learning methods. PUFF and SOUR PUFF have less than 3 years of SPINS
  history so far, so accuracy should improve as that history builds. Do not promise a
  specific future figure.
  [OPTIONAL, if approved: "A new method based on sales per store per week times current
  store count roughly halved the monthly portfolio miss in testing (about 11%). It is
  still being validated and is not yet live."]

  Never quote any other accuracy figure. In particular, never quote 2–6%, 4%, 4.3% or
  6.1%. They were measured in ways that do not reflect a real 13-week forecast and have
  been retired.
  Do not compare these figures with BUILT's own "7–10%" estimate; how that figure is
  measured is not yet known.

COMPARISON WITH OFF-THE-SHELF AI FORECASTING MODELS:
  In an earlier test, Mo was compared with four pre-trained forecasting models (Amazon
  Chronos, IBM Granite TTM, Salesforce Moirai, Google TimesFM) on the same 100 established
  items, 13 weeks ahead. Typical-item miss: Mo about 27%, Chronos and Granite about 28%, Moirai 32%,
  TimesFM 38%; simply repeating recent sales also scored about 27%.
  So on forecast accuracy alone Mo is roughly level with the best pre-trained models, not
  several times better. Never say Mo is "5x" or "several times" more accurate.
  Mo's advantage is what a generic model cannot do: it works from BUILT's own SPINS data
  and explains demand through distribution, sales per store, cannibalization between
  BUILT items, price sensitivity and promotions, and it shows why a number moved.
  All four pre-trained models were run locally; no BUILT data was sent to outside services.
```

Sources: production 20.07 and bias 0.920 (MO_125, README 226); item level 32–41% (MO_80,
README ~1943) and 36.3 (README 225); under-13-week routing (MO_126, README 227);
foundation comparison (MO_106, README 217); BUILT's workbook (README 224).

## Also noticed (not changed, outside this draft)

Lines 2172–2178 describe seasonality as "STL decomposition of the top-20 longest-history
BUILT series", applied only to items under 52 weeks. The current seasonal index is
volume-weighted over all qualifying series, and the seasonal mode has since changed
(README 219–222). Worth a separate check before Mo Chat explains seasonality.
