# Mo Build Field Guide Addendum — Price Elasticity

This addendum extends `Mo_Build_Field_Guide.docx` for the new peer-level
Price Elasticity module in Mo. Use it after the cannibalization workflow is
loaded and verified.

## What You Are Building

Mo now has two study tools:

| Tool | Main question |
|---|---|
| Cannibalization | Is a BUILT SKU or pack size stealing demand from another SKU? |
| Price Elasticity | How do price, promo depth, pack size price gaps, and competitor price gaps affect BUILT demand? |

The user should be able to switch between the tools from the top-level Mo menu.
Each tool keeps the same Determine / Diagnose / Decide rhythm.

## New Druid Outputs

Run these after the existing cannibalization Q0-Q13 sequence:

| Query | Output table | What it does |
|---|---|---|
| Q14 | `price_elasticity_weekly_features` | Adds price per bar, log price, log units, promo depth bucket, and seasonality controls |
| Q15 | `price_pack_ladder_weekly` | Compares price levels between pack sizes of the same specific flavor |
| Q16 | `price_competitive_weekly` | Compares BUILT price per bar against Tier 1 competitors in the same account/geography/week |
| Q17 | `price_elasticity_training_features` | Builds regression-ready windows for own-price, cross-price, and promo elasticity |
| Q18 | `scored_price_elasticity` | Stores model outputs, confidence, drivers, and recommended actions |
| Q19 | `price_elasticity_forecast_weekly` | Stores scenario forecasts for price and promo decisions |
| Q20 | `mulo_food_pack_size_norms` | Creates MULO FOOD protein bar norms for 1ct, 4pk, 8pk, and 12pk |
| Q21 | `flavor_protein_driver_features` | Compares flavor and protein content against sales, velocity, and store penetration |
| Q22 | `price_event_queue` | Stores significant price, promo, new item, benchmark, confidence, and price-defense events |

## Price Fields to Verify First

Before training, check that these columns are populated:

- `ARP`
- `Base ARP`
- `ARP, Promo`
- `ARP, Non-Promo`
- `ARP % Discount, Any Promo`
- `Units, Promo`
- `Units, Non-Promo`
- `Units, % Promo`
- `Promo Weeks`
- `TDP`
- `Average Weekly Units SPM`
- `Average Weekly Units Per Store Selling Per Item`
- `PACK COUNT`
- `Brand`
- `FLAVOR`
- `Subcategory`
- `% of Stores Selling`
- `NFP - PROTEIN`
- `NFP RANGES - PROTEIN VALUE`

If `PACK COUNT` is missing or wrong, price per bar will be wrong. Stop and fix
the product mapping before scoring.

## MULO Food Norms Diagnostic

Add a Diagnose screen that compares a BUILT specific flavor against MULO FOOD
protein bar category norms for:

- 1ct
- 4pk
- 8pk
- 12pk

For each pack size, show:

- BUILT ARP
- category norm ARP
- BUILT price per bar
- category norm price per bar
- Units SPM index vs norm
- percent of stores selling index vs norm
- TDP / distribution index vs norm

Use this view for two objectives:

1. Compare flavor vs protein content to understand which better explains sales,
   velocity, and store penetration.
2. Evaluate the 12-pack vs 4-pack pricing strategy against MULO FOOD category
   norms so the pack ladder does not overprice the value pack or collapse the
   4-pack role.

Guardrail: protein content can explain shopper permission and shelf fit, but it
should not be treated as the only demand driver. Control for flavor, pack size,
price per bar, promo, and TDP before claiming protein is driving the result.

## Guardrails

Do not trust an elasticity score when:

- fewer than 8 usable weeks exist in the selected window
- price barely moved
- TDP changed materially at the same time as price
- promo weeks changed but promo mechanics are missing
- competitor price is missing for the selected account/geography
- the row is from military / DECA channels

Show Low confidence instead of hiding the row when the user can still learn from
the context.

## Significant Price Events

Mo should actively watch for events, not wait for the analyst to inspect every
chart. Add a `price_event_queue` with these event types:

- `NEW_ITEM_PRICE_BASELINE`
- `DRASTIC_PRICE_CHANGE`
- `PROMO_DEPTH_SHIFT`
- `PROMO_RESPONSE_BREAKPOINT`
- `COMPETITIVE_PRICE_GAP`
- `PACK_NORM_GAP`
- `ELASTICITY_CONFIDENCE_DOWNGRADE`
- `PRICE_DEFENSE_OPPORTUNITY`
- `PACK_LADDER_COMPRESSION`

Start with these deterministic triggers:

```text
absolute price change >= 15%
or absolute price change >= $2.00
or promo depth changes by 10+ points
or BUILT price gap vs Tier 1 competitor >= 9%
or BUILT price index vs MULO pack norm >= 1.07
or new item is between week 8 and week 16
or elasticity confidence falls from High/Medium to Low
```

Every event must include:

- the trigger value
- confidence
- source table
- source columns
- model version
- scoring window
- geography/account scope
- top SHAP drivers or another feature-attribution method
- a plain-language Mo narrative
- a recommended action

Do not let Mo show a black-box label such as "Elastic Risk" without the trigger,
drivers, provenance, and drill path.

## Price Defense Insights

Price defense means Mo explains when BUILT should avoid overreacting to a
competitor price gap or short-term unit softness.

Examples:

- If BUILT is priced above a competitor but velocity and store penetration remain
  strong, Mo should say "defend price, monitor competitor promo weeks."
- If a competitor promotes below BUILT and BUILT velocity drops without TDP loss,
  Mo should recommend a temporary promo response before a permanent ARP cut.
- If the 12-pack is above the MULO value-pack norm and store penetration is weak,
  Mo should recommend testing a value correction.
- If the 4-pack falls during a 12-pack discount, Mo should warn that the 12-pack
  lift may be sourced from the BUILT pack ladder.

## Model Setup

Train price models separately from cannibalization models.

| Model | Target |
|---|---|
| Own-price elasticity | BUILT unit or base-unit response to its own price |
| Cross-price elasticity | BUILT response to another pack size or competitor price |
| Promo elasticity | Unit lift by discount depth and promo mechanic |
| Price forecast | Low/base/high unit response under planned ARP, promo depth, and competitor gap |

Start simple: regularized regression or LightGBM regression with SHAP drivers.
The first goal is a trusted business read, not a perfect econometric model.

## What-If Calculator Formula

Mo should support user-entered scenarios like:

> What if we decrease price by $3 on the 12-pack?

Use this deterministic first-pass formula before applying model guardrails:

```text
percent_price_change = (new_price - current_price) / current_price
expected_percent_unit_change = signed_elasticity * percent_price_change
forecast_units = current_units * (1 + expected_percent_unit_change)
```

Example:

```text
Current ARP = $22.99
New ARP     = $19.99
Price drop  = -$3.00

percent_price_change = (19.99 - 22.99) / 22.99 = -13.05%
signed elasticity    = -1.5
unit lift estimate   = -1.5 * -13.05% = +19.57%
```

Important convention:

- Store own-price elasticity two ways: `own_price_elasticity_signed` and
  `own_price_elasticity_abs`.
- Use `own_price_elasticity_signed` in formulas. Normal own-price elasticity is
  usually negative for normal goods.
- Display `own_price_elasticity_abs` in the UI because business users usually
  expect price elasticity to be reported as a positive value.
- Keep cross-price elasticity signed because the sign explains whether the other
  item is a substitute or complement.

For competitors, use signed cross-price elasticity:

```text
competitor_unit_change_pct =
  competitor_cross_price_elasticity * built_price_change_pct
```

If BUILT cuts price and a competitor is a substitute, competitor units may fall.
Example: `+0.25 * -13.05% = -3.26%`.

Flag the simple estimate as Low confidence or "needs guardrail review" when the
price cut is very large, TDP changes at the same time, promo mechanics change,
or the move could pull demand from another BUILT pack size.

## UI Wiring

Use `mockups/mo_intelligence_suite_v11.html` as the new mockup target.

Price screen mapping:

| Screen | Backend source |
|---|---|
| Pricing events | `scored_price_elasticity` alerts |
| Elasticity summary | `scored_price_elasticity` by focal UPC |
| Pack price | `price_pack_ladder_weekly` |
| Promo response | `price_elasticity_training_features` grouped by discount bucket |
| Competitive price | `price_competitive_weekly` |
| MULO norms | `mulo_food_pack_size_norms` + `flavor_protein_driver_features` |
| Price explanation | `price_event_queue` + SHAP fields on `scored_price_elasticity` |
| Price forecast | `price_elasticity_forecast_weekly` |
| Pricing action | scored action labels plus cannibalization links |

Keep the existing Mo theme:

- blue = information / scenarios
- amber = watch / medium confidence
- red = elasticity risk / competitor gap warning
- green = recommended band / healthy lift

## Link Back to Cannibalization

When price movement overlaps with donor pressure, Mo should say so plainly.

Examples:

- "This 4pk promo lift may be partly sourced from the 1ct donor."
- "The price cut drove units, but pack ladder cannibalization rose in the same weeks."
- "The competitor gap looks external; BUILT pack sizes are not showing donor loss."

That linkage is the reason to keep both tools in one Mo suite.
