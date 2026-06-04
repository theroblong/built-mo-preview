# Brad's Cannibalization Project Roadmap

This document turns the cannibalization strategy, blueprint, diagrams, and data requirements into a phased delivery roadmap. It is intended to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_implementation_blueprint.md`
- `docs/brad_cannibalization_diagrams.md`
- `docs/brad_cannibalization_data_requirements.md`

The goal is to provide a realistic path from project kickoff to first production use.

## Objective

Deliver a governed cannibalization prediction capability in Aevah that can:

- measure historical demand transfer
- predict SKU-level cannibalization risk
- support assortment, launch, pricing, and promotion decisions
- provide explainable outputs for dashboards and AI agents

## Planning assumptions

This roadmap assumes:

- the project starts with one category or subcategory
- 2 to 3 years of weekly history are available
- the initial scope is a pilot, not an enterprise-wide rollout
- Aevah is the governed platform for data, semantics, and delivery
- the team can access product hierarchy, geography mappings, and POS history

## Recommended delivery horizon

Recommended initial pilot timeline:

- 12 to 16 weeks

This is long enough to build something credible and governed, but short enough to preserve momentum and business sponsorship.

## Phase summary

The recommended phases are:

1. project alignment and scope lock
2. data foundation and semantic layer
3. historical measurement and target design
4. feature engineering and baseline modeling
5. validation, explainability, and business packaging
6. pilot deployment and monitoring

## Phase 1: Project alignment and scope lock

**Suggested duration**

- Weeks 1 to 2

**Primary goals**

- lock the business definition of cannibalization
- choose the first category or brand scope
- choose the first use case such as launch, promo, or assortment cannibalization
- confirm success criteria and pilot stakeholders

**Key activities**

- stakeholder working sessions
- review of available SPINS and hierarchy data
- agreement on analytical grain
- agreement on pilot outputs
- approval of core business definitions

**Primary deliverables**

- agreed scope statement
- approved business definitions
- initial project charter
- stakeholder map and ownership model

**Exit criteria**

- no ambiguity about the first business question
- pilot category and market scope approved
- executive sponsor and working team aligned

## Phase 2: Data foundation and semantic layer

**Suggested duration**

- Weeks 2 to 5

**Primary goals**

- build the curated weekly panel
- define canonical entities for product, market, and week
- create governed semantic definitions in Aevah

**Key activities**

- ingest and profile source data
- standardize UPC, geography, retailer, and week keys
- create `fact_pos_weekly`
- build `dim_product`, `dim_market`, and `dim_calendar_week`
- define lineage and data quality checks
- identify leakage-sensitive source fields

**Primary deliverables**

- curated weekly fact table
- foundational dimensions
- semantic definitions for launch, promo, incrementality, and cannibalization
- quality-check framework

**Exit criteria**

- core fact table stable at the selected grain
- key joins resolve reliably
- major data quality issues understood or remediated

## Phase 3: Historical measurement and target design

**Suggested duration**

- Weeks 4 to 7

**Primary goals**

- quantify observed demand transfer patterns
- define modeling targets and event logic
- validate competitive-set logic

**Key activities**

- identify launch, promo, distribution, and assortment events
- measure pre/post demand shifts
- define donor and recipient logic
- compare `Base Units` and `Units` as primary targets
- publish historical measurement views

**Primary deliverables**

- event definitions
- historical cannibalization diagnostics
- approved target definitions
- initial competitive-set framework

**Exit criteria**

- business stakeholders recognize the historical measurement patterns as credible
- target definitions are stable enough for training

## Phase 4: Feature engineering and baseline modeling

**Suggested duration**

- Weeks 6 to 10

**Primary goals**

- build reusable feature views
- train and compare baseline models
- establish explainable predictive performance

**Key activities**

- create own-item, competitor, same-brand, and market-context features
- construct reusable feature views in Aevah
- train regression and classification baselines
- evaluate forward-chaining and holdout-market validation
- review leakage risk and feature stability

**Primary deliverables**

- governed feature views
- baseline model candidates
- validation reports
- ranked prediction drivers

**Exit criteria**

- selected baseline beats naive benchmarks
- model behavior is stable across validation slices
- explainability is strong enough for business review

## Phase 5: Validation, explainability, and business packaging

**Suggested duration**

- Weeks 9 to 13

**Primary goals**

- convert model outputs into business-facing intelligence
- make results usable for decision support
- prepare dashboards and agent-ready outputs

**Key activities**

- publish SKU-level and market-level prediction outputs
- publish donor-recipient views
- create scenario-ready output structures
- align outputs to commercial workflows
- prepare dashboard and agent consumption layers

**Primary deliverables**

- cannibalization scorecards
- explainability views
- scenario planning outputs
- dashboard-ready and agent-ready tables

**Exit criteria**

- business users can interpret outputs without heavy analyst translation
- the first pilot workflow is supported end-to-end

## Phase 6: Pilot deployment and monitoring

**Suggested duration**

- Weeks 12 to 16

**Primary goals**

- operationalize the pilot
- establish refresh, monitoring, and feedback loops
- prove business value in live usage

**Key activities**

- activate weekly scoring cadence
- implement drift and quality monitoring
- define model refresh process
- gather business feedback on prediction usefulness
- measure pilot adoption and decision impact

**Primary deliverables**

- live pilot outputs
- monitoring dashboard
- retraining and governance process
- pilot review package

**Exit criteria**

- pilot outputs are being used by the target audience
- monitoring is active and reliable
- business value and next-step scale plan are documented

## Example 12-week compressed roadmap

If the team wants a faster pilot, the roadmap can be compressed like this:

### Weeks 1 to 2

- scope lock
- business definitions
- initial source profiling

### Weeks 3 to 4

- curated weekly fact table
- product, market, and calendar dimensions
- initial semantic layer

### Weeks 5 to 6

- event logic
- historical measurement views
- target definition approval

### Weeks 7 to 8

- feature engineering
- competitive-set logic
- first-pass baseline models

### Weeks 9 to 10

- validation
- explainability outputs
- business review of predictions

### Weeks 11 to 12

- dashboard or agent delivery layer
- weekly scoring workflow
- pilot readout and next-phase recommendation

## Team structure

Recommended minimum team for the pilot:

- executive sponsor
- analytics product owner
- data engineer or platform engineer
- data scientist
- BI or analytics delivery lead
- business stakeholder from category, revenue management, or commercial analytics

## Dependencies

The roadmap depends on:

- access to full historical SPINS data
- product hierarchy and mapping availability
- stable geography and retailer definitions
- agreement on the first use case
- Aevah environment readiness for governed table and semantic-layer delivery

## Key decision gates

The team should pause for explicit decisions at these gates:

1. end of scope definition
2. completion of the curated panel
3. approval of target definitions
4. baseline model selection
5. approval of business-facing outputs
6. pilot go-live decision

## Risks to schedule

The most likely schedule risks are:

- unclear business definition of cannibalization
- delays in product hierarchy or market mapping
- poor quality competitive-set definitions
- hidden leakage in source fields
- model outputs that are analytically sound but hard for the business to trust
- expanding scope before the first pilot is proven

## Recommended first pilot target

If the business has not yet chosen a first use case, the strongest pilot candidate is usually:

- within-brand launch cannibalization in one category

Why:

- it is easier to explain
- it has clear commercial value
- donor and recipient relationships are more intuitive
- success criteria are easier to define than category-wide substitution across many brands

## Success measures for the pilot

The pilot should be judged on three levels:

### Delivery success

- on-time completion of the governed panel and semantic layer
- model outputs delivered on weekly cadence
- working dashboard or agent consumption layer

### Analytical success

- credible predictive performance on future periods
- believable donor-recipient identification
- useful prioritization of high-risk events

### Business success

- adoption by the intended planning audience
- evidence that outputs influence launch, promo, or assortment decisions
- measurable commercial value or avoided cannibalization in the pilot scope

## Recommended next step after pilot

If the pilot succeeds, the next expansion should follow this order:

1. expand to adjacent categories
2. add dollar and margin-oriented outputs
3. improve scenario simulation depth
4. broaden agentic workflows and executive reporting
5. scale into a multi-category cannibalization intelligence program
