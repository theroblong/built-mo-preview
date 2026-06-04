# Best Reliable Productivity Metrics From `All_items_extract_100.csv`

This note focuses only on what is actually available in [All_items_extract_100.csv](/Users/jasonbrazeal/Documents/FirstAgent/All_items_extract_100.csv).

The question is not what would be ideal in SPINS overall, but what can be used reliably from this specific extract without overpromising precision.

The companion CSV artifact is:

- [all_items_extract_100_best_reliable_productivity_metrics.csv](/Users/jasonbrazeal/Documents/FirstAgent/outputs/all_items_extract_100_best_reliable_productivity_metrics.csv)

## Bottom line

Because this extract does not include `# Stores Selling`, it does not support a true units-per-store calculation.

That means:

- we cannot reliably compute `Units / # Stores Selling`
- we cannot reconstruct store count from `TDP`, `Avg % ACV`, `Max % ACV`, or `Units SPP`
- we should not label any fallback metric as units per store

## Best available fallback metrics from this extract

### 1. `Units/TDP`

This is the strongest fallback productivity-style metric in the file because it is already provided directly by SPINS and does not require weak reconstruction.

Best use:

- use as the primary reach-adjusted productivity metric when store-count measures are missing

Important caveat:

- this is units per distribution point, not units per store

### 2. `Units SPM`

This is a solid secondary productivity measure because it is also provided directly by SPINS and adjusts for distribution scale through ACV.

Best use:

- use as a secondary normalized productivity control

Important caveat:

- this is not units per store and should not be presented that way

### 3. `Average Weekly Units SPM`

This can be useful as a support metric when comparing similarly defined time windows.

Best use:

- use as an analyst-support weekly-normalized productivity signal

Important caveat:

- still not a store-based productivity measure

## Best interpretive combination

If the goal is to separate true demand movement from distribution movement using only this extract, the best practical approach is to look at:

- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`

Interpretation pattern:

- if `Units` rises and `TDP` rises, some of the gain may be distribution-driven
- if `Base Units` rises while `TDP` is stable, demand improvement is more likely to be real
- if `Units/TDP` rises, the item may be becoming more productive relative to its reach

## Metrics to avoid over-interpreting

The following should not be used as polished substitutes for units per store:

- `Units SPP`
- `Units/TDP`
- `Units SPM`

They can still be useful, but only with careful labeling and explanation.

## Recommendation

For a polished BUILT experience that is restricted to this extract, I would prioritize:

- `Base Units`
- `Units`
- `TDP`
- `Units/TDP`

and frame them as:

- demand
- underlying demand
- reach
- reach-adjusted productivity

That is narrower than a full SPINS view, but it is much more trustworthy than pretending we have a true units-per-store measure when we do not.
