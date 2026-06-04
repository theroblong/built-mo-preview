# BUILT Final UX-Safe Metric Shortlist

This note defines which SPINS measures are appropriate for the polished end-user cannibalization experience at BUILT versus which ones should remain analyst-support or back-end-only signals.

The guiding principle is:

- narrow and high-confidence
- easy to explain
- difficult to misinterpret
- consistent with how business users naturally think about demand, price, reach, and launch timing

The companion CSV artifact is:

- [built_final_ux_safe_metric_shortlist.csv](/Users/jasonbrazeal/Documents/FirstAgent/outputs/built_final_ux_safe_metric_shortlist.csv)

## Tier definitions

- `End-User Safe`: strong candidate for polished BUILT-facing output
- `Analyst Support`: useful in modeling, QA, drill-down, or explanation layers, but usually too technical for headline UX
- `Avoid in Final UX`: technically useful in some cases, but too easy for end users to misread or over-trust

## Recommended end-user metric core

For a polished BUILT demand cannibalization experience, the strongest core metrics are:

- `Base Units`
- `Units`
- `TDP`
- `ARP`
- `Base ARP`
- `ARP % Discount, Any Promo`
- `# Stores Selling`
- `% of Stores Selling`
- `Average Weekly Units Per Store Selling Per Item`
- `Average Weekly Dollars Per Store Selling Per Item`
- `First Week Selling`
- `Unit Shr, Sub-Cat`

These work well because they cover the main business questions:

- what happened to demand
- what part may be driven by distribution
- what part may be driven by price or promotion
- how productive the item is where it sells
- whether the item is still in launch ramp
- whether it is gaining or losing position in the closest substitution set

They are also important because store-productivity measures help separate:

- true changes in demand at the point of sale
- changes caused mainly by expansion or contraction in distribution

In other words, if total `Units` change over time, BUILT will often need to know whether:

- more stores started selling the item
- fewer stores carried the item
- or the item truly sold better or worse within the stores where it was already present

That is why `# Stores Selling`, `% of Stores Selling`, and especially `Average Weekly Units Per Store Selling Per Item` should remain part of the final polished metric core if they are available as trusted SPINS measures.

## Measures to keep behind the scenes

Measures such as the following are still valuable, but usually belong in analyst views, model features, diagnostics, or explanation tooling rather than the final user-facing layer:

- `Incr Units`
- `Incr Dollars`
- `Units, Promo`
- `Units, Non-Promo`
- `Dollars, Promo`
- `Dollars, Non-Promo`
- `TDP, Any Promo`
- `TDP, Non-Promo`
- `Units SPM`
- `Dollars SPM`
- `ARP, Promo`
- `ARP, Non-Promo`
- `Units, Promo Effect Index`
- `Dollars, Promo Effect Index`
- `Unit Shr, Category`
- `Dol Shr, Category`
- `Dol Shr, Sub-Cat`
- `Number of Weeks Selling`

These measures are helpful, but they generally require more interpretation discipline than a polished business experience should assume.

## Measures to avoid in the final BUILT UX

The following should generally not be used as polished front-end metrics:

- `Units SPP`
- `Dollars SPP`
- `Units/TDP`
- `Dollars/TDP`

The main reason is that users can easily mistake these for literal store productivity measures when they are actually normalized by ACV points or distribution points.

If they are used at all, they should stay in analyst support layers with explicit labeling and explanation.

## Bottom line

The final BUILT user experience should emphasize a small set of demand, distribution, price, launch, and subcategory-position metrics that are both reliable and easy to understand.

The analyst layer can still remain richer behind the scenes, but the end-user layer should stay selective and polished.
