# Brad's Cannibalization Prediction Capabilities

This document describes what the project should be able to predict from the SPINS dataset, assuming access to the full dataset of approximately 95 million rows spanning at least 3 years of weekly history.

It is intended to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_implementation_blueprint.md`
- `docs/brad_cannibalization_data_requirements.md`

## Assumptions

The prediction capabilities described here assume:

- the data is available at a stable weekly panel grain such as `UPC x Geography x Week`
- the full dataset contains repeated observations across products, markets, and time
- the source includes demand, pricing, promotion, and distribution signals similar to those seen in the sample extract
- product hierarchy and competitive-set logic can be defined reliably

## What this dataset should support

With the full dataset, the project should be able to predict several forms of cannibalization-related behavior at the SKU, market, and event levels.

## 1. Demand loss risk for a focal SKU

The model should be able to estimate:

- which SKUs are likely to lose demand
- how much demand loss is likely in units
- how much demand loss is likely in dollars
- whether the expected loss is material or minor

This is the most direct cannibalization prediction use case.

## 2. Donor and recipient relationships

The model should be able to estimate:

- which SKU is likely to gain demand
- which SKU or group of SKUs is likely to lose demand
- the strength of donor-recipient relationships
- whether substitution is primarily within brand or across competing brands

This is especially valuable for launch planning and portfolio management.

## 3. Cannibalization intensity

The project should be able to estimate:

- cannibalized units
- cannibalized dollars
- cannibalization rate as a share of incremental demand
- gross lift versus net incremental gain

These measures help distinguish between true growth and internal demand transfer.

## 4. Launch cannibalization

For a new item introduction, the model should be able to predict:

- how much volume the new SKU is likely to take from existing portfolio items
- which incumbent SKUs are most exposed
- which markets or retailers are most vulnerable
- whether the launch appears incremental or portfolio-destructive

This is one of the strongest and most commercially useful applications.

## 5. Promotion-driven cannibalization

The project should be able to estimate:

- how much one SKU's promotion is likely to pull from sibling or nearby items
- which promo types are most likely to create internal switching
- how promo-driven substitution varies by market, retailer, or segment
- whether promotional lift is mostly incremental or mostly transferred

This is particularly useful for revenue management and trade planning.

## 6. Distribution-driven cannibalization

The project should be able to estimate:

- what happens when a SKU gains ACV or TDP
- whether broader availability creates net new demand or demand transfer
- which existing items lose volume when a related SKU expands distribution
- where distribution shifts create the strongest internal portfolio pressure

## 7. Assortment cannibalization

The project should be able to estimate:

- the impact of adding a SKU to an assortment
- the impact of removing a SKU
- which assortments are likely over-segmented or overcrowded
- which low-velocity items are likely donors with limited incremental portfolio value

This supports assortment rationalization and portfolio design.

## 8. Market and retailer sensitivity

The model should be able to identify:

- geographies with stronger cannibalization risk
- retailers or channels where substitution is more aggressive
- segments where consumers switch more readily
- markets where launches or promotions are more likely to redistribute existing demand

This helps localize decisions rather than treating all markets the same.

## 9. Same-brand versus external substitution

The project should be able to estimate:

- the share of demand transfer that stays within brand
- the share of demand transfer that comes from competitors
- whether a tactic is mostly expanding category demand or reshuffling share
- whether a new SKU is helping or hurting the broader portfolio

This is important for interpreting whether a commercial action is actually creating value.

## 10. Scenario-based planning outputs

With strong feature engineering and stable historical data, the project should support scenario predictions such as:

- launching a new SKU in selected markets
- changing the price of a SKU
- promoting a SKU at different discount depths
- expanding or narrowing distribution
- removing a low-velocity item
- changing the assortment structure within a brand or segment

These scenarios are where the model becomes a planning tool instead of just a reporting tool.

## Strongest likely first-release outputs

The most realistic and useful first-release outputs are:

- predicted donor SKUs
- predicted recipient SKU
- predicted cannibalized units
- predicted cannibalized dollars
- cannibalization rate
- views by `UPC x Geography x Week`
- event-based outputs for launches, promotions, and distribution changes

These outputs are grounded in what weekly POS data tends to support well.

## What the dataset does not fully support on its own

Even at full scale, POS data alone has limits. The project will probably not support perfect prediction of:

- household-level switching behavior
- shopper intent
- exact consumer-level substitution paths
- causal truth without explicit event design and controls

This means the project should be framed as:

- SKU-level and market-level cannibalization prediction
- event-level and portfolio-level demand transfer estimation

and not as a direct replacement for household panel analysis.

## Practical interpretation

The full SPINS dataset should be strong enough to build a serious cannibalization intelligence capability if:

- the weekly panel is stable
- competitive sets are defined well
- leakage from derived metrics is controlled
- validation is done across time and markets

Under those conditions, the data should support both:

- retrospective measurement of historical demand transfer
- forward-looking prediction of cannibalization risk

## Recommended framing for stakeholders

The simplest way to describe the capability is:

The system can estimate which SKUs are likely to lose demand, which SKUs are likely to gain that demand, how much of the gain is truly incremental, and how those effects change across launches, promotions, distribution changes, and assortment decisions.
