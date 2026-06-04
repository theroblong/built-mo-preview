# BUILT Cannibalization UI V2 - Comparison Pool Workbench

This artifact reimagines an additional version of the BUILT cannibalization tool UI that fully uses the newer architecture:

- flexible comparison pools for any SKU, flavor, brand line, competitor brand, or custom basket
- pairwise `focal_upc x comparison_upc x geography x week` scoring
- weekly win counts and win percentages over time
- donor pressure, opposition rate, co-win rate, and related-loss drilldowns
- deterministic metric evidence first, with ML ranking and explanation as support

This does not replace the focused pack-ladder UI. It is a broader analyst and product-owner workbench for exploring all plausible cannibalization and complementarity relationships.

## Product Thesis

The first version asks:

```text
Is this new SKU or pack size cannibalizing its closest same-flavor siblings?
```

This second version asks:

```text
Across any pool of related SKUs, who is winning, who is losing, and is the group growing together or shifting demand internally?
```

The core UX pattern is:

1. define the focal set
2. define the comparison pool
3. scan group health over time
4. drill into pairwise SKU pressure
5. explain whether the pattern is incremental, concentrated, or cannibalizing

## Screen 1: Comparison Pool Builder

### Purpose

Give users a clear, editable way to create the exact SKU universe they want to analyze.

### Layout

```text
+----------------------------------------------------------------------------------+
| Comparison Pool Builder                                                          |
+----------------------------------------------------------------------------------+
| Focal Set                                                                         |
| [ BUILT Brownie Batter 4pk ] [change]                                             |
| Grain:  UPC | Pack ladder | Specific flavor | Flavor family | Brand line | Basket |
+----------------------------------------------------------------------------------+
| Comparison Pool                                                                   |
| ( ) Pack sizes of same flavor only                                                |
| ( ) Same flavor, all brands                                                       |
| ( ) Same family, BUILT only                                                       |
| ( ) Same family, all brands                                                       |
| ( ) All BUILT flavors                                                             |
| ( ) Selected competitor brands: [QUEST] [BAREBELLS] [RXBAR]                      |
| ( ) Custom SKU basket                                                             |
+----------------------------------------------------------------------------------+
| Scope                                                                            |
| Geography: [Total US] [Regions] [Retailers]     Channel: [All] [Grocery] [Club]  |
| Window: [Last 13 weeks] [Last 26 weeks] [Custom] Baseline: [Trailing 4 weeks]    |
+----------------------------------------------------------------------------------+
| [Run Pool]                                                                        |
+----------------------------------------------------------------------------------+
```

### Design rule

The default should still be narrow:

```text
Focal SKU -> same specific flavor pack ladder
```

But every part is editable. A user can widen from one SKU to all BUILT, from same flavor to same family, or from BUILT-only to specific competitor brands without changing screens.

### Required outputs

The builder should produce a request object like:

```text
comparison_request_id
focal_selection_type
focal_selection_values
comparison_selection_type
comparison_selection_values
relationship_distance_filter
geography_scope
channel_scope
week_window
baseline_window
```

## Screen 2: Pool Health Overview

### Purpose

Answer whether the selected pool is broadly healthy or whether growth is concentrated in a few SKUs.

### Layout

```text
+----------------------------------------------------------------------------------+
| Pool Health: Brownie Batter Pack Ladder | Total US | Last 13 Weeks                |
+----------------------------------------------------------------------------------+
| Group Units/TDP     +6.4%     | Group Base Units     +4.9%                        |
| Weekly Win Rate      71%      | Avg Active SKUs       7                           |
| Related Loss Rate    29%      | Pattern               Healthy Mix                 |
+----------------------------------------------------------------------------------+
| Time Trend                                                                         |
| Week      W1 W2 W3 W4 W5 W6 W7 W8 W9 W10 W11 W12 W13                             |
| Win %     86 71 57 29 43 71 86 86 57  43  71  86  71                              |
| Units/TDP +  +  +  -  +  +  +  +  +   flat +   +   +                               |
+----------------------------------------------------------------------------------+
| Interpretation: Group demand improved, but four weeks show concentrated growth.   |
+----------------------------------------------------------------------------------+
```

### Primary metrics

| Metric | Meaning |
|---|---|
| `group_base_units_change_pct` | Underlying demand change for the selected pool |
| `group_units_tdp_change_pct` | Reach-adjusted productivity change |
| `weekly_win_count` | Number of active SKUs that won in each week |
| `weekly_win_pct` | Share of active SKUs that won in each week |
| `related_loss_pct` | Share of comparison SKUs that lost while focal won |
| `win_concentration_ratio` | Share of positive unit gains captured by the focal SKU or top winner |

### Pattern labels

| Label | Rule of thumb |
|---|---|
| Broad Growth | Group demand up and win percentage at or above 70% |
| Healthy Mix | Group demand up and win percentage between 50% and 70% |
| Concentrated Growth | Group demand up but win percentage below 50% |
| Possible Cannibalization | Focal wins while related SKUs lose and group demand is flat or weak |
| Portfolio Decline | Group demand down and win percentage below 50% |
| Distribution-Led Growth | Units up, TDP up materially, productivity flat or down |

## Screen 3: SKU Win Matrix

### Purpose

Show the week-by-week pattern behind the pool summary.

### Layout

```text
SKU group: Brownie Batter pack ladder | Geography: Total US | Baseline: trailing 4 weeks

+----------------------------------------------------------------------------------+
| SKU / Week              | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | Win % | Role    |
|-------------------------|----|----|----|----|----|----|----|----|-------|---------|
| Brownie Batter 1ct      | +  | -  | -  | +  | -  | +  | +  | -  | 50%   | Donor   |
| Brownie Batter 4pk      | +  | +  | +  | +  | +  | +  | +  | +  | 100%  | Focal   |
| Brownie Batter 8pk      | +  | +  | -  | -  | +  | +  | -  | +  | 63%   | Neutral |
| Brownie Batter 12pk     | +  | -  | -  | -  | -  | +  | -  | -  | 25%   | Donor   |
| Group weekly win count  | 4  | 2  | 1  | 2  | 2  | 4  | 2  | 2  |       |         |
+----------------------------------------------------------------------------------+
```

### Cell states

Use compact visual states:

| State | Meaning |
|---|---|
| `+` | SKU beat its selected baseline |
| `-` | SKU missed its selected baseline |
| `0` | SKU was effectively flat |
| `.` | Insufficient evidence or inactive |
| `P` | Promo-confounded week |
| `D` | Distribution-confounded week |

The win matrix should not claim causality. It reveals patterns quickly, then lets the user drill into units, base units, dollars, TDP, ARP, and promotion context.

## Screen 4: Pairwise Pressure Table

### Purpose

Rank the comparison SKUs most likely to be donating demand to the focal item or moving in opposition to it.

### Layout

```text
Focal: Brownie Batter 4pk | Pool: Same flavor pack ladder | Total US

+------------------------------------------------------------------------------------------------+
| Comparison SKU        | Relationship | Opp. Rate | P(Loses | Focal Wins) | Co-Win | Risk | Driver |
|-----------------------|--------------|-----------|----------------------|--------|------|--------|
| Brownie Batter 12pk   | Pack ladder  | 62%       | 74%                  | 18%    | High | Base units down |
| Brownie Batter 1ct    | Pack ladder  | 45%       | 59%                  | 31%    | Med  | Velocity down   |
| Brownie Batter 8pk    | Pack ladder  | 21%       | 28%                  | 64%    | Low  | Wins together   |
+------------------------------------------------------------------------------------------------+
```

### Important metrics

| Metric | Definition |
|---|---|
| `opposition_rate` | Weeks where focal wins and comparison loses, divided by weeks both are active |
| `co_win_rate` | Weeks where both SKUs win, divided by weeks both are active |
| `p_comparison_loses_given_focal_wins` | Conditional loss probability for the comparison SKU |
| `loss_lift_given_focal_win` | Conditional loss probability divided by comparison SKU's normal loss probability |
| `donor_rank` | ML-assisted rank of likely donor candidates |
| `cannibalization_risk_score` | Model-supported risk score, shown as a label rather than false precision |

### Design rule

Use neutral labels in the table until the evidence supports a role:

- `Comparison SKU`
- `Likely donor`
- `Likely co-winner`
- `Neutral`
- `Insufficient evidence`

Do not label every declining SKU as a donor. A SKU can lose because of promotion, reach, seasonality, retailer resets, or category softness.

## Screen 5: All-SKU Comparison Map

### Purpose

Let users compare all SKUs in the selected universe against all other SKUs without manually opening pair after pair.

### Layout

```text
Rows = focal SKUs
Columns = comparison SKUs
Cell = relationship pattern

+----------------------------------------------------------------------------------+
|                    | 1ct Brownie | 4pk Brownie | 12pk Brownie | 4pk Coconut | QUEST |
|--------------------|-------------|-------------|--------------|-------------|-------|
| 1ct Brownie        | --          | Donates?    | Co-wins      | Neutral     | Watch |
| 4pk Brownie        | Pressure    | --          | Pressure     | Neutral     | Low   |
| 12pk Brownie       | Co-wins     | Donates?    | --           | Low         | Low   |
| 4pk Coconut        | Neutral     | Neutral     | Low          | --          | Watch |
+----------------------------------------------------------------------------------+
```

### Recommended cell encodings

| Cell state | Meaning |
|---|---|
| `Pressure` | High opposition rate and weak group growth |
| `Donates?` | Candidate donor, needs drilldown |
| `Co-wins` | High co-win rate, likely complementary or jointly driven |
| `Neutral` | No strong association |
| `Watch` | Mixed evidence or sparse data |
| `Low` | Low substitution evidence |

This view is especially useful for all BUILT SKUs, all pack sizes within a flavor, or selected competitor brand comparisons.

## Screen 6: Geography and Channel Split

### Purpose

Show whether the same relationship behaves differently across regions, retailers, or channels.

### Layout

```text
Pair: Brownie Batter 4pk vs Brownie Batter 12pk

+----------------------------------------------------------------------------------+
| Geography / Channel | Risk | Win % | Opp. Rate | Base Units Chg | TDP Chg | Note   |
|---------------------|------|-------|-----------|----------------|---------|--------|
| Total US            | High | 71%   | 62%       | +4.9%          | +8.2%   | Watch  |
| Grocery             | High | 64%   | 70%       | +1.1%          | +10.4%  | Reach  |
| Club                | Low  | 83%   | 18%       | +9.8%          | +2.3%   | Healthy|
| Northeast           | Med  | 57%   | 45%       | +3.0%          | +4.7%   | Mixed  |
+----------------------------------------------------------------------------------+
```

### Design rule

National rollups should never hide market conflict. If Total US looks healthy but a major channel shows high opposition, the UI should surface that channel as a drilldown prompt.

## Screen 7: Scenario Lens

### Purpose

Turn historical evidence into planning support without pretending the tool has exact future certainty.

### Example questions

- What happens if we expand Brownie Batter 4pk into more retailers?
- Which existing SKUs are most exposed if we add a new 8pk?
- Would Coconut 12pk likely steal from Coconut 1ct or grow the flavor family?
- Which competitor SKUs show the strongest historical pressure against BUILT?

### Layout

```text
+----------------------------------------------------------------------------------+
| Scenario Lens                                                                     |
+----------------------------------------------------------------------------------+
| Proposed change: [Expand distribution]                                             |
| Focal set:       [BUILT Brownie Batter 4pk]                                        |
| Markets:         [Grocery | Northeast + Southeast]                                 |
| Comparison pool: [Same flavor pack ladder + same family BUILT]                     |
+----------------------------------------------------------------------------------+
| Expected pattern                                                                  |
| Incrementality: Medium                                                            |
| Donor exposure: Brownie Batter 12pk, Brownie Batter 1ct                            |
| Confidence: Medium                                                                |
| Reason: Similar historical expansions showed focal wins with related SKU losses.  |
+----------------------------------------------------------------------------------+
```

### Guardrail

Keep scenario language directional:

- `likely exposed`
- `expected pressure`
- `higher-risk comparison pool`
- `historically similar pattern`

Avoid language that implies exact causal certainty.

## Screen 8: Explanation and Provenance Drawer

Every score, label, and recommendation should expose:

- focal selection
- comparison pool definition
- relationship distance filter
- geography and channel scope
- baseline and analysis windows
- active SKU count
- excluded SKU count and reason
- win definition used
- deterministic metrics used
- ML model version, if used
- scoring timestamp

### Example explanation

```text
Brownie Batter 4pk shows high pressure against Brownie Batter 12pk in Grocery.
The 4pk won in 9 of 12 active weeks. The 12pk lost in 7 of those 9 focal-win weeks.
Group Base Units were only slightly up, while TDP rose materially.
That pattern suggests demand may be shifting inside the pack ladder rather than expanding broadly.
```

## Navigation Model

Recommended top-level tabs:

| Tab | Job |
|---|---|
| Overview | Pool health, win %, group demand, major alerts |
| Win Matrix | SKU/week win-loss pattern |
| Pair Pressure | Ranked focal-to-comparison relationships |
| Map | All-SKU relationship matrix |
| Geography | Regional, retailer, and channel splits |
| Scenario | Directional planning from historical analogs |
| Evidence | Metric table, formulas, provenance |

This is more powerful than the first-pass UI, so it should be presented as an advanced workbench or analyst mode. The default business workflow can still launch users into a simpler event card or pack-ladder view.

## Metric Hierarchy

The UI should keep the metric stack disciplined.

### Primary business metrics

- `Base Units`
- `Units`
- `Base Dollars`
- `Dollars`
- `TDP`
- `Units/TDP`
- `ARP`

### Pattern metrics

- `sku_week_win_flag`
- `weekly_win_count`
- `weekly_win_pct`
- `related_loss_count`
- `related_loss_pct`
- `win_concentration_ratio`
- `focal_share_of_group_gain`

### Pairwise association metrics

- `co_win_rate`
- `opposition_rate`
- `p_comparison_loses_given_focal_wins`
- `loss_lift_given_focal_win`
- `relationship_distance`
- `comparison_type`

### Model outputs

- `cannibalization_risk_label`
- `donor_rank`
- `confidence_label`
- `materiality_flag`
- `top_explanation_drivers`

## MVP Version of UI V2

The smallest useful build is:

1. Comparison Pool Builder
2. Pool Health Overview
3. SKU Win Matrix
4. Pairwise Pressure Table
5. Explanation and Provenance Drawer

That MVP would already support:

- all pack sizes for any selected flavor
- all BUILT SKUs by brand line or flavor family
- selected competitor brand comparisons
- win counts and win percentages over time
- donor ranking without hard-coding donor assumptions

## Why This Version Is Additive

The original polished UI remains valuable for guided launch and assortment decisions. This V2 workbench is for deeper exploration.

| First-pass UI | V2 comparison pool workbench |
|---|---|
| Guided workflow | Open-ended exploration |
| New SKU / pack focus | Any focal set against any comparison set |
| Same-flavor pack ladder default | Full relationship taxonomy |
| Geography heatmap | Geography plus pairwise pressure |
| Pre/post diagnostics | Weekly win/loss sequences |
| Business recommendation | Analyst-grade evidence and scenario lens |

Together, the two versions create a strong product shape:

- simple enough for executives and channel teams
- flexible enough for analysts and product owners
- grounded enough for data science and governance teams
