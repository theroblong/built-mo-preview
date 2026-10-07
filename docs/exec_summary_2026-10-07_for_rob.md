# Exec summary for Rob: 2026-10-07 (Jason's session)

## Bottom line
- **The accuracy claims we had been making don't hold.** Today we stopped repeating them,
  starting with Mo Chat.
- **The seasonal adjustment used in every backtest had look-ahead.** That made the
  forecast candidates look better than they are. A clean re-test (MO_127) is running now.
- **Next is the test Jason actually wants** (MO_128): on the PUFF SKUs with the longest
  history, can our model beat Connor's last-4-weeks method?

## 1. Accuracy claims: corrected and tracked
- **We found 13 places quoting retired figures:** 4%, 4.3%, 2–6%, 6.1% and "5× better
  than foundation models". They include Mo Chat, the FP&A report, the horserace and exec
  brief mockups, wiki/13 and the marketing notes.
  - New tracker: `docs/ACCURACY_CLAIMS_REGISTER.md`. It lists the current numbers, the
    retired ones and why, and each location with a status.
- **Mo Chat is fixed** (approved by Jason, with your OK). It no longer quotes any
  percentage for Mo's own forecast, and explains accuracy in plain language. It goes live
  on the next Mo API redeploy.
- **Stance (Jason):**
  - Accuracy isn't the headline while forecasting is being tuned.
  - Lead with velocity × distribution insight, cannibalization, elasticity and
    explainability.
  - Demand velocity forecasting stays the main deliverable.
  - Metrics like wMAPE are always explained for a CFO/FP&A reader.

## 2. Your settled-findings draft: Jason's review
- **Load only the key parts each session** (blockers, method rules, current position,
  do-not-cite list; about 110 lines). FACT and older results stay in the file for
  lookup.
- **Model vs flat at portfolio × month: NOT settled.** The skeptic agent showed:
  - README 223's win is the unshipped anchor-mode arm.
  - Flat beats the model in every history band at that level.
  - MO_92 is differently scoped, not reversed.
- **BUILT's "7%" moves from FACT to an open question.** Its definition is unknown.
- **Meijer brief: already rebuilt on Meijer RMA data on Sept 25.** The README open item
  was stale.

## 3. What the skeptic found (verified against the files)
- **Seasonal index look-ahead.** The index was built Oct 1 from every series with 104+
  weeks, then applied at every historical cutoff.
  - Our panel starts **2023-10-15**, so at the four 2025 cutoffs **zero** series had 104
    weeks. No honest index could have existed then.
  - conn_L4W's edge at portfolio × month comes entirely from seasonality: 16.4 without it
    vs flat 16.0.
- **What ships today has never been scored at portfolio × month.** MO_27 runs
  step-over-step; MO_125's "production" arm is the pre-Oct-6 target mode.
- **The MO_126 script isn't committed.** Is it on your machine?

## 4. MO_127, running now
- **The test:** it rebuilds the seasonal index at each cutoff from pre-cutoff data only,
  using MO_59's own code. It scores the model, conn_L4W and flat with the full index, the
  honest index and no seasonality: 3 levels × 4 history bands × 7 quarters.
- **Protocol:** predictions were committed before the run.
- **Smoke test:** the rebuild exactly reproduces the committed index. Early hint: the
  honest index at the Jun-2026 cutoff correlates only **r = +0.17** with the full one.

## 5. The long-history PUFF SKUs (for MO_128)
These are the top 25 PUFF series by history and volume. All have 152 weeks, the full
panel from 2023-10-15 to 2026-09-06. Other retailers may also carry these SKUs with full
history.

| SKU | UPC | Retailers with full history |
|---|---|---|
| PUFF Brownie Batter 1.41oz single | 08-40229-30362 | Kroger, Circle K, Publix, UNFI, Maverik, CVS, Wegmans, AWG, Albertsons, Hy-Vee |
| PUFF Coconut 1.41oz single | 08-40229-30037 | Circle K, Kroger, Publix, Maverik, UNFI, Walmart, CVS, Wegmans, Albertsons, AWG |
| PUFF Brownie Batter 4-pack | 08-40229-30380 | Walmart (1.18M base units, last 52 wks), Meijer |
| PUFF Coconut 4-pack | 08-40229-30381 | Walmart (0.99M), Publix, Meijer |

- **Wider set:** 262 PUFF item × retailer series with 2+ years of history, 461 with 78+
  weeks, and 749 with 52+.
- **Evidence so far** (MO_126, 52+ week items, item × week, full-panel index):

  | Method | Average miss |
  |---|---|
  | conn_L4W | **22.2** |
  | flat | 29.9 |
  | our model | 34.7 |

  The likely cause is that year-ago anchors understate a brand growing this fast.
  conn_L4W avoids that by working per store × current stores.

## 6. Proposed next step: MO_128 (plan to come for approval)
- **The head-to-head on the focal SKUs:**
  - conn_L4W
  - Connor's actual L12W default
  - flat
  - the shipped model
  - the model without BAR
- **Two model variants:**
  - predict sales per store × stores (targets the growth understatement)
  - learn corrections on top of conn_L4W
- **Scoring:** item × week and account × month, 13 weeks ahead, by quarter.
- **Framing:** "L4W anchor plus ML for what it can't see" (promos, price, seasonal turns,
  competitor launches), not ML vs L4W. If the model can't beat L4W even as a corrector,
  we ship L4W and keep ML for explanation and scenarios.
- **TFT/RNN deprioritized:** about 260 long series and under 3 years of data.
- **Caveat:** these are flagship survivors, so they're a strong signal, not a portfolio
  verdict.

## Asks for you
1. Review the settled-findings draft together with Jason's answers (live notes in
   `agents/project_memory.md`).
2. Redeploy the Mo API so the Mo Chat wording goes live.
3. Find the MO_126 script if you have it.
4. Any objection to the "L4W + corrections" framing for MO_128.
