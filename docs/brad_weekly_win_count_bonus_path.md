# Brad's Weekly Win Count Bonus Path

This artifact captures a bonus path for the cannibalization tool: tracking simple weekly win counts, percentages, probabilities, and ratios alongside the core units, dollars, and productivity measures.

The idea is to make complementary product health easier to visualize. The business objective is not just to identify cannibalization. The larger objective is to help complementary products sell well together. If seven SKUs belong together in a store, we want to know whether the group is broadly improving or whether one item is growing at the expense of the others.

## Core Idea

Keep `units`, `dollars`, `base_units`, `base_dollars`, and units/dollars per store per week as the economic truth.

Add a simpler boolean layer:

```text
Did this SKU win this week? TRUE / FALSE
```

Then summarize across a related SKU group:

```text
weekly_win_count = count of SKUs that won
weekly_win_pct   = weekly_win_count / active_sku_count
```

This gives users a fast read on whether growth is broad-based or concentrated.

## Why This Helps

Traditional cannibalization views can become metric-heavy. They show units, dollars, TDP, price, promotion, distribution, velocity, and pre/post changes. Those measures matter, but they can be difficult for a business user to scan over many weeks.

Win counts create a simpler visual layer:

- 7 of 7 SKUs won: broad portfolio health
- 5 of 7 SKUs won: mostly healthy
- 2 of 7 SKUs won: growth is concentrated
- 1 of 7 SKUs won while total group sales are flat: possible cannibalization
- 0 of 7 SKUs won: portfolio decline

The win layer does not replace actual units or dollars. It helps users see patterns more quickly, then drill into the underlying measures.

## Example

```text
SKU group: Brownie Batter pack ladder + close complementary items
Market: Total US
Window: weekly
Baseline: trailing 4-week average
```

| Week | Group Units / Store | Group Dollars / Store | Win Count | Win % | Pattern |
|---|---:|---:|---:|---:|---|
| W1 | 14.2 | 36.50 | 6 / 7 | 86% | Broad Growth |
| W2 | 15.1 | 38.20 | 2 / 7 | 29% | Concentrated Growth |
| W3 | 15.4 | 39.10 | 1 / 7 | 14% | Possible Cannibalization |
| W4 | 13.8 | 34.90 | 0 / 7 | 0% | Portfolio Decline |

The important signal is not only whether the total group grew. It is whether the group grew together.

## Candidate Win Definitions

A win should be configurable because different business questions need different baselines.

### Simple demand win

```text
units_win = current_units_per_store > baseline_units_per_store
```

Useful for quick sales momentum views.

### Base demand win

```text
base_units_win = current_base_units_per_store > baseline_base_units_per_store
```

Useful when the user wants to reduce promotion noise.

### Dollar win

```text
dollars_win = current_dollars_per_store > baseline_dollars_per_store
```

Useful for commercial value, especially if price or pack mix changes.

### Productivity win

```text
velocity_win = current_units_per_tdp > baseline_units_per_tdp
```

Useful when distribution changes could make raw units misleading.

### Quality win

```text
quality_win =
  base_units_win
  AND velocity_win
  AND NOT promo_confounded
```

Useful as a stricter signal for real demand improvement.

## Recommended Default

The default win should compare each SKU against its trailing 4-week average using a productivity-aware measure:

```text
sku_week_win =
  current_units_per_store_or_tdp
  >
  trailing_4_week_avg_units_per_store_or_tdp
```

Then show promo and distribution flags nearby so users can see whether a win was demand-led or caused by reach, price, or promotion.

Prior-week comparison should be available, but it may be noisy. Same-week-last-year comparison should be added when enough history is available.

## Complementary Group Health

For a selected SKU group:

```text
active_sku_count = count of SKUs with sufficient evidence that week
weekly_win_count = count of active SKUs where sku_week_win = TRUE
weekly_loss_count = active_sku_count - weekly_win_count
weekly_win_pct = weekly_win_count / active_sku_count
```

Suggested labels:

| Pattern | Rule of thumb |
|---|---|
| Broad Growth | group units or dollars up, win_pct >= 70% |
| Healthy Mix | group value up, win_pct between 50% and 70% |
| Concentrated Growth | group units or dollars up, win_pct < 50% |
| Possible Cannibalization | focal wins, related SKUs lose, group growth is flat or weak |
| Portfolio Decline | group units or dollars down, win_pct < 50% |
| Distribution-Led Growth | group units up, win_pct weak, TDP up materially |

## Cannibalization Pattern Logic

The weekly win layer can support simple cannibalization pattern detection:

```text
focal_win = TRUE
related_loss_count >= threshold
group_units_per_store_change <= small_positive_threshold
```

Plain-language interpretation:

```text
The focal SKU improved, but the related group did not expand.
Several related SKUs lost at the same time.
This may indicate demand transfer rather than incremental growth.
```

For a pack ladder, that might read:

```text
Brownie Batter 4pk won this week.
Brownie Batter 1ct and 12pk lost.
Total Brownie Batter units per store were flat.
Pattern: possible pack-size cannibalization.
```

## UI Views This Enables

### 1. SKU win matrix

Rows are SKUs. Columns are weeks. Cells show win, loss, neutral, or insufficient data.

```text
              W1   W2   W3   W4   W5
1ct Brownie    +    -    -    +    +
4pk Brownie    +    +    +    +    -
12pk Brownie   +    -    -    -    +
```

This makes repeated substitution patterns easier to see than a dense metric table.

### 2. Portfolio win count trend

Show `weekly_win_pct` as a line next to group units/store and group dollars/store.

Key interpretation:

- units up and win_pct up: healthy growth
- units up and win_pct down: concentrated growth
- units flat and focal win: possible cannibalization
- dollars up and units flat: possible premiumization or trade-up

### 3. Focal versus basket contribution

Show whether a focal SKU's growth is accompanied by broad basket growth or offset by related SKU losses.

Useful questions:

- Is the focal SKU lifting the whole set?
- Is the focal SKU only reallocating demand?
- Are complementary items improving together?
- Are pack sizes trading volume back and forth?

### 4. Drillable probability view

For each SKU pair or group, show simple historical probabilities:

```text
P(comparison SKU loses | focal SKU wins)
P(group grows | focal SKU wins)
P(5+ SKUs win | focal SKU promoted)
P(pack ladder grows | 4pk wins)
```

These are approachable statistics that business users can understand without needing to inspect a full model.

## Simple Metrics to Add

Recommended first-pass metrics:

- `sku_week_win_flag`
- `sku_week_loss_flag`
- `sku_week_neutral_flag`
- `active_sku_count`
- `weekly_win_count`
- `weekly_loss_count`
- `weekly_win_pct`
- `focal_win_flag`
- `related_loss_count`
- `related_loss_pct`
- `group_units_per_store_change_pct`
- `group_dollars_per_store_change_pct`
- `win_concentration_ratio`
- `focal_share_of_group_gain`

Useful ratio formulas:

```text
win_concentration_ratio = focal_units_gain / total_positive_units_gain_across_group

focal_share_of_group_gain = focal_units_change / group_units_change

related_loss_pct = related_loss_count / related_active_sku_count
```

These can be shown in simple UI language:

- "5 of 7 SKUs won"
- "71% group win rate"
- "Focal SKU captured 64% of all positive unit gains"
- "3 related SKUs lost while focal SKU won"

## Bayesian Extension

The win-count approach plays well with Bayesian statistics because each SKU/week can be treated as evidence.

Example:

```text
weekly_win_count ~ Binomial(active_sku_count, portfolio_health_probability)
```

A Bayesian layer could estimate:

- the probability that a SKU group is healthy this week
- the probability that a focal SKU win coincides with related SKU losses
- the probability that a pack ladder is expanding versus shifting demand
- credible intervals around win rates for sparse geographies

Why this is useful:

- works naturally with true/false win data
- handles small samples better than raw percentages alone
- provides uncertainty ranges instead of false precision
- is easier to explain than many black-box outputs

Example user-facing language:

```text
This SKU group has a 78% estimated probability of broad-based growth this week.
The credible range is 62% to 89% because only four SKUs had enough evidence.
```

## Neural Network Extension

The win matrix can also support neural network approaches later, especially when enough history is available.

Possible approaches:

- sequence models that learn week-by-week SKU interaction patterns
- embeddings that learn which SKUs tend to win or lose together
- graph neural networks where SKUs are nodes and substitution or complementarity relationships are edges
- multi-task models that predict both numeric demand and win/loss state

Potential inputs:

- SKU win/loss sequences
- units and dollars per store
- TDP and ACV
- promo flags
- price and discount depth
- pack size and flavor attributes
- geography and channel
- relationship type between focal and comparison SKU

Potential outputs:

- probability each SKU wins next week
- probability the group grows broadly
- probability focal growth is incremental
- likelihood of donor-recipient relationships
- early warning of concentrated growth or cannibalization

This should be treated as a later-stage enhancement. The first release should keep the win-count layer deterministic and interpretable.

## Correlation and Association Metrics

The win layer also enables simple association metrics:

```text
co_win_rate = weeks_both_skus_win / weeks_both_active

opposition_rate = weeks_focal_wins_comparison_loses / weeks_both_active

lift_of_comparison_loss_given_focal_win =
  P(comparison_loses | focal_wins)
  /
  P(comparison_loses)
```

Interpretation:

- high `co_win_rate`: products may be complementary or jointly affected by category growth
- high `opposition_rate`: possible substitution or cannibalization pattern
- high conditional loss lift: focal wins may be associated with comparison losses

These metrics are not causal by themselves, but they are excellent drillable clues.

## How This Fits With the Main Tool

This is a bonus path, not a replacement for the main cannibalization model.

The main model still needs:

- units and dollars
- base units and base dollars
- distribution and velocity
- price and promo controls
- geography and channel context
- product relationship distance
- pre/post event windows

The win-count layer adds:

- fast visual pattern detection
- approachable percentages and ratios
- simple drill-down paths
- a bridge to Bayesian and neural network methods
- a cleaner way to explain whether products are winning together

## Recommended Positioning

Describe this to the client as:

```text
In addition to measuring units and dollars, Aevah can track whether each SKU in a related product set is winning or losing each week. This lets the client see whether growth is broad-based across complementary products or concentrated in one item at the expense of others. The result is an intuitive weekly health view that can be drilled into with units, dollars, probabilities, ratios, and model scores.
```

This is especially valuable because business users often understand:

- "6 of 7 SKUs improved"
- "Win rate fell from 86% to 29%"
- "The focal SKU won while three related SKUs lost"

faster than they understand a dense table of feature values.
