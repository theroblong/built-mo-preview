# Aevah SPINS Data Processing and Value-Added Workflow Overview

This document explains, at a high level, what Aevah will do on the client's behalf when processing the approximately 51GB, 95 million row SPINS weekly POS data feed.

The purpose is to make the work visible. The client is not simply handing over a large file and receiving a dashboard. Aevah is turning a raw commercial data feed into a governed, reusable, explainable intelligence asset for assortment, cannibalization, pricing, promotion, and launch planning.

## Executive Summary

Aevah will accept the client's recurring SPINS data feed, validate it, standardize it, enrich it, structure it for analytics, generate modeling-ready features, score cannibalization and demand-transfer patterns, and publish governed outputs for dashboards and AI-assisted business workflows.

The platform is designed so the client can continue sending updated SPINS files going forward. Each new feed can be processed through the same repeatable pipeline, which means the work becomes operational rather than one-time analysis.

At a high level, Aevah will:

- receive and register the raw SPINS files
- verify file completeness and schema consistency
- load the data into a scalable analytical environment
- standardize product, market, geography, week, price, promo, and distribution fields
- enrich products with flavor, pack size, brand line, category, and competitive metadata
- build curated tables at the `UPC x Geography x Week` grain
- generate historical demand, distribution, velocity, price, and promotion signals
- create flexible focal-item versus comparison-item pairings
- measure historical cannibalization and incrementality patterns
- train and score machine learning models where appropriate
- publish explainable outputs for business users, dashboards, and Aevah agents
- monitor incoming feeds, model freshness, data quality, and scoring stability over time

## What the Client Sends

The client provides the SPINS weekly POS feed and supporting reference files. The expected core feed is large, approximately:

```text
51GB
95 million rows
UPC x Geography x Week grain
```

The feed includes measures such as:

- units and dollars
- base units and base dollars
- incremental units and incremental dollars
- price and average retail price
- promotion activity
- TDP, ACV, and distribution measures
- geography and retailer-market fields
- product descriptions, UPCs, brands, pack counts, and flavor fields

Supporting files may include product hierarchy, item catalog, flavor mappings, pack size mappings, category attributes, lifecycle dates, launch calendars, and competitor definitions.

## What Aevah Does With the Feed

### 1. Secure feed intake and registration

Aevah accepts the delivered files into a controlled intake process. Each file is registered with source, date, version, row count, and processing status.

Value added:

- creates a repeatable intake process
- avoids one-off analyst file handling
- preserves source lineage
- makes each feed auditable

### 2. File validation and quality checks

Before the feed is used downstream, Aevah checks whether it is complete and structurally usable.

Examples of checks:

- expected columns are present
- row counts are within expected ranges
- week-ending dates are valid
- numeric measures can be parsed correctly
- UPC and geography fields are populated
- duplicate records are identified
- impossible values are flagged, such as negative units where not allowed

Value added:

- catches file issues early
- reduces business risk from bad source data
- gives the client clear feedback when a feed changes or breaks

### 3. Scalable load into an analytical engine

The raw 95 million rows are too large for spreadsheet-style analysis. Aevah loads the feed into a scalable analytical layer designed for large weekly POS data.

Value added:

- makes the large feed queryable
- supports repeatable transformation
- prevents analysts from manually manipulating massive files
- prepares the data for dashboards, modeling, and agent workflows

### 4. Source-to-target mapping

Aevah maps raw SPINS fields into governed business fields.

Examples:

- raw `UPC` becomes the canonical product key
- raw geography text becomes standardized market, retailer, channel, and banner fields
- raw week fields become standard calendar-week entities
- raw measures are assigned clear analytical roles, such as demand, baseline demand, promotion, price, and distribution

Value added:

- creates one consistent interpretation of the feed
- reduces ambiguity across teams
- makes future data refreshes easier to process

### 5. Product enrichment

Aevah enriches the raw product records so the system understands what items are comparable.

Examples of enrichment:

- normalized specific flavor
- flavor family
- pack count
- size and unit of measure
- brand line
- product type
- category and subcategory
- protein or functional positioning
- competitor brand tier
- direct substitute flags

Value added:

- turns product descriptions into analytical attributes
- enables pack-size, flavor, and competitor comparisons
- makes the tool useful for real category-management questions

### 6. Geography and channel normalization

SPINS geography fields often contain retailer panels, regions, banners, sub-banners, co-op panels, and national rollups in text form. Aevah parses and standardizes those fields.

Examples:

- Total US
- region
- retailer
- parent group
- banner
- sub-banner
- channel
- market type

Value added:

- lets the client analyze results by retailer, channel, region, or national view
- prevents inconsistent geography labels from fragmenting the analysis
- supports cleaner dashboard filtering

### 7. Curated weekly fact table creation

Aevah creates a governed weekly POS table at the core analytical grain:

```text
UPC x Geography x Week
```

This curated table becomes the foundation for all downstream work.

Value added:

- creates a stable base layer
- supports repeatable reporting and modeling
- separates raw file complexity from business-facing outputs

### 8. Analytical feature generation

Aevah calculates reusable signals from the raw measures.

Examples:

- week-over-week changes
- pre/post launch windows
- velocity measures
- distribution-normalized productivity
- price-per-unit and price-per-pack relationships
- promotion intensity
- baseline versus promoted demand
- ACV and TDP movement
- item maturity and weeks selling
- seasonality and rolling trend features

Value added:

- converts raw rows into decision-ready signals
- makes the data useful for prediction, not just reporting
- reduces repeated manual analytics work

### 9. Flexible comparison pool creation

Aevah creates a flexible comparison structure that allows the client to compare:

- one pack size against other pack sizes of the same flavor
- one specific flavor against another specific flavor
- one BUILT item against another BUILT item
- one BUILT item against competitor items
- one flavor family against another
- one brand or selected SKU basket against another

The key design is a neutral pairwise layer:

```text
focal item x comparison item x geography x week
```

Value added:

- avoids locking the client into one predefined cannibalization target list
- supports user-directed exploration
- allows the tool to start with likely targets while still remaining flexible

### 10. Historical cannibalization measurement

Aevah measures what has happened historically when items launched, expanded distribution, promoted, changed price, or overlapped with related items.

Examples of outputs:

- which items gained demand
- which items lost demand
- whether losses were within brand or competitive
- whether volume growth was incremental or transferred
- which geographies showed the strongest substitution

Value added:

- gives the client factual historical diagnostics
- grounds future modeling in observed behavior
- helps stakeholders understand category dynamics before relying on predictions

### 11. Machine learning feature tables and scoring

Where useful, Aevah turns the curated and enriched data into modeling-ready tables.

Modeling tasks may include:

- cannibalization risk scoring
- likely donor item ranking
- demand-transfer intensity
- launch cannibalization risk
- promotion-driven substitution
- distribution-led versus demand-led growth
- significant event detection

Value added:

- helps move from descriptive reporting to forward-looking decision support
- ranks the most likely donor and recipient relationships
- gives business users a confidence-weighted view rather than raw noise

### 12. Explainability and business interpretation

Aevah will not only return a score. It will attach reasons, drivers, and supporting metrics.

Examples:

- donor base units declined while focal base units rose
- focal TDP increased faster than velocity
- price-per-unit changed between pack sizes
- promo activity may be confounding the signal
- a result is strong in one channel but weak in another

Value added:

- helps users trust the output
- makes results usable by commercial teams
- supports executive explanations and AI-agent answers

### 13. Dashboard, agent, and workflow-ready outputs

The final outputs are shaped for consumption, not left as technical tables.

Examples:

- SKU-level cannibalization scorecards
- geography heatmaps
- pack-size ladder comparisons
- flavor-to-flavor comparison views
- competitor comparison views
- launch and promotion risk views
- agent-ready tables for natural-language questions

Value added:

- turns the processed feed into a usable business product
- reduces analyst translation work
- supports repeatable client workflows

### 14. Ongoing feed refresh and monitoring

Once the initial pipeline is established, new SPINS feeds can run through the same process.

Ongoing processing can include:

- ingesting new weekly or periodic files
- validating feed structure
- refreshing curated tables
- recalculating features
- rescoring affected items and markets
- updating dashboards
- logging data quality and processing status
- flagging unusual feed or demand changes

Value added:

- makes the system sustainable
- keeps insights current
- gives the client confidence that the platform can operate beyond the initial project

## How This Feels to the Client

From the client's perspective, the operating model should be simple:

```text
1. Client sends SPINS feed and reference files.
2. Aevah validates and loads the data.
3. Aevah enriches, standardizes, and structures the feed.
4. Aevah builds reusable analytics and modeling layers.
5. Aevah publishes dashboards, scores, and agent-ready answers.
6. Future feeds refresh through the same governed process.
```

The client does not need to manually prepare the 51GB file for analysis each time. Aevah absorbs the complexity and turns the feed into a maintained intelligence layer.

## What Work Is Being Done on the Client's Behalf

The major value-added work includes:

- large-file intake and processing
- schema validation and feed quality control
- raw-to-curated data modeling
- product hierarchy and UPC standardization
- geography, channel, retailer, and banner normalization
- flavor and pack-size enrichment
- competitive-set construction
- baseline, promo, price, distribution, and velocity signal engineering
- pre/post event measurement
- flexible item-to-item comparison generation
- cannibalization label creation
- machine learning training and scoring
- donor-recipient ranking
- explainability generation
- dashboard-ready output creation
- agent-ready semantic output creation
- refresh monitoring and processing governance

## Why Aevah Is Valuable Here

The client already has the SPINS data, but the raw feed is not yet a decision system.

Aevah adds value by making the feed:

- governed
- repeatable
- scalable
- enriched
- comparable across products and markets
- ready for machine learning
- explainable to business users
- usable in dashboards and AI-agent workflows
- maintainable as new feeds arrive

The end product is not just a processed file. It is an operating layer for commercial intelligence.

## Recommended Client Message

Aevah can easily accept the SPINS feed as a recurring data source, process the full 51GB / 95 million row dataset through a governed pipeline, and convert it into curated tables, reusable features, flexible comparison pools, cannibalization scores, and business-facing outputs.

The work behind the scenes includes data validation, standardization, enrichment, feature engineering, comparison logic, ML scoring, explainability, and ongoing refresh monitoring. That means the client gets more than a dashboard: they get a repeatable intelligence system that keeps improving as new SPINS data arrives.
