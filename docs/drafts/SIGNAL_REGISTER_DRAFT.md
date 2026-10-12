# Forecast signal register (DRAFT v1, 2026-10-12, internal)

Purpose: one place that records every demand signal Mo has, or could have, so each one enters the
forecast **once**, **without look-ahead**, and with its test status known. Prompted by Rob's
`docs/forecasting_growth_signals.md`. Built from a scout sweep (2026-10-12) of the code, README,
SETTLED_FINDINGS, the Druid load list and memory notes; quotes and file:line refs in the session
log. Not yet skeptic-reviewed.

## The five facts recorded for every signal
1. **Source and owner**
2. **Known ahead or only observed?** Known-ahead signals (calendars, plans) can drive future weeks.
   Observed-only signals (weather, social, competitor moves) explain the past and need their own
   forecast to help the future.
3. **Dated versions?** Backtests may only use what was known on the forecast date. A plan without
   dated snapshots can't be tested honestly.
4. **Where it enters:** base model input / separate layer on top / display only / not used.
   Each signal enters in exactly one place (no double counting).
5. **Test status:** untested / testing / proven / rejected, with the experiment ID.

## Register

| # | Signal | Source / owner | Known ahead? | Dated versions? | Enters where today | Test status | Next step |
|---|---|---|---|---|---|---|---|
| 1 | Recent sales, lags 1/4/13/52, 4/8/13-wk averages and trends | SPINS (weekly) | n/a | SPINS restates up to 35 wks back | Base model (56 inputs) | Proven core | Lag 26 / 26-wk average: cheap add (MO_136) |
| 2 | Week of year (annual + half-year curves) | Calendar | Yes | n/a | Base model | In model; a separate Fourier add was rejected (MO_57, older model) | None |
| 3 | Holiday and retail calendar flags | None stored; Calendarific planned | Yes | n/a | Not used | **Rejected:** all 7 holiday flags hurt (MO_54, older 28-input model) | Do not re-add without a new reason |
| 4 | Seasonal index (STL, BUILT items) | MO_59, built from SPINS | n/a | Index built 2026-10-01 only | Recursive model, post-hoc step + 10% pull | **Look-ahead confirmed;** honest rebuild worse than none (MO_127) | Under review (settings guide B2) |
| 5 | Category seasonality and category trend (competitors) | SPINS full category (`spins_full`, `built_filtered_weekly`); license OK for cloud (Rob, 2026-10-09) | No | Can rebuild as of each date | Not used | Untested | **MO_136:** category index + category trend, rebuilt as of each forecast date |
| 6 | Neighbor signals (same item at other retailers; sister items at same retailer) | SPINS | No | Yes (from history) | Partly: donor count / donor store count | Untested beyond donors | **MO_136** (also step 1 of the graph-model idea) |
| 7 | Store count (TDP) and per-store velocity | SPINS | Only via plans | No plan vintages | Base model (held at forecast-date value) | Future store counts worth <1 pt even with perfect foresight (MO_95/105); door-count ask closed (SETTLED) | None for existing items |
| 8 | **New item x retailer combinations** (new authorizations, retailer entries) | Not captured. Candidates: Connor's sheet, sales/retailer authorizations, item attributes | Yes, if BUILT records them | No | **Not covered:** ~14% of a quarter's volume is structurally missing | Structural floor measured (README ~220) | Design a new-distribution layer: velocity of comparable items x planned launch date per retailer (step 4) |
| 9 | Product lifecycle: launches, discontinuations, 2027 innovation | `item_attributes.csv` (Connor 7/22/26 + ItemDim 10/1/26 + SPINS) | Yes | Single snapshot | Not used | New-item rule: last value won in 2025, lost on 2026 dates (MO_79, MO_135) | Feeds row 8; snapshot each update |
| 10 | Price (ARP) and discount | SPINS; NS2 invoice $/bar | No forward price file | No | Base model (held at last price); elasticity research (MO_44, MO_61) | Elasticity research only; figures disagree between files | Reconcile the elasticity figures |
| 11 | SPINS promotions (TPR, display, feature) | SPINS | No (observed) | n/a | Base model history; **zeroed in future weeks** (target is base units) | Lift under-predicted ~2x (MO_70); lift ladder by discount depth (MO_73) | Keep promo lift as a layer on top |
| 12 | Trade promotion calendar (incl. 2027 lines) | Brian; `trade_promotions.csv` (Druid load) | **Yes** | **No:** one snapshot (2026-09-30) | Not used | Untested; 61.6% of events ran off-schedule (older) | **Start saving dated snapshots at every update**; feed the promo-lift layer, with a schedule-slip discount |
| 13 | Shipments, inventory, out-of-stocks | NetSuite NS2 (Ebad, 3.5 yrs weekly); Costco CRX in-stock / OOS fields (Circana) | Open orders only | No | Not used | Untested | Flag supply-constrained weeks so the model doesn't learn shortages as low demand |
| 14 | Influencer, paid social, marketing campaigns | BUILT marketing (no data) | Yes, if logged | No | Not used | None | **Start an event log now** (date, type, channel, reach) so it can be tested in 6-12 months |
| 15 | Macro (FRED, EIA) | FRED / EIA APIs (live in Mo Trends) | Partly | Yes (FRED vintages exist) | Display only | Archived (MO_76): window too short | Reopen with 2+ more years of data |
| 16 | Weather, Keepa, Placer, EDGAR, BLS | Planned only | No | n/a | Not used | None | Low priority at item-week level |
| 17 | Retailer strategies (resets, club promos, new banners) | Connor and sales (notes only) | Yes | No | Not used | None | Capture in the event log (row 14) |
| 18 | Saved forecasts (forward tracker) | Aevah; `forecast_versions` (append-only) | n/a | **Yes** | Scoring and budget vs latest estimate | First scorable 2026-12-06 | Keep saving at every SPINS delivery |

## What this changes in the plan
- **MO_136 shrinks to what is new and untested:** category seasonality and trend from full-category
  SPINS (rebuilt as of each date), neighbor signals, and lag 26 / 26-week average. Holiday flags are
  dropped (rejected in MO_54); macro stays archived (MO_76).
- **The biggest gap is row 8, new item x retailer combinations.** It is not the closed door-count
  ask (store counts for items already selling). It needs BUILT to record planned launches by
  retailer and date.
- **Start capturing now, even before use:** dated snapshots of the promo calendar and item
  attributes (rows 9, 12), and an event log for marketing and retailer events (rows 14, 17).
  Without dated history these can never be tested honestly.

## Data caveats that affect how signals are built (Jason, 2026-10-12)
- **SPINS weekly figures are averages over the week** (price, distribution and some rates), so small items carry rounding noise.
- **Promotions do not line up with SPINS weeks.** SPINS reports each week on a fixed week-ending day, while a retailer price
  promotion can run midweek to midweek, so one promotion is often split across two SPINS weeks with a diluted discount and lift
  in each. Rows 11 and 12 must therefore map promotions to SPINS weeks by the number of promo days in each week (an overlap
  fraction), not a yes/no promo-week flag, and lift should be measured over the two weeks together.

## Contradictions found (to resolve)
1. Forward promo file: README says "forward confirmed TPR file (Brian)"; the load list says "trade
   commitments, not confirmed shelf promotions" (Brian, 2026-09-30). The latter is current.
2. Elasticity: SETTLED says portfolio -0.34; README says -0.51 (86 retailers). Scope not stated.
   Mid-pressure elasticity also differs (-1.0 vs -0.25 to -0.63).
3. FRED: a memory note says "integrated ... ML features"; README says MO_76 archived. Archived is correct.
4. SPINS competitor license: project memory still carries it as open; Rob confirmed it on 2026-10-09.
   Closed.
