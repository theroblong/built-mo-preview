<!--
DRAFT v0.1 (2026-10-14) -- content only, unstyled. Styling waits for Rob's Aevah design file.
Audience: BUILT leadership and finance (Brian shares it). Generic technology names; no vendor names; no other clients.
Items marked [[ROB: ...]] are unconfirmed and are removed or replaced before Brian receives it
(checklist: docs/drafts/aevah_trust_document_rob_checklist.md).
No forecast-accuracy figures: none is cleared for outside use (docs/ACCURACY_CLAIMS_REGISTER.md section 2).
Sources for each section are listed in the HTML comments; every factual sentence must trace to one.
-->

# How Mo Works

**A guide to Aevah's Mo for BUILT: what it does, how it is built, how it uses machine learning, where its data comes
from, and how your data is protected.**

Prepared by Aevah for BUILT · October 2026

## In brief

Mo is BUILT's demand intelligence platform, built and run by Aevah. It brings together BUILT's retail sales data and
BUILT's own business data, and turns them into forecasts, cannibalization reads, price-sensitivity reads and
retailer-level views that BUILT's teams can use directly.

Three principles shape everything in Mo:

**The numbers come from models, not from generated text.** Every forecast, probability and sensitivity figure in Mo
is calculated by machine-learning and statistical models trained on BUILT's data, and stored with the date and model
version that produced it. Mo's conversational assistant explains those numbers; it does not create them.

**Every number can be traced.** Results carry when they were produced, which model version produced them and which
data they came from, so a figure in a report can be followed back to its source.

**Your data stays governed.** BUILT's data sits in a secured data store. The Mo app reaches it only through fixed,
pre-defined data requests, never free-form queries. [[ROB: hosting, encryption, access-control statements to add
here once confirmed]]

## What Mo does for BUILT

<!-- sources: ACCURACY_CLAIMS_REGISTER messaging stance (lead features); README/memory feature set -->
**Demand forecasting.** Forecasts of BUILT's sales by item and retailer, 13 weeks ahead, built around what actually
drives BUILT's growth: how many stores carry an item and how fast it sells in each store.

**Cannibalization.** When a new item launches, how much of its sales are new to BUILT and how much come out of
BUILT's existing items, with the reasons behind each read.

**Price sensitivity.** How strongly sales respond to price changes and promotions, for BUILT and its competitive set.

**Retailer and portfolio views.** Performance, distribution and trends for each retailer and across the portfolio.

**Mo Chat.** A conversational assistant that answers questions about the numbers on screen and explains them in
plain language.

## How Mo is built

<!-- sources: docs/aevah_platform_pipeline_and_llm_boundary.md sections 2, 4, 5 (architecture, not its retracted
figures); customer-built-mo-api code: fixed endpoints (app/routers), authenticated data store (app/druid.py) -->
Mo is organized in five layers, each with one job:

| Layer | What it does |
|---|---|
| 1. Data intake | New retail and business data arrive on their own schedules (weekly for retail sales). Each delivery is checked for completeness and consistency before it is used. |
| 2. Secure data store | A secured analytics data store holds BUILT's data at the level of item × retailer × week, alongside the full category so competitors and the market can be measured. |
| 3. Preparation | Raw rows become business language: product lines, pack sizes, flavors, retailers, calendar and promotions. This happens inside the data store, under the same controls. |
| 4. Machine learning | Models are trained on the prepared data and produce forecasts, cannibalization scores and price-sensitivity estimates. Results are written back to the data store with their date, model version and source. |
| 5. Mo app and Mo Chat | BUILT's users see results through the Mo app. The app requests data only through fixed, pre-defined requests, so no one can run an arbitrary query against the data store from the app. |

When new data arrives, the preparation and scoring steps are re-run so Mo reflects the latest week.
[[ROB: confirm the refresh process and cadence in production; monitoring and change control, if we want to
mention them]]

## How Mo uses machine learning

<!-- sources: SETTLED_FINDINGS (5-seed direct model, validation protocol, forward test); MO_142 brief methods;
scored_cannibalization schema (shap_feature_1..3, model_version); no accuracy numbers -->
Machine learning in Mo means models that learn patterns from BUILT's history and are then tested on periods they
have not seen. Each job has a model suited to it:

**Forecasting** uses gradient-boosted decision trees: many small decision rules, each correcting the last, trained
on sales history, distribution, pricing, promotions and seasonality across BUILT's items and retailers. The model is
trained several times with different random starting points and the results averaged, which makes the forecast
steadier.

**Cannibalization** is scored by a classification model that compares new items with existing items, and each score
is stored with the three factors that drove it most, so the reason travels with the number.

**Price sensitivity** is estimated from how weekly sales move as prices and promotions change, item by item.

**How forecasts are tested before BUILT relies on them.** Aevah tests every forecasting change the way a finance
team would want it tested:

- **Rewind and compare.** We go back to earlier dates, forecast forward using only what was known then, and compare
  with what actually sold, at the item, retailer and portfolio level.
- **Simple yardsticks.** Every model is compared with simple rules a planner could use, such as "assume recent
  sales continue" and "recent weekly sales rate × current store count", and the comparison is reported.
- **Predictions written down first.** Before a test runs, we record what we expect, so a result cannot be
  explained away afterward.
- **Independent review.** Every result is checked by a separate reviewer who tries to break it before it is
  reported.
- **Forward confirmation.** Forecasts are saved before the weeks they cover, then scored once those weeks have
  happened.

We do not change the forecast BUILT sees unless a new approach passes a rule we wrote down before testing it,
including consistency across forecast dates and a check that it does not drift high or low through the seasons.

## How Mo is different from generative AI products

<!-- sources: docs/aevah_platform_pipeline_and_llm_boundary.md sections 1, 3; mo_chat.py prompt rules ("Never
invent data", "Do not guess or fabricate -- use a tool instead") -->
Generative AI tools, such as chat assistants, write fluent text by predicting likely words. That makes them good at
explaining and summarizing, and unreliable as a source of numbers: they produce figures that sound plausible, not
figures calculated from your data. Mo is built the other way around.

| | Generative AI tools | Mo |
|---|---|---|
| Where numbers come from | Generated text; plausible but not calculated | Calculated by models trained and tested on BUILT's data |
| Same question, same answer | Not guaranteed | Yes: results are stored and versioned |
| Traceability | Hard to tie an answer to a source | Each result carries its date, model version and source data |
| Scale of data | Limited to what fits in a prompt | Millions of weekly records, processed in the data store |
| Testing | Rarely tested against outcomes | Tested against what actually sold, before and after release |

**Where Mo does use generative AI.** Mo Chat uses an AI language model to understand questions and explain answers in
plain English. When you ask a question, Mo Chat retrieves the relevant figures from the data store at that moment and
explains them; it is instructed never to invent or estimate data, and to look figures up instead. The language model
does not calculate the forecasts or scores.
[[ROB: which language model provider is used in production; what data is sent with a question; provider terms on
training and retention; whether a fully local option is offered so no data leaves Aevah's environment]]

## Where Mo's data comes from

<!-- sources: wiki/02 data classes + status table; MO_141 (shipments file); DRUID_LOAD_LIST (trade promotions, item
attributes); Brian 2026-10-14 (nutrition from SPINS); feedback_client_artifact_tech_refs (FRED may be credited) -->
| Source | What it provides | Status |
|---|---|---|
| SPINS weekly retail sales | Sales, prices, promotions and distribution for BUILT and the full category at about 80 retailers, each retailer's own stores | In use |
| SPINS product details | Product attributes, including nutrition facts | Available |
| Circana | Sales for Costco, which SPINS does not cover | In use |
| BUILT's NetSuite shipments | Billed shipments, used for retailers with no store-level sales data (WinCo, ALDI, H-E-B, Trader Joe's) | Being added |
| BUILT's trade promotion calendar | Planned trade promotions by customer | Loaded; being added to analysis |
| BUILT's item information | Item list, product lines and pack details | Loaded |
| Public economic data (Federal Reserve Economic Data) | Economic context such as consumer spending and prices | In use |

Retail sales data are weekly and arrive with a lag of a few weeks, so Mo always states the latest week it covers.

## Security and data handling

<!-- sources: customer-built-mo-api code (fixed endpoints, authenticated data store, Mo Chat client token);
wiki/08 and wiki/18 (SSO and role-based access are plans); runpodagent policy (credentials kept out of training
code). Everything else waits for Rob. -->
**In place today:**
- BUILT's data sits in a data store that requires authenticated access.
- The Mo app reaches data only through fixed, pre-defined requests; it cannot run free-form queries.
- Mo Chat requires an authenticated client. [[ROB: confirm this check is on in production]]
- Mo Chat is instructed not to reveal system details, data structures or proprietary methods.
- Model training runs in isolated, short-lived compute jobs, with access credentials kept out of the training code.

[[ROB: to add, once confirmed]]
- Where BUILT's data is hosted, and whether it is dedicated to BUILT.
- Encryption in transit and at rest.
- Backups and data retention, including what happens to BUILT's data if the engagement ends.
- How users sign in (individual accounts today; single sign-on through BUILT's identity provider is planned).
- Role-based access by team (planned tiers: finance and leadership; sales by their own customers; operations).
- Who at Aevah can access BUILT's data, and how that access is logged.
- Where model-training data is processed (currently a cloud GPU service; storage region to confirm).
- Certifications or audits, if any; if there are none, the document will not imply any.

## Keeping the numbers honest

Mo's results carry the date they were produced and the model version that produced them. Forecasts are also saved
as versions, so an earlier forecast can be compared with what actually sold. [[ROB/JASON: confirm for the
production tables]]

Forecast accuracy is reported with context, never as a headline: what was measured, at what level (item, retailer
or portfolio), how far ahead, compared with what simple rule, and on how much data.

## Questions

Aevah · [[JASON: contact name and email]]
