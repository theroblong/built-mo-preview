# Recommended SPINS Measures for Cannibalization

This one-pager summarizes the SPINS measures that are most useful for cannibalization analysis based on the current project materials, including [BUILT- SPINS MEASURES.xlsx](/Users/jasonbrazeal/Documents/FirstAgent/BUILT-%20SPINS%20MEASURES.xlsx).

The goal is to separate true substitution and assortment effects from changes caused by promotion, pricing, distribution, launch timing, and market context.

## Core recommendation

For a first-pass cannibalization model, the most important SPINS measures to carry forward are:

- observed demand: `Units`, `Dollars`
- underlying non-promo demand: `Base Units`, `Base Dollars`
- promo-attributed lift: `Incr Units`, `Incr Dollars`
- distribution and reach: `# Stores Selling`, `% of Stores Selling`, `TDP`
- per-store-style productivity: `Average Weekly Units Per Store Selling Per Item`, `Average Weekly Dollars Per Store Selling Per Item`
- pricing: `ARP`, `Base ARP`, `ARP, Promo`, `ARP, Non-Promo`
- promo intensity and response: `ARP % Discount, Any Promo`, `Units, Promo Effect Index`, `Dollars, Promo Effect Index`
- market position: `Unit Shr, Category`, `Unit Shr, Sub-Cat`, `Dol Shr, Category`, `Dol Shr, Sub-Cat`
- launch timing: `First Week Selling`, `Number of Weeks Selling`

## Measure groups

### 1. Demand outcome measures

These are the primary outcome measures for cannibalization analysis.

- `Units`: observed unit sales
- `Dollars`: observed dollar sales
- `Base Units`: estimated units without retailer promotion
- `Base Dollars`: estimated dollars without retailer promotion

Recommended use:

- use `Base Units` as the cleanest starting signal for underlying demand substitution
- compare against `Units` to understand real-world operational effects
- use `Dollars` and `Base Dollars` when revenue effects matter, not just volume

### 2. Promo decomposition measures

These measures help separate promotion-driven changes from actual cannibalization.

- `Incr Units`
- `Incr Dollars`
- `Units, Promo`
- `Units, Non-Promo`
- `Dollars, Promo`
- `Dollars, Non-Promo`

Important caveat:

- `Incr Units` is promo-attributed incremental volume, not a generic week-over-week sales change
- it should be interpreted alongside `Units` and `Base Units`, not instead of them

### 3. Distribution and availability proxy measures

These help explain whether sales movement came from product reach rather than substitution.

- `# Stores Selling`
- `% of Stores Selling`
- `TDP`
- `TDP, Any Promo`
- `TDP, Non-Promo`

Recommended use:

- use these to control for distribution expansion and contraction
- if a SKU gains units while `TDP` also rises sharply, the change may be driven by reach rather than cannibalization

### 4. Store productivity measures

These help estimate how well a product performs where it is already selling.

- `Average Weekly Units Per Store Selling Per Item`
- `Average Weekly Dollars Per Store Selling Per Item`

These are the closest SPINS measures to a true units-per-store and dollars-per-store view.

### 5. Distribution-normalized productivity measures

These are useful, but they are not the same as simple per-store averages.

- `Units SPM`
- `Dollars SPM`
- `Units SPP`
- `Dollars SPP`
- `Units/TDP`
- `Dollars/TDP`

Recommended use:

- use these when you want productivity adjusted for distribution scale
- do not present them as literal store-level averages
- do not use `Units/TDP` or `Units SPP` as a direct substitute for `Units / # Stores Selling`
- if `# Stores Selling` is unavailable, these can still be used as fallback productivity proxies with explicit labeling

### 6. Price and discount measures

These help separate price-driven switching from assortment-driven switching.

- `ARP`
- `Base ARP`
- `ARP, Promo`
- `ARP, Non-Promo`
- `ARP % Discount, Any Promo`

Recommended use:

- monitor these alongside `Units` and `Base Units`
- large unit gains paired with deep discounting are less likely to be pure cannibalization effects

### 7. Promo response measures

These help quantify how strongly a product responds to merchandising support.

- `Units, Promo Effect Index`
- `Dollars, Promo Effect Index`

Recommended use:

- use these to identify items that are highly promotion-sensitive
- highly promo-sensitive items can create misleading cannibalization signals if promo is not controlled for

### 8. Share measures

These show whether a SKU is gaining or losing position within the relevant market.

- `Unit Shr, Category`
- `Unit Shr, Sub-Cat`
- `Dol Shr, Category`
- `Dol Shr, Sub-Cat`

Recommended use:

- use share changes to judge whether gains are coming from competitors, from same-brand switching, or from total category growth

### 9. Launch and lifecycle timing measures

These help identify launch windows and immature selling periods.

- `First Week Selling`
- `Number of Weeks Selling`

Recommended use:

- use these to identify true launch periods
- use them to avoid comparing a new SKU directly against mature items without accounting for ramp time

## Recommended minimum feature set for a pilot

If the first pilot needs a smaller SPINS feature set, start with:

- `Units`
- `Base Units`
- `Dollars`
- `Base Dollars`
- `Incr Units`
- `# Stores Selling`
- `% of Stores Selling`
- `TDP`
- `Average Weekly Units Per Store Selling Per Item`
- `ARP`
- `Base ARP`
- `ARP % Discount, Any Promo`
- `Units, Promo Effect Index`
- `Unit Shr, Sub-Cat`
- `First Week Selling`

## Practical interpretation notes

- `Base Units` is often the best primary target for cannibalization because it reduces promo distortion.
- `Units` should still be retained because the business ultimately experiences observed sales, not only modeled base demand.
- `Incr Units` should be used as a promo control, not as a substitute for week-over-week demand change.
- If weekly SPINS data is available, add LAG-based fields such as `units_wow_delta` and `base_units_wow_delta`.
- If inventory and authorization data are missing, distribution measures like `TDP` and `# Stores Selling` become even more important as context controls.

## Bottom line

SPINS already provides a strong first layer for cannibalization analysis if the model uses the measures in the right roles:

- `Units` and `Dollars` for observed outcomes
- `Base Units` and `Base Dollars` for underlying demand
- `Incr Units` and `Incr Dollars` for promo attribution
- `TDP`, `% of Stores Selling`, and per-store-style measures for reach and productivity
- price, promo, share, and launch measures for interpretation and control
