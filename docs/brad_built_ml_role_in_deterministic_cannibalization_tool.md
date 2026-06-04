# BUILT ML Role in a Deterministic Cannibalization Tool

This note defines how machine learning should fit into a polished BUILT cannibalization experience without turning the product into an opaque or experimental workflow.

The guiding principle is:

- deterministic user experience first
- ML as a scoring and prioritization layer
- transparent business logic around the model
- visible supporting evidence for every recommendation
- provenance, lineage, and explainability around every surfaced insight

## Core idea

The final BUILT tool should not ask the user to trust a raw model score by itself.

Instead, the user experience should combine:

1. deterministic business rules
2. visible demand and distribution metrics
3. ML-based probability or risk scoring
4. clear explanation of the drivers behind the score
5. explicit provenance for the data windows, comparison set, and model version used

That means ML should support the workflow, not own the entire decision.

At the same time, the product should not artificially downgrade itself into a simplistic rules engine if stronger ML can provide materially better predictions. The right goal is:

- sophisticated modeling behind the scenes
- disciplined explanation on the front end
- statistically stronger prediction with transparent lineage

## What should remain deterministic

The following parts of the experience should remain rule-based and directly auditable:

- product matching logic
- same-specific-flavor grouping
- donor set definition rules
- geography rollups
- pack-size comparisons
- pre/post launch windows
- displayed raw metrics such as `Base Units`, `Units`, `TDP`, `Units/TDP`, `ARP`
- business thresholds used for red/yellow/green labels when desired

These are the parts users should be able to understand and verify without needing model knowledge.

## Where ML adds the most value

ML is most valuable in the following places:

### 1. Donor SKU ranking

The model can rank which existing items are the most likely demand donors to a new SKU.

This is useful because the donor set is rarely obvious when:

- multiple similar SKUs coexist
- the same launch behaves differently by geography
- substitution spans more than one pack size or one flavor family

The deterministic layer can define the candidate pool. The ML layer can rank the candidates.

### 2. Cannibalization likelihood scoring

The model can estimate the probability that a launch or new pack size is:

- incremental
- neutral
- mildly cannibalizing
- strongly cannibalizing

This is where ML helps synthesize multiple signals at once:

- `Base Units`
- `Units`
- `TDP`
- price and promo context
- launch timing
- specific flavor overlap
- same-family pack-size overlap
- geography behavior

### 3. Incrementality estimation

The model can estimate how much of the new item’s demand looks:

- newly created
- shifted from same-brand donor items
- shifted from competitors

This is especially valuable when the user wants a tighter answer than a simple before/after table can provide.

### 4. Recommendation prioritization

The model can help prioritize which assortment actions are most worth attention, such as:

- add
- keep
- reduce
- replace
- monitor

This is useful because the business often needs triage more than it needs raw scores.

### 5. Significant event detection

The model can surface statistically meaningful events such as:

- likely launch success or failure
- meaningful same-brand demand transfer
- geography-specific cannibalization spikes
- unexpected donor SKU declines
- distribution-driven versus demand-driven change patterns

This is valuable because users often want the system to call attention to what matters instead of manually inspecting every SKU and geography.

## What ML should not do in the final UX

To keep the product trustworthy, the final user experience should avoid:

- unexplained black-box recommendations
- model outputs with no visible supporting evidence
- unstable labels that change dramatically on weak evidence
- dozens of model-derived metrics that users cannot interpret
- replacing core business measures with latent or abstract embeddings in the UI

ML should be used to narrow, rank, and summarize, not to overwhelm.

The goal is not to hide model sophistication. The goal is to avoid exposing users to model internals without interpretation.

## Recommended product pattern

The best pattern is:

### Layer 1. Deterministic evidence

Show:

- focal SKU
- likely donor SKU set
- geography
- specific flavor
- pack size
- `Base Units`
- `Units`
- `TDP`
- `Units/TDP`
- launch timing

This gives the user direct evidence.

### Layer 2. ML summary

Then show a small number of ML outputs:

- `cannibalization_risk_score`
- `incrementality_estimate`
- `top_likely_donor_skus`
- `assortment_action_priority`
- `significant_event_callout`

### Layer 3. Rule-based explanation

Then show a plain-language explanation based on both model features and business rules, for example:

> Mint Brownie 4pk appears mildly cannibalizing in Texas because Base Units rose only slightly while TDP expanded materially and the 1ct Mint Brownie item declined over the same period.

This style keeps the experience intelligible.

### Layer 4. Provenance and lineage panel

Every important recommendation should expose a compact lineage panel such as:

- source dataset used
- geography and product scope
- time window used for comparison
- donor candidate pool definition
- model version and score date
- confidence or evidence strength

This lets advanced users verify where the output came from without overwhelming casual users.

## Recommended user-facing ML outputs

The front-end should stay narrow. Good user-facing ML outputs would be:

- cannibalization status: `Incremental`, `Neutral`, `Watch`, `Cannibalizing`
- confidence level: `High`, `Medium`, `Low`
- top 1-3 likely donor SKUs
- incrementality percentage band
- recommended action: `Keep`, `Expand`, `Monitor`, `Reduce`, `Replace`
- significant event callouts such as `Demand Shift Detected`, `Likely Donor Decline`, `Distribution-Led Gain`, `Launch Underperforming in Geography`
- optional weekly win/loss summaries such as `5 of 7 SKUs won`, `71% group win rate`, or `focal SKU won while 3 related SKUs lost`

That is usually enough.

For the optional win-count extension, see [brad_weekly_win_count_bonus_path.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_weekly_win_count_bonus_path.md). That layer can provide approachable probabilities, ratios, and sequence-ready features while preserving the deterministic front-end pattern.

## Recommended analyst-facing ML outputs

The analyst or back-end layer can be richer and include:

- numeric cannibalization probability
- donor attribution weights
- SHAP or feature contribution summaries
- geography-specific feature interactions
- scenario simulation outputs
- uncertainty intervals
- statistical significance checks or event-threshold diagnostics
- training data lineage and feature snapshot references

These can power the UX without being dumped directly into the user-facing layer.

## Reliability guardrails

To keep the tool deterministic and trustworthy, the ML layer should be governed by guardrails such as:

- only score when minimum evidence thresholds are met
- suppress low-confidence scores
- require visible donor candidates before surfacing cannibalization claims
- prevent contradictory labels when underlying metrics are weak or sparse
- use stable thresholds for converting probabilities into business labels
- log the key drivers behind every surfaced recommendation
- retain the exact feature snapshot or feature summary used for each surfaced recommendation
- attach model version, scoring timestamp, and comparison-window metadata to every output
- require event callouts to meet defined statistical or practical significance thresholds

## Provenance and explainability expectations

If BUILT wants black-box power with enterprise trust, every surfaced insight should answer these questions:

1. What was scored?
2. Compared against what?
3. Over what time period?
4. Using which input data sources?
5. Which model version produced the result?
6. What were the strongest drivers?
7. How confident is the system?
8. Did the event clear a significance threshold or just a heuristic threshold?

That does not mean exposing raw math on every screen. It means the product should always be able to reveal this information on demand.

## Significant event callouts

The event layer is especially important for a polished user experience.

The tool should proactively call out events such as:

- `Significant Demand Transfer Detected`
- `Likely Cannibalization Concentrated in Texas`
- `Launch Growth Driven Mostly by Distribution Expansion`
- `Same-Flavor 1ct Donor Decline Exceeds Expected Range`
- `Pack-Size Overlap Risk Elevated in Grocery`

Each event callout should include:

- event label
- affected SKU or SKU set
- geography or channel scope
- evidence summary
- significance or confidence level
- drill-down link to the underlying metrics and donor set

This is where the black-box capability becomes genuinely useful to the business: not just better scores, but better attention direction.

## Best hybrid decision flow

The strongest flow for BUILT is:

1. deterministic rules define the candidate comparison set
2. deterministic metrics show what changed
3. ML estimates likelihood, ranking, and event significance
4. deterministic explanation logic translates the result into business language
5. provenance panel shows where the answer came from
6. user sees recommended assortment action with supporting evidence

That is the right balance between rigor and usability.

## Example

### User sees

- Focal item: `BUILT Mint Brownie 4pk`
- Geography: `Texas`
- Specific flavor: `Mint Brownie`
- `Base Units`: `+4%`
- `Units`: `+11%`
- `TDP`: `+18%`
- `Units/TDP`: `-6%`
- Top donor: `BUILT Mint Brownie 1ct`
- Cannibalization status: `Watch`
- Confidence: `Medium`
- Recommended action: `Monitor before wider expansion`
- Event callout: `Distribution-Led Gain`
- Provenance: `Texas | same specific flavor donor pool | last 13 weeks vs prior 13 weeks | model v1.8`

### What happened behind the scenes

- rules identified same-flavor same-family donor candidates
- model ranked the 1ct pack as the most likely donor
- score suggested moderate risk rather than strong cannibalization
- explanation logic converted the feature pattern into a concise narrative
- provenance metadata preserved the scoring window, donor logic, and model version

## Bottom line

For BUILT, ML should make the tool smarter, not murkier.

The most reliable product pattern is:

- deterministic evidence
- ML prioritization, scoring, and event detection
- deterministic explanation
- visible provenance and lineage

That gives BUILT a tool that feels polished and trustworthy while still benefiting from machine learning where it actually helps.
