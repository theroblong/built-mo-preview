# BUILT Cannibalization Storyboard

This storyboard shows how a BUILT user could experience the cannibalization tool from the moment they open it through the point of making an assortment decision.

The storyboard assumes the product is:

- polished and selective
- powered by strong deterministic evidence
- supported by ML scoring and event detection
- transparent about provenance and explanation

## Storyboard Goal

Help a BUILT user answer:

- is a new item or new pack size incremental or cannibalizing
- where is the effect happening
- which SKUs are likely losing demand
- what should we do about the assortment by channel and geography

## Screen 1. Priority Event Landing Page

### User sees

A clean landing page with only the highest-value callouts:

- `Significant Demand Transfer Detected`
- `Launch Underperforming in Texas`
- `Same-Flavor Pack Overlap Risk Elevated in Grocery`
- `Distribution-Led Gain Detected`

Each card includes:

- focal SKU
- geography or channel
- event label
- confidence level
- recommended next step

### Why it matters

The user does not need to hunt through every SKU. The tool points them to the most meaningful events first.

### Data and logic behind it

- deterministic evidence metrics
- ML event detection
- significance thresholding
- provenance metadata ready for drill-down

## Screen 2. New SKU / New Pack Summary View

### User sees

The user opens a focal item such as `BUILT Mint Brownie 4pk`.

The summary panel shows:

- cannibalization status: `Watch`
- confidence: `Medium`
- likely donor SKUs: `Mint Brownie 1ct`, `Mint Brownie 12pk`
- recommended action: `Monitor before wider expansion`

The main metric tiles show:

- `Base Units`
- `Units`
- `TDP`
- `Units/TDP`
- `ARP`
- `First Week Selling`

### Why it matters

This gives a fast answer without forcing the user to interpret raw model output.

### Data and logic behind it

- deterministic donor candidate logic
- ML donor ranking
- ML cannibalization scoring
- rule-based translation into a business label

## Screen 3. Geography Comparison View

### User sees

A table or heatmap showing the focal item by geography:

- total US
- key regions
- priority markets

For each geography, the user sees:

- `Base Units` change
- `Units` change
- `TDP` change
- `Units/TDP` change
- status label

### Why it matters

It shows where the same launch is helping, mixed, or destructive. BUILT can immediately see that cannibalization is not uniform.

### Data and logic behind it

- geography-specific comparisons
- pre/post launch windows
- deterministic metric deltas
- ML score adjusted for local evidence

## Screen 4. Same Specific Flavor Pack Ladder

### User sees

The user drills into `Mint Brownie` and sees all BUILT pack variants of that exact specific flavor.

Displayed for each SKU:

- pack count
- `Base Units`
- `Units`
- `TDP`
- `Units/TDP`
- donor / recipient role

An insight banner summarizes:

- whether the new pack is incremental
- whether it appears to be taking demand mostly from 1ct, 12pk, or both

### Why it matters

This is where assortment and pack-size decisions become concrete.

### Data and logic behind it

- exact specific flavor grouping
- same-family pack comparison
- donor ranking
- pack-mix interpretation logic

## Screen 5. Pre/Post Launch Diagnostic

### User sees

A simple before-and-after diagnostic:

- pre-launch baseline
- launch window
- stabilized post-launch window

Metrics shown:

- focal SKU `Base Units`
- focal SKU `Units`
- focal SKU `TDP`
- focal SKU `Units/TDP`
- donor SKU declines

### Why it matters

This screen gives the user a concrete explanation for why the system labeled the launch the way it did.

### Data and logic behind it

- deterministic period comparisons
- difference and percent-change formulas
- supporting donor evidence

## Screen 6. Explanation Drawer

### User sees

An expandable explanation panel with plain-language reasoning such as:

> Mint Brownie 4pk is flagged as Watch in Texas because observed units rose, but most of the gain appears tied to distribution expansion while productivity weakened and the 1ct Mint Brownie donor item declined over the same period.

The panel also lists the top drivers:

- `TDP` up materially
- `Units/TDP` down
- donor SKU decline detected
- launch still in early ramp

### Why it matters

This is where the product becomes explainable instead of mysterious.

### Data and logic behind it

- rule-based explanation templates
- top model drivers
- deterministic feature summaries

## Screen 7. Provenance and Lineage Drawer

### User sees

A compact metadata panel:

- source data used
- scoring window
- geography scope
- donor pool definition
- model version
- score timestamp
- confidence / significance level

### Why it matters

This gives advanced users confidence that the output is audit-friendly and grounded in traceable evidence.

### Data and logic behind it

- scoring metadata
- feature snapshot or summary
- model governance metadata

## Screen 8. Assortment Recommendation View

### User sees

A final recommendation framed in business language:

- `Keep core`
- `Expand selectively`
- `Monitor before expanding`
- `Reduce overlap`
- `Replace low-productivity pack`

The recommendation is broken out by channel and geography where possible.

### Why it matters

The user does not just want diagnostics. They want a practical assortment decision.

### Data and logic behind it

- deterministic thresholds
- ML prioritization
- geography and channel context
- same-specific-flavor pack overlap logic

## Storyboard Summary

The full user journey is:

1. start with significant event callouts
2. inspect the focal SKU summary
3. compare by geography
4. drill into exact flavor and pack-size overlap
5. validate with pre/post launch diagnostics
6. read explanation and provenance
7. take action on assortment

## Why this works for BUILT

This storyboard keeps the experience:

- narrow
- high-confidence
- explainable
- operationally useful

It gives users the sophistication of ML and event detection without losing trust, lineage, or business clarity.
