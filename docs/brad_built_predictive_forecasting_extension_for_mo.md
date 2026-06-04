# BUILT Predictive Forecasting Extension for Mo

This note defines how to add predictive forecasting capabilities to the BUILT cannibalization model, tool workflow, and Mo UI while preserving the strongest current product direction:

- polished, not experimental
- narrow and great, not wide and noisy
- deterministic evidence first
- ML used for ranking, forecasting, and prioritization
- visible confidence, assumptions, and provenance
- recommendations that lead to assortment action

The goal is not to turn Mo into a generic forecasting dashboard. The goal is to help BUILT answer a small number of future-facing commercial questions with enough confidence to guide decisions.

## Product Principle

Mo should keep the current guided flow:

```text
Priority event -> focused diagnosis -> explanation -> assortment action
```

Forecasting should be added as a controlled planning layer:

```text
Current evidence -> forecasted outcome range -> likely donor exposure -> recommended next move
```

The UI should avoid open-ended model controls on the first screen. Scenario inputs belong behind clear business actions such as:

- expand this SKU
- hold expansion
- add a new pack size
- reduce overlap
- replace a low-productivity pack
- test in selected markets

## Forecasting Questions to Support First

The first release should support only the questions most aligned to the existing pack-ladder and launch workflow.

### 1. What happens if we expand this SKU?

Example:

```text
If Mint Brownie 4pk expands in Grocery from 63 to 80 TDP, what is the likely net portfolio effect?
```

Outputs:

- forecasted focal units range
- forecasted donor unit loss range
- net incremental units range
- likely affected SKUs
- markets where expansion is safest
- markets where expansion should be held

### 2. Which markets should we expand into next?

Example:

```text
Where does Brownie Batter 4pk look most likely to grow incrementally without hurting 1ct?
```

Outputs:

- ranked geographies or channels
- forecasted incremental share
- cannibalization risk label
- confidence label
- top reason for each recommendation

### 3. Should we keep all pack sizes?

Example:

```text
If the 4pk remains, should the 1ct and 12pk both stay in Grocery?
```

Outputs:

- forecasted pack-ladder health
- expected role by pack
- keep / monitor / reduce recommendation
- projected win percentage
- donor exposure range

### 4. What is the risk of a proposed new pack?

Example:

```text
If BUILT launches an 8pk for Mint Brownie, which existing packs are most exposed?
```

Outputs:

- likely donor ranking
- expected cannibalized units range
- expected incremental share range
- highest-risk geographies
- comparable historical analogs

## ML Additions

Forecasting needs a separate model layer from retrospective scoring.

### Current retrospective layer

Purpose:

- measure what happened
- explain current events
- identify donor patterns
- label past launches as incremental, watch, or cannibalizing

Uses:

- pre/post metrics
- observed donor declines
- realized changes after launch
- event significance tests

### New predictive layer

Purpose:

- estimate what is likely to happen under a proposed future action
- compare scenarios before the business commits
- rank markets and SKUs by forward risk

Uses only information available before the forecast horizon:

- current and trailing demand
- current and trailing productivity
- current and trailing TDP / ACV
- price and promo history
- product relationship features
- pack count and flavor similarity
- geography and channel history
- category seasonality
- launch age and lifecycle stage
- historical analog outcomes
- proposed scenario assumptions

The most important modeling rule:

```text
Do not train the forecasting model on post-event outcome features that would not be known at prediction time.
```

## Recommended Forecasting Model Stack

Use a pragmatic stack, not one giant model.

### 1. Baseline demand forecast

Forecast each SKU's expected demand if no new action is taken.

Targets:

- `base_units_next_4w`
- `base_units_next_13w`
- `units_tdp_next_4w`
- `units_tdp_next_13w`

Useful models:

- gradient boosted trees with lag features
- hierarchical time-series baseline by SKU, geography, and channel
- simple seasonal baseline as a fallback for sparse SKUs

### 2. Scenario adjustment model

Estimate the lift or decline from a planned action.

Actions:

- distribution expansion
- new pack launch
- price change
- promo support
- SKU reduction or removal

Outputs:

- focal lift range
- donor loss range
- net incremental range
- confidence label

### 3. Donor exposure model

Rank which comparison SKUs are most exposed under the scenario.

Features:

- relationship distance
- same specific flavor flag
- same family flag
- pack-size difference
- price-per-unit distance
- baseline velocity similarity
- distribution overlap
- historical opposition rate
- co-win rate
- promo overlap

Outputs:

- top likely donor SKUs
- donor attribution weights
- donor confidence

### 4. Market selection model

Rank geographies and channels by expected net benefit.

Outputs:

- best expansion markets
- risky markets to hold
- markets needing more data
- expected net incremental range by market

## Scenario Output Table

The predictive layer should create a governed output table at a scenario grain:

```text
scenario_id
scenario_type
focal_upc
comparison_pool_id
geography
channel
forecast_start_week
forecast_horizon_weeks
scenario_tdp_change
scenario_price_change
scenario_promo_depth
forecast_focal_units_low
forecast_focal_units_mid
forecast_focal_units_high
forecast_donor_units_loss_low
forecast_donor_units_loss_mid
forecast_donor_units_loss_high
forecast_net_incremental_units_low
forecast_net_incremental_units_mid
forecast_net_incremental_units_high
forecast_incremental_share_low
forecast_incremental_share_mid
forecast_incremental_share_high
top_donor_skus
market_rank
recommended_action
confidence_label
top_drivers
model_version
score_timestamp
```

## UI Additions

Forecasting should be added to Mo as one new guided screen plus small forecast cards in existing screens.

## New Screen: Forecast Next Move

Purpose:

Help users choose the next action from a small set of business-safe options.

Layout:

```text
Forecast next move
Focal: Mint Brownie 4pk | Pool: same specific flavor pack ladder | Grocery

Choose action:
[ Hold current distribution ]
[ Expand selectively ]
[ Expand broadly ]
[ Reduce overlapping pack ]
[ Test selected markets ]

Scenario assumptions:
TDP: 63 -> 80
Promo: no change
Price: stable
Horizon: next 13 weeks

Mo forecast:
Net incremental units: +180 to +420
Likely donor loss: -90 to -240
Incremental share: 55% to 72%
Confidence: Medium

Recommended move:
Expand selectively in Club and Northeast.
Hold Texas and Mountain West until productivity improves.
```

## Existing Screen Additions

### Priority Events

Add forecast callouts only when actionable:

```text
Forecasted risk if expanded broadly
Mint Brownie 4pk | Grocery | next 13 weeks
Expected donor exposure: 1ct and 12pk
Recommended next step: expand selectively, not broad rollout
```

### SKU Summary

Add one compact forecast tile:

```text
Next 13-week outlook
Net incremental units: +180 to +420
Cannibalization risk: Medium
Best next action: Expand selectively
```

### Geography View

Add a forecast column:

| Geography | Current status | Forecast if expanded | Action |
|---|---|---|---|
| Club | Incremental | Low risk | Expand |
| Texas | Watch | Medium risk | Hold |
| Mountain West | Cannibalizing | High risk | Reduce overlap |

### Pack Ladder

Add a pack-role forecast:

| Pack | Current role | Forecasted role | Action |
|---|---|---|---|
| 1ct | Core donor | Still core, exposed | Protect |
| 4pk | Focal | Growth pack | Expand selectively |
| 12pk | Minor donor | Low velocity | Monitor / reduce |

### Assortment Action

Add expected outcome ranges beside the recommendation:

```text
Expand selectively
Expected net incremental units: +180 to +420
Expected donor loss: -90 to -240
Confidence: Medium
```

## UI Guardrails

To keep the product polished:

- show ranges, not false-precision point forecasts
- show confidence labels prominently
- always show the assumptions used
- always show the comparison pool
- suppress forecasts when evidence is too sparse
- avoid editable model internals
- limit scenario controls to business levers
- explain forecasts in business language
- keep "Forecast next move" behind the current diagnosis, not before it

## Forecast Confidence Labels

### High

Use when:

- close historical analogs exist
- SKU has stable recent selling history
- comparison pool is clean
- geography has enough observations
- scenario assumptions are modest

User-facing language:

```text
High confidence. Similar launches and distribution expansions have occurred often enough for a stable estimate.
```

### Medium

Use when:

- partial analogs exist
- recent history is usable but not deep
- scenario assumptions are reasonable but not exact
- geography is somewhat noisy

User-facing language:

```text
Medium confidence. This is useful for comparing options, but the range should be treated as directional.
```

### Low

Use when:

- SKU is too new
- market history is sparse
- no close analogs exist
- scenario assumptions are large or uncertain
- forecast range is too wide

User-facing language:

```text
Low confidence. Mo can structure the risk, but this should not drive a major rollout decision without more evidence.
```

## Implementation Phases

### Phase 1: Forecast cards from current evidence

Use existing model outputs and deterministic rules to produce directional forecast cards:

- low / medium / high forecasted risk
- likely donor exposure
- safest geographies
- recommended next action

This can be implemented before full unit-range forecasting.

### Phase 2: 4-week and 13-week demand forecast

Add SKU-level forecasts:

- focal units
- donor units
- net incremental units
- incremental share

Start with same-specific-flavor pack ladders only.

### Phase 3: Scenario comparison

Let users compare two or three controlled options:

- hold
- selective expansion
- broad expansion

Keep controls simple and tied to business levers.

### Phase 4: NPI / new pack planning

Support proposed new pack or SKU launches using historical analogs.

Outputs:

- likely donors
- expected incremental share range
- high-risk geographies
- recommended pilot markets

## What Not to Add Yet

Avoid these in the polished client version:

- open-ended "ask any forecast" prompts
- editable algorithm settings
- dozens of future curves
- SKU-level precision beyond what POS data can support
- long-range forecasts beyond the launch or planning window
- full-category competitive simulations before same-flavor pack ladders are trusted

## Bottom Line

Forecasting should make Mo more action-oriented, not more complicated.

The strongest first forecasting addition is:

```text
Given what we know now, what should BUILT do next with this SKU, and what range of portfolio impact should they expect?
```

That keeps the product narrow, polished, and commercially useful while adding meaningful predictive ML capability.
