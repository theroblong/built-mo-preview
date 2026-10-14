<!--
DRAFT v0.2 (2026-10-14; skeptic edits applied same day) -- content for the styled trust document (builder: scripts/build_trust_document.py).
Audience: BUILT leadership and finance (Brian shares it). Aevah brand voice (docs/aevah_brand/brand/aevah-brand-guide.md).
Rob's answers (docs/drafts/aevah_trust_document_rob_checklist.md) govern: accuracy-first; security = one sentence
(item 1); nothing about encryption, backups, retention, sign-in, roles, AI provider, local model, monitoring or
certifications, and nothing described as planned; no data-residency absolutes (item 6). Architecture per Rob's
item-14 correction (approved by Jason 2026-10-14). No forecast-accuracy figures (ACCURACY_CLAIMS_REGISTER section 2).
Vendor names: only Azure (Rob item 1); everything else generic.
Skeptic (opus/high) 2026-10-14: SURVIVES WITH EDITS; all wording edits applied. Open for Rob: Circana status; whether
'runs in BUILT's own Azure subscription' needs scoping (Mo Chat's language model is an external service; forecast runs
are made on Aevah machines); 'secure' dropped from the data store. Before Brian: redeploy Mo API (retired-figure fix),
correct the 4.4% from 10-09 with BUILT, fill the contact line.
-->

# How Mo works

**How BUILT's demand intelligence produces its numbers, how those numbers are checked, and where it runs.**

Prepared by Aevah for BUILT · October 2026

## In brief

Mo is BUILT's demand intelligence experience, built and operated by Aevah. It turns BUILT's retail sales data into
forecasts, cannibalization reads, price-sensitivity reads and retailer views that BUILT's teams can use directly.

The question that matters most is whether Mo's numbers can be trusted. Three things make them trustworthy:

- **The numbers are calculated, not generated.** Every forecast, probability and sensitivity figure Mo shows comes
  from models and calculations run on BUILT's sales data, not from a language model.
- **The numbers are tested against what actually sold.** Before a new forecasting method replaces the current one,
  Aevah rewinds to earlier dates, forecasts forward using only data up to each date, and compares the result with
  actual sales.
- **The numbers can be traced.** Each forecast and score is stored with when it was produced and which model version
  produced it.

## How Mo's numbers are produced

Mo uses machine learning: models that learn patterns from BUILT's history and are then tested on periods they have
not seen. Each job has a model suited to it.

**Demand forecasts.** Mo forecasts each item at each SPINS-reported retailer 13 weeks ahead. The model uses how many
stores carry an item and how fast it sells in each store, alongside sales history, pricing, promotions and
seasonality. It is a set of gradient-boosted decision trees: many small decision rules that each correct the last.

**Everyday sales and promotions.** The forecast model predicts everyday (non-promotion) sales, the steady base of
the business; it does not yet add expected promotion volume. Separately, Mo shows how each item's sales have
responded to past promotions, by type of promotion.

**Cannibalization.** When BUILT launches an item, Mo scores how likely it is to be drawing sales from each nearby
item, BUILT's own and competitors', and tracks a weekly cannibalization rate. Each score carries the three factors
that most influenced it, so the reason travels with the number.

**Price sensitivity.** Mo estimates whether sales tend to rise or fall with price changes, by item and retailer where
there is enough price history. The direction is more reliable than the size, because most price changes happen
during promotions.

## How the numbers are checked

Aevah tests every forecasting change the way a finance team would want it tested:

- **Rewind and compare.** Aevah goes back to 18 earlier forecast dates, forecasts forward from each using only data up
  to that date, and compares with what actually sold, at the level of an item at a retailer, a retailer's month and
  BUILT's total month.
- **Simple yardsticks.** Every model is compared with rules a planner could use by hand, such as "assume recent sales
  continue" and "recent weekly sales per store × current store count".
- **Predictions written down first.** Before a test runs, Aevah records what it expects, so each result can be checked
  against what was expected.
- **Challenge before reporting.** Each forecasting result goes through a separate review step whose job is to try to
  break it. Results that do not survive are marked withdrawn in Aevah's records.
- **A switching rule set in advance.** The forecast BUILT sees changes only when a new method passes a rule written
  before testing: better on recent dates, consistent across forecast dates, no worse for established items, and no
  more prone to running high or low through the seasons.
- **Forward confirmation.** Since September 2026, forecasts are saved before the weeks they cover. The first will be
  scored once those weeks' sales data arrive in December.

Mo's forecast changes only when a candidate passes this rule. Several alternatives, including neural networks and
blends of methods, have been tested so far, and none has met every condition. Forecast accuracy is still being
improved, and Aevah reports it only with the context below.

When Aevah reports accuracy, it states what was measured, at what level, how far ahead, compared with what simple
rule, and on how much data, because the same forecast can look very different at an item level and a company level.

## How Mo differs from generative AI

Generative AI tools built on large language models (LLMs) are remarkable at language: understanding questions,
summarizing and explaining. They produce fluent text by predicting likely words, which makes them a strong interface
but an unreliable source of business numbers. *LLMs generate. Aevah operates.*

| | Generative AI tools | Mo |
|---|---|---|
| Where numbers come from | Generated text; plausible but not calculated | Calculated by models and calculations run on BUILT's sales data |
| Same question, same answer | Not guaranteed | Stored figures stay the same until new data or a new model version is released, and each carries its date; Mo Chat's wording can vary |
| Traceability | Hard to tie an answer to a source | Each forecast and score is stored with its date and model version |
| Scale of data | What fits in a prompt | Millions of weekly records |
| Testing | Rarely tested against outcomes | Tested against what actually sold |

**Where Mo uses generative AI.** Mo Chat uses an AI language model to understand questions and explain answers in
plain English. It retrieves the relevant figures from Mo's data at the moment of the question and explains them; it
is instructed to use figures from Mo's data and never to invent data. The language model does not calculate Mo's
forecasts or scores.

## How Mo is built

1. **Data sources.** SPINS weekly retail sales (the core), Circana for Costco, and BUILT's item master, including
   NetSuite item attributes. BUILT's shipments and trade promotion calendar are being added and evaluated.
2. **A data store in BUILT's own Azure subscription.**
3. **Preparation and machine learning.** Prepared feature tables and model scoring, refreshed by Aevah when new SPINS
   data arrives and checked before release.
4. **Versioned results,** stored back in the data store with their date and model version.
5. **The Mo app and Mo Chat,** which read results only through fixed, predefined data requests.

## Where Mo's forecasts and scores get their data

| Source | What it provides | Status |
|---|---|---|
| SPINS weekly retail sales | Sales, prices, promotions and distribution for BUILT and the full category at more than 100 retail accounts | In use (the core) |
| Circana | Sales for Costco, which SPINS does not cover | Loaded into the data store |
| BUILT's item master | Items, product lines, pack details and NetSuite item attributes | In use |
| BUILT's NetSuite shipments | Shipments to retailers without store-level sales data | Being added and evaluated |
| BUILT's trade promotion calendar | Planned promotions by customer | Being added and evaluated |

Retail sales data arrive weekly, a few weeks after the fact, so Mo's forecast views state the last week of actual
sales they use.

## Where Mo runs

Mo runs in BUILT's own Azure subscription, in the West US 3 region (United States), operated by Aevah.

## Keeping the numbers honest

Mo's forecasts and scores are stored with the date they were produced and the model version that produced them, and
forecasts are now saved as versions, so an earlier forecast can be compared with what actually sold. When Aevah finds
an error in its own work, the correction is recorded in Aevah's records alongside the original result rather than
quietly replaced.

## Questions

Aevah · [[JASON: contact name and email]]
