# Brad's NPI Cannibalization Prediction and Trust Framework

This document describes what the project should be able to predict for new product introduction (NPI) cannibalization, and how much confidence stakeholders should place in those predictions when using the full SPINS dataset of approximately 95 million rows over at least 3 years.

It is intended to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_prediction_capabilities.md`

## Objective

For new product introduction, the goal is not only to estimate whether a new SKU will sell, but also to estimate where that demand is likely to come from.

In practice, this means predicting:

- which existing SKUs are likely to lose demand
- how much demand they are likely to lose
- whether the new SKU is mostly incremental or mostly cannibalistic
- which markets or retailers are most vulnerable

## What we should be able to predict for NPI

Assuming stable weekly panel data and strong competitive-set definitions, the project should be able to estimate the following for a new product introduction.

## 1. Likely donor SKUs

The model should be able to identify:

- which existing SKUs are most likely to donate volume to the new SKU
- whether those donor SKUs are mostly within the same brand
- whether demand transfer is likely to come from close substitutes or broader competitive items

This is one of the most useful NPI outputs because it helps teams understand portfolio exposure.

## 2. Expected cannibalized units

The model should be able to estimate:

- unit loss by incumbent SKU
- total portfolio units likely to be cannibalized
- range of plausible cannibalized units under different launch conditions

This supports launch planning, assortment decisions, and post-launch performance interpretation.

## 3. Expected cannibalized dollars

The model should be able to estimate:

- dollar loss by incumbent SKU
- total portfolio dollar transfer
- relationship between gross launch sales and net revenue impact

This is important because a launch can appear commercially strong in gross terms while still being weak in net portfolio value.

## 4. Incremental versus transferred demand

The model should be able to estimate:

- what share of the new SKU's demand is incremental
- what share is transferred from existing items
- whether the launch is mostly portfolio additive or mostly self-cannibalizing

This is often the most strategically important NPI output.

## 5. Market-specific launch vulnerability

The model should be able to estimate:

- which geographies are most likely to experience demand transfer
- which retailers or channels are most vulnerable
- where the new SKU is most likely to be additive versus destructive

This enables more targeted launch strategies instead of assuming uniform impact everywhere.

## 6. Product-attribute-driven cannibalization risk

The model should be able to estimate whether cannibalization risk is higher when the new SKU is similar to existing items on dimensions such as:

- brand
- flavor
- pack size
- protein band or nutrition profile
- price point
- promo profile
- distribution footprint

This helps explain not just what the prediction is, but why it is happening.

## 7. Launch scenario sensitivity

The model should be able to compare launch scenarios such as:

- launching in selected markets versus broad rollout
- launching with different price points
- launching with different promo support
- launching with different distribution levels
- launching alongside assortment rationalization versus without it

This turns the prediction system into a planning tool rather than a post-hoc reporting tool.

## What we can trust most

In NPI cannibalization prediction, trust is usually strongest for:

- ranking which incumbent SKUs are most exposed
- determining whether a launch is likely to be mostly incremental or mostly transferred
- identifying which markets are relatively more or less vulnerable
- detecting likely within-brand cannibalization

These are the areas where historical POS data tends to be most useful and stable.

## What we should trust somewhat less

Trust is usually lower for:

- exact point estimates with high numeric precision
- predictions for completely novel products with no close analogs
- long-range forecasts far beyond the launch window
- situations where distribution or promo assumptions are still uncertain

In other words, the model is usually more reliable for directional and comparative decisions than for pretending to know the exact future with perfect precision.

## High-confidence prediction conditions

Prediction confidence is highest when:

- the new SKU has close historical analogs in the dataset
- the category has many prior launches
- product attributes are well defined
- competitive sets are clean and realistic
- the target markets have stable weekly history
- launch assumptions for price, distribution, and promo are known

Under these conditions, the model should be very useful for ranking risk and estimating realistic cannibalization ranges.

## Medium-confidence prediction conditions

Prediction confidence is moderate when:

- the new SKU is somewhat differentiated but still comparable to prior products
- the category has launch history, but not many exact analogs
- the market context is somewhat noisy
- some launch assumptions are still variable

In these cases, the predictions should still be useful for scenario comparison and directional planning, but not treated as exact forecasts.

## Low-confidence prediction conditions

Prediction confidence is lowest when:

- the new SKU is truly novel or category-creating
- the product hierarchy is incomplete
- the competitive set is poorly defined
- the retailer or market history is sparse
- the launch plan is highly uncertain
- the historical data contains few comparable events

In these cases, the model should be framed as a structured estimate with wide uncertainty rather than a strong operational commitment.

## Recommended way to express trust

The project should avoid presenting NPI predictions as single numbers without context. A better output format is:

- likely donor SKUs
- expected cannibalization range
- expected incremental share versus transferred share
- confidence level
- top drivers of the prediction

This provides a much more trustworthy and decision-useful view than an isolated point estimate.

## Suggested confidence labels

A simple confidence framework can be used in business outputs:

### High confidence

- strong historical analogs
- stable market history
- clear competitive-set relationships
- reliable launch assumptions

### Medium confidence

- partial analogs
- moderate uncertainty in transfer magnitude
- generally usable for planning and comparison

### Low confidence

- highly novel product
- weak analog history
- uncertain launch assumptions
- wide plausible range of outcomes

## Practical interpretation for stakeholders

The cleanest way to describe the capability is:

For a new product introduction, the system can estimate which existing SKUs are most likely to lose demand, how much of the new SKU's volume is truly incremental versus transferred, and where that effect is likely to be strongest across markets and retailers.

That prediction should be trusted most as:

- a ranking tool
- a scenario comparison tool
- a portfolio risk assessment tool

and less as:

- an exact unit-level prophecy
- a substitute for shopper-level panel analysis

## Bottom line

With the full dataset, the project should be able to produce useful and commercially actionable NPI cannibalization predictions. The highest value will come from:

- identifying likely donor SKUs
- estimating the degree of self-cannibalization
- distinguishing incremental growth from internal transfer
- comparing alternative launch strategies

The output should be treated as decision support with explicit confidence framing, not as an oracle.
