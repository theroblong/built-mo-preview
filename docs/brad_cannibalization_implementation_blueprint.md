# Brad's Cannibalization Implementation Blueprint

This document translates the cannibalization strategy into an execution-ready blueprint. It is designed to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`

The intended use is to give the project a practical structure with phases, owners, inputs, outputs, and success criteria.

## Objective

Build a governed product cannibalization prediction capability that can:

- estimate which SKUs are likely to lose demand
- identify likely donor and recipient relationships
- quantify unit, dollar, and eventually margin impact
- support launch, assortment, pricing, and promotion decisions

## Scope

Initial scope:

- weekly POS panel modeling
- SKU-level prediction
- geography-level and retailer-level analysis
- within-brand and close-substitute cannibalization
- explainable outputs for business users and agents

Out of scope for the first release:

- full enterprise-wide optimization
- fully automated decisioning
- highly customized causal modeling for every category at once

## Core modeling grain

Primary grain:

- `UPC x Geography x Week`

Optional reporting rollups:

- brand
- segment / subcategory
- retailer / channel
- geography

## Workstreams

The work should be run across five coordinated workstreams:

1. data foundation
2. measurement and target design
3. feature engineering and modeling
4. business delivery and explainability
5. operationalization and monitoring

## Phase plan

### Phase 1: Data foundation

**Goal**

Create the trusted analytical base for all downstream modeling and reporting.

**Primary owner**

- data engineering / platform lead

**Supporting owners**

- analytics lead
- business stakeholder for product hierarchy validation

**Inputs**

- raw SPINS POS extracts
- product master or hierarchy tables
- geography / retailer mappings
- calendar table
- price, promo, and distribution fields

**Key tasks**

- define canonical keys for UPC, geography, retailer, and week
- standardize product hierarchy and competitive-set metadata
- document semantic definitions for launch, promo, incrementality, and cannibalization
- create lineage from raw fields to curated analytical tables
- flag fields with leakage risk

**Outputs**

- curated `UPC x Geography x Week` fact table
- standardized dimension tables
- governed business definitions
- data quality checks and lineage documentation

**Success criteria**

- key joins are stable and reproducible
- product and geography entities are resolved consistently
- no unresolved ambiguity in core business definitions
- curated panel supports modeling without ad hoc manual fixes

### Phase 2: Measurement and target design

**Goal**

Measure historical substitution behavior and define training targets that reflect real business questions.

**Primary owner**

- data science / advanced analytics lead

**Supporting owners**

- commercial analytics
- category or brand stakeholders

**Inputs**

- curated weekly panel
- launch timing
- promo and distribution history
- product hierarchy and competitive-set logic

**Key tasks**

- quantify historical demand shifts after launches, promos, and distribution changes
- define donor and recipient relationships
- evaluate `Units` versus `Base Units` as core targets
- define candidate regression and classification labels
- separate observed demand effects from baseline demand effects

**Outputs**

- historical cannibalization measurement views
- final target definitions
- event definitions for launch, promo, and distribution shifts
- target quality assessment

**Success criteria**

- target definitions are understandable and stable
- business stakeholders agree the labels reflect real substitution behavior
- historical views produce believable patterns by SKU and market

### Phase 3: Feature engineering and modeling

**Goal**

Build robust, explainable predictive models for cannibalization.

**Primary owner**

- data science lead

**Supporting owners**

- analytics engineering
- platform / ML operations

**Inputs**

- governed feature-ready panel
- historical target labels
- competitive-set definitions

**Key tasks**

- create reusable feature views for own-item, competitor, same-brand, and market context features
- build baseline models using interpretable approaches
- compare regression and classification formulations
- validate across future periods and holdout markets
- evaluate stability across brands and product families

**Outputs**

- reusable model feature tables
- baseline model artifacts
- validation results
- ranked driver outputs by prediction

**Success criteria**

- predictions outperform naive baselines
- model behavior is stable across time and geographies
- drivers are explainable in commercial terms
- no major leakage issues are found in validation

### Phase 4: Business delivery and explainability

**Goal**

Turn model outputs into business-ready intelligence that supports decision-making.

**Primary owner**

- analytics product owner

**Supporting owners**

- data science
- BI / dashboard lead
- commercial stakeholders

**Inputs**

- model outputs
- explainability outputs
- scenario assumptions

**Key tasks**

- publish predicted donor / recipient views
- expose unit and dollar cannibalization outputs
- create scenario-ready views for launch, pricing, and promo planning
- package outputs for dashboards and agent queries
- define user-facing interpretation guidance

**Outputs**

- cannibalization scorecards
- market and SKU-level dashboards
- scenario planning outputs
- agent-ready tables or APIs

**Success criteria**

- business users can answer planning questions without analyst rework
- stakeholders can understand the "why" behind model outputs
- outputs map clearly to assortment, launch, or promo decisions

### Phase 5: Operationalization and monitoring

**Goal**

Keep the system governed, trustworthy, and useful over time.

**Primary owner**

- platform / ML operations

**Supporting owners**

- data science
- analytics product owner

**Inputs**

- deployed features
- production predictions
- monitoring logs

**Key tasks**

- define retraining cadence
- monitor prediction drift and feature drift
- monitor cold-start behavior for new SKUs
- version target definitions and feature logic
- maintain auditability and lineage

**Outputs**

- monitoring dashboards
- retraining schedule
- model and feature version history
- incident and exception handling process

**Success criteria**

- drift is detected early
- model refreshes are controlled and traceable
- new SKU behavior is monitored explicitly
- business trust is maintained after deployment

## Roles and ownership

Suggested ownership model:

- executive sponsor: commercial or category leadership
- product owner: analytics or intelligence lead
- data foundation owner: data engineering / platform
- modeling owner: data science lead
- delivery owner: BI / analytics product
- governance owner: platform or enterprise data lead

## Key inputs required before execution

Before the build starts, the team should confirm:

- full weekly SPINS extract availability
- product hierarchy and category mapping availability
- access to promo, price, and distribution history
- agreement on the business definition of cannibalization
- agreement on the initial category or brand scope
- success metrics for the first deployment

## Recommended first-release success metrics

First-release success should be measured across three dimensions:

### Technical success

- stable governed panel
- reproducible feature generation
- predictive lift versus baseline models
- acceptable out-of-time performance

### Analytical success

- believable donor-recipient relationships
- consistent performance across major markets
- useful prioritization of high-risk cannibalization events

### Business success

- improved launch or promo planning decisions
- reduced portfolio self-cannibalization
- clear adoption by business users
- measurable commercial value in a pilot scope

## Delivery milestones

Recommended milestone sequence:

1. data model and semantic definitions approved
2. curated weekly panel delivered
3. historical cannibalization measurement views published
4. target definitions finalized
5. baseline model validation completed
6. explainability outputs published
7. dashboard and agent-ready outputs delivered
8. monitoring and refresh process activated

## First implementation recommendation

For the first deployment, keep scope narrow enough to learn quickly:

- one category or subcategory
- one business question, such as launch cannibalization or promo cannibalization
- one initial output set for planning decisions

That keeps the work credible, measurable, and easier to operationalize before expanding across the broader portfolio.
