# Brad's Product Cannibalization Modeling Plan for Aevah

This document preserves the original modeling plan while adapting it to an Aevah-centered implementation. The core modeling logic remains the same, but the operating model changes. In Aevah, the cannibalization solution should be designed as a governed intelligence product with traceable inputs, explainable predictions, and business-facing outputs that can be consumed by dashboards, executives, and AI agents.

## What changes when the data is loaded into Aevah

Aevah changes the plan in several important ways:

- the governed semantic layer becomes a first-class requirement
- entity resolution and standardized business definitions move earlier in the project
- explainability and lineage are part of the design, not a later add-on
- outputs should be business-facing and scenario-ready from the start
- the final product should support both human decision-makers and agent workflows

The result is not just a model, but a production intelligence asset that fits inside Aevah's governed analytics and agentic execution environment.

## 1. Establish the governed semantic layer first

Before serious feature engineering begins, build a canonical semantic model for the core business entities needed by the project:

- product / UPC
- brand
- product hierarchy and subcategory
- geography
- retailer / channel
- calendar week
- price
- promo
- distribution
- base and observed demand

This work should define one trusted version of key concepts such as:

- active distribution
- promo week
- launch week
- cannibalization event
- incrementality
- gross versus net lift

Inside Aevah, that semantic layer becomes the foundation for every model, dashboard, and agent response downstream.

## 2. Make data unification and lineage explicit

Because Aevah emphasizes one governed truth, early project work should focus on:

- standardizing product identifiers and hierarchies
- resolving geography and retailer naming inconsistencies
- defining data lineage from raw SPINS fields to modeled features
- documenting which source columns feed each feature and metric
- flagging derived fields that could introduce leakage

This reduces confusion later when predictions need to be explained to commercial teams or audited by leadership.

## 3. Keep the modeling grain centered on weekly panel data

The base modeling grain should still be:

- `UPC x Geography x Week`

That grain is appropriate for:

- launch analysis
- promo-driven substitution
- distribution-driven cannibalization
- ongoing demand transfer monitoring

If needed, Aevah can surface rollups above this grain for brand, segment, channel, or geography-level intelligence.

## 4. Define the product hierarchy and competitive set in governed form

Cannibalization depends on realistic substitution pools. In the Aevah implementation, competitive sets should be expressed as governed business logic rather than informal notebook assumptions.

These definitions should use:

- brand
- pack count / size
- flavor
- nutrition attributes such as protein tier
- category / subcategory metadata
- price tier
- geography / channel context

The outcome should be a reusable competitive-set framework that supports both model training and downstream business explanations.

## 5. Expand the target design to match Aevah's business orientation

The original plan focused on `Base Units` and `Units`. In Aevah, I would broaden that target framework to include:

- unit cannibalization
- dollar cannibalization
- margin cannibalization

Recommended starting targets:

- `Base Units` for underlying demand shifts
- `Units` for observed operational effects
- dollar and margin views once the unit model is stable

This aligns the model output with executive decision-making and margin-oriented use cases.

## 6. Engineer features as reusable governed feature views

Rather than building features only for one model training workflow, create reusable feature views that can serve:

- predictive modeling
- dashboard metrics
- ad hoc business analysis
- AI agent queries

Feature families should still include:

### Own-item features

- price
- promo depth
- ACV
- TDP
- item age
- seasonality
- launch timing
- base productivity

### Competitive-set features

- competitor count
- average competitor price
- competitor promo intensity
- competitor distribution strength
- competitor assortment breadth
- weighted same-segment pressure

### Same-brand pressure features

- active same-brand SKU count
- same-brand promo intensity
- same-brand price ladder
- overlap in size, flavor, and protein band
- new launch flags

### Market context features

- geography effects
- retailer / channel effects
- holiday and seasonal effects
- category velocity
- category promo intensity

All of these should have documented lineage and stable business definitions.

## 7. Create a measurement layer before the prediction layer

Before building predictive models, create governed historical measurement views inside Aevah that answer questions like:

- what happened to incumbent SKUs after a new SKU launch
- what happened after a sibling SKU gained promo support
- what happened when assortment breadth changed
- what happened when distribution expanded for a related SKU

These views should act as the factual foundation for both:

- validating the modeling assumptions
- supporting business users who want historical evidence before trusting predictions

## 8. Build interpretable baseline models first

The first predictive models should still prioritize interpretability and robustness:

- regularized regression
- gradient boosting models such as LightGBM or XGBoost
- panel or mixed-effects regression with geography and time effects

Because Aevah emphasizes explainable intelligence, interpretable baselines are especially valuable. More complex approaches should only be added when they clearly improve performance and remain explainable enough for commercial use.

## 9. Publish driver-level explainability outputs

In Aevah, prediction alone is not enough. Each prediction should ideally be accompanied by explainability artifacts that support human and agent consumption, such as:

- top contributing drivers of predicted cannibalization
- whether the pressure is same-brand or external
- role of promo, price, and distribution
- confidence or uncertainty bands
- comparable historical examples

These outputs make the model usable in executive and operational workflows.

## 10. Design validation around future use, not random splits

Validation remains critical and should be aligned to how the business will use the solution. Recommended validation structures:

- forward-chaining time splits
- holdout geographies
- holdout launch periods
- holdout brands or product families where relevant

Validation in Aevah should also be transparent and documented so leadership can understand when and where the model is most reliable.

## 11. Design business-facing outputs from the start

The prediction layer should feed business-facing outputs such as:

- predicted cannibalized units by SKU
- expected donor SKUs and recipient SKU
- cannibalization rate as a percent of incremental demand
- dollar and margin impact
- market-level and retailer-level views
- launch and promo scenario estimates

This ensures the work is useful for assortment planning, launch strategy, pricing, and promotion optimization.

## 12. Make the outputs agent-ready

Because Aevah supports agentic execution, the outputs should be structured so an AI agent can reliably answer questions such as:

- which SKUs are most at risk of cannibalization next quarter
- what is driving the predicted cannibalization for a given launch
- which geographies are most vulnerable if a specific promo runs
- which existing items are most likely to donate demand to a new SKU

That means the model outputs should include:

- prediction values
- ranked donor relationships
- driver fields
- explanation text or explanation-ready metadata
- scenario inputs and outputs

## 13. Build scenario intelligence, not only static reporting

Once the base prediction layer is working, add scenario support for:

- launching a new SKU in selected markets
- promoting a SKU at different discount depths
- expanding distribution
- removing a low-velocity item
- reshaping the assortment within a brand or segment

This is where the Aevah implementation becomes an active planning tool rather than a retrospective analytics asset.

## 14. Operationalize with monitoring and governance controls

After deployment, monitor:

- prediction drift
- feature drift
- cold-start performance
- changes in promo mechanics
- geography and channel degradation
- changes in competitive-set behavior

Operationalization should also include:

- feature versioning
- target definition versioning
- retraining cadence
- model lineage
- auditability of business outputs

## Recommended Aevah implementation sequence

The recommended sequence for this version of the project is:

1. establish the governed semantic layer for product, market, calendar, and demand
2. define the competitive-set and product hierarchy logic in governed business terms
3. create reusable feature views for price, promo, distribution, and competitive pressure
4. publish historical measurement views for launch, promo, and distribution effects
5. train interpretable baseline models for unit cannibalization prediction
6. add dollar and margin-oriented views after unit modeling is stable
7. publish explainability outputs and decision-facing metrics
8. expose scenario-ready outputs for dashboards and agent workflows
9. monitor drift, lineage, and performance over time

## Biggest risks in the Aevah version

The main risks remain similar to the original plan, but with added emphasis on governed delivery:

- weak or inconsistent entity definitions
- feature leakage from derived POS fields
- poorly defined competitive sets
- overcomplicated models that are hard to explain
- outputs that predict well but do not support business decisions
- lack of alignment between model outputs and executive KPIs such as margin

## Relationship to the original plan

This Aevah-specific plan does not replace the original plan in `docs/brad_cannibalization_plan.md`. It is a companion artifact that adapts the same modeling strategy to a governed intelligence platform and agent-ready delivery model.
