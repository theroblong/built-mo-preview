# BUILT Mo Intelligence Suite — Druid Query Plan & ML Model Design
## Version 6 — v11 suite shell, cannibalization, and price elasticity extension

### May 29, 2026 price elasticity extension

Mo now needs to operate as an intelligence suite rather than a single
cannibalization tool. Cannibalization remains the first study tool, and
**Price Elasticity** becomes a peer-level module with equal menu placement.
The shared foundation is still the enriched weekly SPINS item table, flexible
comparison pools, Druid-first aggregation, Python/LightGBM scoring, visible
provenance, and business-facing guardrails.

The price elasticity module adds:

- own-price elasticity by BUILT SKU, pack size, account, geography, and window
- pack-ladder price architecture for same specific flavor pack sizes
- cross-price response between BUILT pack sizes, especially 1ct / 4pk / 12pk
- competitive price-gap tracking against Tier 1 competitors such as BAREBELLS,
  QUEST, RXBAR, PERFECT BAR, and THINK!
- promo elasticity by discount depth and mechanic: TPR, display, feature, SPK,
  and combinations
- MULO FOOD protein bar category norms for 1ct, 4pk, 8pk, and 12pk pack sizes
  by price per bar, velocity, store penetration, promo mix, and distribution
- flavor vs protein-content diagnostics to estimate which factor is more
  associated with sales and store penetration
- scenario forecasting for ARP, promo depth, competitor gap, and expected unit
  / base-unit response
- user-entered what-if scenarios such as "$3 price drop on 12-pack" with
  explicit percent price change, expected unit lift, pack-ladder pressure, and
  competitor response
- linkable navigation between Price Elasticity and Cannibalization so a user can
  inspect whether a price move is creating true demand, promo pull-forward, or
  internal donor pressure

### May 21, 2026 implementation update

This version now assumes the expanded 214-column SPINS extract represented by
`All_items_extract_41926-h100.csv`. Section 13 is the build-ready appendix for
the client Azure/Aevah Druid discussion: it includes concrete Druid SQL, Python
training/scoring scripts, v10 UI wiring targets, and the recommended 10% pilot
upload strategy.

### Changelog from v4

| Area | Change |
|---|---|
| **UI label philosophy** | All user-facing "dist N" badges and scope labels have been replaced with plain English. `relationship_distance` and `comparison_type` remain first-class internal columns in every Druid table, ML feature set, and Python pipeline — they are never removed. Only the strings rendered in the browser change. |
| **`comparison_scope_label` values** | The `comparison_scope_label` column in `scored_cannibalization` (and its echo in the context bar) now stores the new plain-English strings defined in Section 2.4. The `comparison_type` enum is unchanged and stored alongside it. |
| **Event card relationship badge** | Priority Events cards previously showed "dist 1 · Pack ladder" and "dist 3 · Cross-flavor". They now show "Pack size comparison" and "Cross-flavor (BUILT portfolio)" respectively. The badge maps from `comparison_type` at render time using the label lookup table in Section 2.4. |
| **Geography screen column header** | `<th>Channel</th>` → `<th>Channel / Outlet</th>`. Row values now show the literal SPINS `Channel/Outlet` string (e.g. `CONVENTIONAL|FOOD`, `CONVENTIONAL|MULTI OUTLET`) rather than derived labels like "Grocery" or "Club". |
| **Action screen column header** | Same change: `<th>Channel</th>` → `<th>Channel / Outlet</th>`. Rows now show `CONVENTIONAL|FOOD`, `CONVENTIONAL|MULTI OUTLET`, `CONVENTIONAL|CONVENIENCE`, `CONVENTIONAL|MASS MERCH` directly. |
| **Scope bar `scope-bar-value`** | Previously showed the raw `comparison_type` enum string (e.g. `SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER`). Now shows the plain-English label (e.g. "Pack size comparison — same flavor, same brand"). The enum is still stored in `scored_cannibalization.comparison_type`. |
| **Cross-flavor dist strip** | Pill buttons previously read "dist 1 · Pack ladder", "dist 3 · Cross-flavor (same parent brand)", etc. Now read "Pack sizes (same flavor)", "Cross-flavor · BUILT only", "Cross-flavor · any brand", "Other BUILT FLAVOR groups". |
| **SHAP narrative template** | "Pack distance = {N} ({substitution_read})" → "Pack size gap ({focal_pack}ct → {donor_pack}pk)". |
| **Explanation driver row** | "Pack distance (1→4 = 3)" → "Pack size gap (1ct → 4pk)". The underlying SHAP value is unchanged; only the display label differs. |
| **Provenance panel comparison pool** | "Same flavor BUILT packs (dist 1)" → "Pack size comparison — Mint Brownie (all pack sizes)". |
| **Forecast footer** | "Pack distance and relationship_distance are first-class model features" → "Pack size gap and flavor relationship type are first-class model features". |
| **Modal step 2 scope-dist lines** | Distance-number descriptions replaced with plain explanations of what each scope adds. See Section 2.4. |
| **Modal step 3 filter grid** | Channel filter now exposes literal SPINS `Channel/Outlet` values. Retail Account filter exposes literal SPINS `Retail Account` values. Geography dropdown groups panels by Channel/Outlet and Geography Level exactly as they appear in the SPINS extract. |
| **JS scopeDistances map** | Updated to return new plain-English strings. Internal `data-scope` attribute values (1–6) are unchanged so no backend logic breaks. |

### Changelog from v4 (carried forward, unchanged)

| Area | Change |
|---|---|
| Flavor mapping column aliases | The CSV column `brand` is `brand_line`. The CSV column `flavor_family` is `spins_flavor_mapped`; the production comparison key is `spins_flavor_canonical`, with `spins_flavor` retained as a compatibility alias. |
| `parent_brand` clarification | `parent_brand = BUILT` for every row in `flavor_mapping`. Comparison pool join uses `parent_brand` for brand-identity tests. |
| Section 2.5 pack ladder reference table | Rebuilt entirely from `built_specific_flavor_mapping.csv`. All CHOCOLATE MINT examples use the three correct specific flavors: Mint Brownie (BUILT BAR), Grasshopper Cookie (BUILT BAR), Mint Chip (BUILT PUFF). |
| Metric naming | `Units/TDP` replaced everywhere by `avg_weekly_units_spm`. Explicitly excluded from the UX. |
| Scored output schema | `scored_cannibalization` carries `incremental_share`, `comparison_type`, `relationship_distance`, `p_value`, `z_score_donor`, all five context bar denormalized fields. |
| Expanded SPINS extract | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level` sourced directly; no geography parser required. |
| Four window sizes | 4w, 13w, 26w, YTD all pre-computed in Query 3 via CASE WHEN, stored as `window_type`. |

---

## Section 1. Data Architecture Overview

### Source table in Druid

```
datasource: spins_weekly_pos
grain:       UPC × Retail Account × Geography × __time (week-ending date)
volume:      ~95M rows, ~50GB
key dims:    UPC, Channel/Outlet, Geography Level, Retail Account,
             Retail Account Level, Geography, __time
key facts:   Units, Base_Units, Dollars, Base_Dollars, TDP, Max_ACV,
             Avg_Weekly_Units_SPM, Avg_Weekly_Units_Per_Store_Selling_Per_Item,
             Units_SPM, ARP, Base_ARP, Promo_Weeks, Incr_Units,
             First_Week_Selling, Number_of_Weeks_Selling, Pack_Count, FLAVOR,
             #_of_Stores, #_of_Stores_Selling, %_of_Stores_Selling,
             promo lift and YAGO companion metrics
```

### Expanded extract field usage

The partial sample `All_items_extract_41926-h100.csv` shows SPINS can now provide
fields that were previously inferred or unavailable. Use them as follows:

The sample has only 100 rows, so it should be used for schema and field-purpose
decisions, not for final coverage assumptions. The production ingestion should
be schema-first and scale to the later multi-GB extracts without hard-coding the
sample's retail accounts, channels, or geographies.

| Field family | Source columns | Best use in the cannibalization tool |
|---|---|---|
| Retail context | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography` | Direct UI filters, scope bars, heatmap pivots, and model grouping keys. No channel/market/retailer parser is required. |
| Product hierarchy | `Department`, `Category`, `Subcategory`, `Brand`, `UPC`, `Description`, `PACK COUNT`, `FLAVOR` | Category filtering, parent-brand normalization, pack ladder construction, SPINS `FLAVOR` grouping. |
| Nutrition/product attributes | `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `NFP - SUGARS`, `NFP - CALORIES`, `STORAGE`, `UNIT OF MEASURE` | Competitor similarity and substitution priors. Useful for same-FLAVOR competitive matching and future analog launch selection. |
| Distribution | `Avg % ACV`, `Max % ACV`, `TDP`, `Average Weekly TDP`, `# of Stores`, `# of Stores Selling`, `% of Stores Selling` | Separate reach expansion from true demand transfer. Store-selling fields are preferred for retail execution diagnostics. |
| Velocity | `Average Weekly Units SPM`, `Units SPM Per Item`, `Average Weekly Units Per Store Selling Per Item`, `Average Weekly Units per Store Selling` | Primary demand-pull signals. Prefer `Average Weekly Units Per Store Selling Per Item` for the UI when available; keep `Average Weekly Units SPM` as a stable normalized model feature. |
| Price and base price | `ARP`, `Base ARP`, `ARP, Promo`, `ARP, Non-Promo`, `ARP % Discount, Any Promo` plus display/feature/TPR/SPK variants | Price confound control and promo-depth diagnostics in the Provenance panel. |
| Promo mechanics | `Dollars/Units Promo`, `Dollars/Units Non-Promo`, `% Promo`, `Promo Weeks`, promo ACV/TDP/Weight Weeks, promo lift fields | Distinguish cannibalization from promo-driven focal lift or donor defense activity. |
| Baselines | `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units` | Core pre/post and incremental-share calculations. |
| YAGO companions | Any `, Yago` columns | Seasonality and retailer-specific baseline controls. Do not show by default in the UI, but use in feature engineering and QA. |

Fields still intentionally avoided in the final UX: `Units/TDP` and `Dollars/TDP`.
They may be retained for QA, but the model and UI should rely on store/SPM
velocity fields because those map better to the user question, "is each selling
store actually moving more units?"

### Reference tables (load as Druid lookups or join-time CSVs)

| Table | Source | Key | Use |
|---|---|---|---|
| `flavor_mapping` | built_specific_flavor_mapping.csv | UPC | Adds `parent_brand`, `brand_line`, `spins_flavor_mapped`, `specific_flavor_normalized`, `pack_count`, `size_oz` |
| `flavor_canonical_overrides` | taxonomy-reviewed CSV/lookup | UPC | Converts raw/mapped FLAVOR conflicts into approved `spins_flavor_canonical` values while retaining provenance |
| `item_catalog` | Item_list_BUILT_and_Category.xlsx | UPC | Adds `Department`, `Category`, `Subcategory`, `Positioning_Group`, `Product_Type`, `Functional_Ingredient`, `Health_Focus`, `Size_Positioning`, **`competitor_tier`** |

**Column mapping from the raw CSV to the enriched schema:**

| CSV column | Enriched column | Notes |
|---|---|---|
| `brand` | `brand_line` | Values: `BUILT BAR`, `BUILT PUFF`, `BUILT SOUR PUFF`, `BUILT`. Not the parent brand. |
| Source `FLAVOR` | `spins_flavor_raw` | Literal SPINS source value from the expanded extract; retained for QA and provenance. |
| `flavor_family` | `spins_flavor_mapped` | FLAVOR value from `built_specific_flavor_mapping.csv`; used as input to canonicalization. |
| Override lookup | `spins_flavor_canonical` | Approved FLAVOR grouping used by the UI accordion, comparison pools, and heatmap pivots. |
| `spins_flavor_canonical` | `spins_flavor` | Compatibility alias used by existing query logic and UI payloads. |
| `specific_flavor_raw` | — | Source text before normalization; retained for QA only. |
| `specific_flavor_normalized` | `specific_flavor_normalized` | Canonical specific flavor name used for all pack-size and cross-brand comparisons. |
| `pack_count` | `pack_count` | Integer. CSV value takes precedence for BUILT rows. |

**`parent_brand` is a derived constant, not a CSV column.** It is set to `BUILT`
for every row in `flavor_mapping`, regardless of `brand_line`. In Query 1 the
join adds `'BUILT' AS parent_brand` for all matched rows. Competitor rows from
the Druid source table receive `parent_brand = c.brand` (the SPINS brand string)
and are never enriched through `flavor_mapping`.

**`competitor_tier`** is added to `item_catalog` as a static column for non-BUILT
brands. Values: `TIER_1_DIRECT` (RXBAR, BAREBELLS, QUEST, PERFECT BAR, THINK!,
ALOHA, NO COW, FULFIL, PURE PROTEIN, 1ST PHORM, SIMPLYPROTEIN, NUGO NUTRITION),
`TIER_2_BFY_ADJACENT` (KIND, LARABAR, CLIF BAR, CLIF BUILDERS, GOMACRO, BOBOS,
PROBAR, MEZCLA, TOSI, ORGAIN), `TIER_3_MAINSTREAM` (NATURE VALLEY, QUAKER CHEWY,
NUTRI-GRAIN, SPECIAL K, SUNBELT, KODIAK CAKES, NATURES BAKERY), `NULL` for BUILT.
Tier controls default display order on the Competitive screen (Tier 1 first).
It is never a filter.

**Flavor hierarchy:** Parent Brand > canonical SPINS `FLAVOR` > Specific Flavor.
`spins_flavor_raw` is sourced strictly from the SPINS `FLAVOR` field. The UI and
comparison pools use taxonomy-approved `spins_flavor_canonical`, exposed as the
compatibility alias `spins_flavor`. The three confirmed specific flavors under
canonical `CHOCOLATE MINT` are:
**Mint Brownie** (BUILT BAR, 1ct), **Grasshopper Cookie** (BUILT BAR, 1ct),
and **Mint Chip** (BUILT PUFF, 1ct/4pk/12pk). `Brownie Batter` maps to `BROWNIE`;
`Double Chocolate` maps to `CHOCOLATE`. Neither appears in any `CHOCOLATE MINT`
comparison pool. Mint Brownie Chocolate 18ct remains a taxonomy-review case
when raw/mapped FLAVOR appears as `MINT`; retain provenance and only canonicalize
to `CHOCOLATE MINT` after approval.

---

## Section 2. Comparison Pool Design — Fully Flexible, User-Driven

### 2.1 The five comparison modes

| Mode | User question | Focal set | Comparison set | Internal distance |
|---|---|---|---|---|
| **Pack size comparison** | "Is the new Mint Chip PUFF 4pk pulling from the Mint Chip PUFF 1ct?" | One specific flavor, one pack size | All other pack sizes of the same `specific_flavor_normalized`, same `parent_brand` | 1 |
| **Same flavor, any brand** | "Is a competitor's Mint Chip bar pulling from BUILT Mint Chip PUFF?" | One BUILT specific flavor | Same `specific_flavor_normalized`, different `parent_brand` | 2 |
| **Cross-flavor, BUILT only** | "Is Mint Chip pulling from Mint Brownie within BUILT's CHOCOLATE MINT group?" | One BUILT specific flavor | Other BUILT `specific_flavor_normalized` values under the same `spins_flavor` | 3 |
| **Cross-flavor, all brands** | "Are THINK! or PERFECT BAR CHOCOLATE MINT items competing with BUILT?" | One or more BUILT SKUs | Same `spins_flavor`, different `parent_brand` | 4 |
| **Full competitive** | "How is BUILT performing against BAREBELLS or QUEST overall?" | One or more BUILT SKUs | Any competitor brand(s) or SKUs | 6 |

The internal `relationship_distance` integer (1–6) is a first-class ML feature
and backend column. It is never shown to the user as a number.

### 2.2 Comparison type taxonomy (internal — backend and ML only)

Every (focal_upc, candidate_upc, geography, week_end) pair carries one of six
`comparison_type` values and a corresponding `relationship_distance`. These are
internal identifiers stored in Druid and used by the ML pipeline. The UI maps
them to plain-English labels at render time (see Section 2.4).

| comparison_type | relationship_distance | Definition |
|---|---|---|
| `SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER` | 1 | Same parent brand + same `specific_flavor_normalized` + different `pack_count`. |
| `SAME_SPECIFIC_FLAVOR_CROSS_BRAND` | 2 | Same `specific_flavor_normalized`, different parent brand. |
| `SAME_FLAVOR_SAME_BRAND` | 3 | Same parent brand + same `spins_flavor`, different `specific_flavor_normalized`. |
| `SAME_FLAVOR_CROSS_BRAND` | 4 | Same `spins_flavor`, different parent brand. |
| `CROSS_FLAVOR_SAME_BRAND` | 5 | Different `spins_flavor`, same parent brand. |
| `CROSS_FLAVOR_CROSS_BRAND` | 6 | Different `spins_flavor`, different parent brand. On-demand only via Query 2b. |

### 2.3 How relationship_distance drives the ML model

`relationship_distance` is a first-class ML feature, not just a filter.
It encodes the prior substitution probability structurally:

- **Distance 1 (pack size comparison):** Most direct substitution possible. A shopper
  switching from 1ct to 4pk of the exact same item. The model needs minimal additional
  evidence to score this as cannibalizing.
- **Distance 2 (same flavor, any brand):** Strong substitution signal, modulated by
  brand loyalty and price-per-unit differences.
- **Distance 3–4 (cross-flavor):** Weaker structural prior; the model relies more
  heavily on metric signals (base units deltas, velocity divergence) than on the
  relationship itself.
- **Distance 5–6:** Model's prior is essentially neutral — metric evidence is the
  only signal that matters.

A single trained model handles all five modes correctly without mode-specific
thresholds or separate model versions.

### 2.4 User-facing label mapping (v5)

This table is the single source of truth for every place the UI renders a
comparison pool description. Backend `comparison_type` enum values are unchanged.
Only the strings shown in the browser change.

| Internal `comparison_type` | Internal `relationship_distance` | UI plain-English label | Where used |
|---|---|---|---|
| `SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER` | 1 | **Pack size comparison** | Focal pill, context bar, scope bar, event card badge, modal step 2, provenance panel |
| `SAME_SPECIFIC_FLAVOR_CROSS_BRAND` | 2 | **Same flavor · any brand** | Context bar, scope bar, modal step 2 |
| `SAME_FLAVOR_SAME_BRAND` | 3 | **Cross-flavor · BUILT only** | Context bar, scope bar, event card badge ("Cross-flavor (BUILT portfolio)"), cross-flavor screen dist strip, modal step 2 |
| `SAME_FLAVOR_CROSS_BRAND` | 4 | **Cross-flavor · all brands** | Context bar, scope bar, modal step 2 |
| `CROSS_FLAVOR_SAME_BRAND` | 5 | **Other BUILT FLAVOR groups** | Modal step 2 dist strip |
| `CROSS_FLAVOR_CROSS_BRAND` | 6 | **Full competitive · on-demand** | Context bar, scope bar ("Full competitive — all brands, all FLAVOR groups"), modal step 2 |

**`comparison_scope_label` column in `scored_cannibalization`** must store the
plain-English string from the table above, not the enum value. The enum value
is stored separately in `comparison_type`. Both columns are required. The context
bar reads `comparison_scope_label` directly; the event card badge is derived from
`comparison_type` at render time using this table.

**Event card badges (Priority Events landing page):**

| `comparison_type` | Badge text rendered on event card |
|---|---|
| `SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER` | Pack size comparison |
| `SAME_FLAVOR_SAME_BRAND` | Cross-flavor (BUILT portfolio) |
| `SAME_FLAVOR_CROSS_BRAND` | Cross-flavor (any brand) |
| `SAME_SPECIFIC_FLAVOR_CROSS_BRAND` | Same flavor · cross-brand |
| `CROSS_FLAVOR_SAME_BRAND` | Other BUILT FLAVOR groups |
| `CROSS_FLAVOR_CROSS_BRAND` | Full competitive |

**Scope bar `scope-bar-value` text (by screen):**

| Screen | `scope-bar-value` text |
|---|---|
| Pack ladder | Pack size comparison — same flavor, same brand |
| Cross-flavor | Cross-flavor comparison — same FLAVOR group, BUILT only |
| Competitive | Full competitive — all brands, all FLAVOR groups |

**Geography and Action screen Channel / Outlet column:** The column header
is `Channel / Outlet` on both screens. Row values are the literal SPINS
`Channel/Outlet` field values: `CONVENTIONAL|FOOD`, `CONVENTIONAL|MULTI OUTLET`,
`CONVENTIONAL|CONVENIENCE`, `CONVENTIONAL|MASS MERCH`. The old derived labels
("Grocery", "Club", "Convenience") are retired from these screens.

### 2.5 User-selectable focal and comparison sets in the UI

**Step 1 — Focal item selection**
The user selects a focal SKU from a SPINS `FLAVOR` accordion with search.
Accordion headers are the exact `spins_flavor` values from the flavor mapping
join — these are the literal SPINS `FLAVOR` strings (e.g. `CHOCOLATE MINT`,
`BROWNIE`, `CARAMEL`, `COCONUT`, `COOKIE DOUGH`, `COOKIES AND CREAM`,
`STRAWBERRY`, `PEANUT BUTTER`). Invented category names such as
"CARAMEL & VANILLA" are not used.

**Step 2 — Comparison set selection**
Five scope options presented as radio buttons with plain-English labels:

```
[ Pack sizes of this flavor only ]       → internal distance = 1
[ Same flavor, any brand ]               → internal distance ≤ 2
[ Same FLAVOR group, BUILT only ]        → internal distance = 3
[ Same FLAVOR group, all brands ]        → internal distance ≤ 4
[ Specific competitor brand(s) ]         → Query 2b on-demand (distance 6)
```

The `data-scope` attribute on each option button still holds the numeric value
(1–6) so the JS `scopeDistances` map resolves the correct plain-English label.
No numeric distance is shown in the browser.

**Step 3 — Scope and filters**
Six filter dimensions, each rendered as a dropdown. All values come directly
from SPINS — no inference or parsing required.

| Filter | Options | Default |
|---|---|---|
| Channel / Outlet | All / CONVENTIONAL\|FOOD / CONVENTIONAL\|MULTI OUTLET / CONVENTIONAL\|CONVENIENCE / CONVENTIONAL\|MASS MERCH / CONVENTIONAL\|MILITARY | All |
| Retail Account | All / SOUTHEASTERN GROCERS / KROGER / ALBERTSONS COMPANIES / AHOLD DELHAIZE / PUBLIX / MEIJER / HY-VEE / GIANT EAGLE / WAKEFERN / WEGMANS / SPARTANNASH / SAVE MART / DEMOULAS / DIERBERGS / BIG Y / K-VA-T / WALMART / TARGET / BJS / SAMS / WALGREENS BOOTS ALLIANCE / CVS / CIRCLE K / EG GROUP / MAPCO / UNFI / ASSOCIATED WHOLESALE GROCERS / DECA | All |
| Geography Level | All / RMA / CRMA | All |
| Geography | SPINS geography values grouped by Channel/Outlet and Geography Level | All |
| Window | 4 weeks vs prior 4 / 13 weeks vs prior 13 / 26 weeks vs prior 26 / YTD vs prior YTD | 13 vs 13 |
| Confidence floor | High only / Medium + High / All (includes Low) | Medium + High |

**CONVENTIONAL|MILITARY excluded from scoring.** `DECA CONUS` panels are
excluded at both the filter layer (shown as greyed-out / labelled "excluded
from scoring" in the geography dropdown) and the query layer
(`channel_outlet != 'CONVENTIONAL|MILITARY'` in every scoring query).

**Context bar** (rendered below the topbar at all times):

```
Focal: [focal_description] · Pool: [comparison_scope_label] ·
Channel/Outlet: [channel_outlet] · Retail Account: [retail_account] ·
Geo Level: [geography_level] · Geography: [geography_display] ·
Window: [window_type_label]
```

All six values read from `scored_cannibalization` denormalized columns at
render time — no secondary join needed.

### 2.6 Known BUILT pack ladder structure (reference documentation)

Derived directly from `built_specific_flavor_mapping.csv`. The pipeline
discovers pairs dynamically — nothing is hard-coded.

#### 2.6a Multi-pack ladders (distance = 1 pairs exist within group)

| `brand_line` | `spins_flavor` | `specific_flavor_normalized` | Pack sizes |
|---|---|---|---|
| BUILT PUFF | BROWNIE | Brownie Batter | 1ct, 4pk, 8pk, 12pk |
| BUILT PUFF | CHOCOLATE MINT | Mint Chip | 1ct, 4pk, 12pk |
| BUILT PUFF | COCONUT | Coconut | 1ct, 4pk, 8pk, 12pk |
| BUILT PUFF | COOKIE DOUGH | Cookie Dough | 1ct, 4pk, 12pk |
| BUILT PUFF | COOKIES AND CREAM | Cookies N Cream | 1ct, 4pk, 12pk |
| BUILT PUFF | LEMON | Lemon Meringue Pie | 1ct, 4pk |
| BUILT PUFF | OTHER | Candy Cane Brownie | 1ct, 12pk |
| BUILT PUFF | OTHER | Churro | 1ct, 12pk |
| BUILT PUFF | STRAWBERRY | Strawberries N Cream | 1ct, 4pk, 12pk |
| BUILT BAR | CARAMEL | Salted Caramel | 1ct, 12pk |
| BUILT BAR | CHOCOLATE | Double Chocolate | 4pk, 12pk, 16pk |
| BUILT BAR | COCONUT | Coconut | 1ct, 12pk |
| BUILT BAR | COCONUT | Coconut Almond | 1ct, 18pk |
| BUILT BAR | COOKIES AND CREAM | Cookies and Cream | 1ct, 4pk |
| BUILT PUFF | CARAMEL | Salted Caramel | 4pk, 12pk |
| BUILT PUFF | BANANA | Banana Cream Pie | 1ct, 12pk |
| BUILT PUFF | CHOCOLATE NUT | Chocolatey Hazelnut | 1ct, 12pk |

**Cross-brand-line pack ladder notes:**
- `CARAMEL / Salted Caramel`: BUILT PUFF (4pk, 12pk) + BUILT BAR (1ct, 12pk)
  share `parent_brand = BUILT` and `specific_flavor_normalized = Salted Caramel`.
  All four-way pairs are distance-1. Different `brand_line` does not prevent
  pack-size pairing — `parent_brand` is the brand-identity test, not `brand_line`.
- `COCONUT / Coconut`: Similarly, BUILT PUFF (1ct, 4pk, 8pk, 12pk) and BUILT BAR
  (1ct, 12pk) are all distance-1 candidates.
- `PEANUT BUTTER`: BUILT PUFF 1ct + legacy BUILT 12pk are distance-1.
  `Peanut Butter Cookie` (1ct) and `Peanut Butter Cup` (4pk) are different
  `specific_flavor_normalized` values — they are distance-3 relative to plain
  `Peanut Butter`, not distance-1.

#### 2.6b Single-pack entries (no distance-1 partner in catalog)

These SKUs participate in distance 3–5 cross-flavor comparisons and become
distance-1 candidates when new pack sizes are auto-detected.

Selected entries: Grasshopper Cookie BAR 1ct (CHOCOLATE MINT), Mint Brownie BAR
1ct (CHOCOLATE MINT), Double Chocolate Fudge BAR 1ct (CHOCOLATE), Salted Caramel
Chocolate BAR 18pk (CARAMEL), plus all BUILT SOUR PUFF SKUs (APPLE, BLUE RASPBERRY,
LEMON, PEACH flavor groups). Full inventory in the flavor mapping CSV.

### 2.7 Competitive universe

63 brands available via Query 2b. Tier classification from `item_catalog`
controls display order on the Competitive screen (Tier 1 first). See Section 1
for tier membership lists. Tier is metadata only — never a filter.

---

## Section 3. Druid Query Plan

The 95M raw rows must never be passed to the ML pipeline directly.
Druid aggregates to feature vectors first. The earlier Q0–Q9 plan remains the
conceptual flow; Section 13 contains the implementation-ready SQL/Python build
sequence for the client Azure/Aevah deployment.

---

### Query 0 — Category extract normalization

**Purpose:** Normalize raw SPINS extract to snake_case, narrow to BUILT brand
+ same-subcategory competitor rows.

```sql
SELECT
  TIME_PARSE("Time Period End Date")   AS week_end,
  "Channel/Outlet"                     AS channel_outlet,
  "Geography Level"                    AS geography_level,
  "Retail Account"                     AS retail_account,
  "Retail Account Level"               AS retail_account_level,
  "Geography"                          AS geography_raw,
  "Department"                         AS department,
  "Category"                           AS category,
  "Subcategory"                        AS subcategory,
  "UPC",
  "Description",
  "Brand"                              AS source_brand,
  "PACK COUNT"                         AS pack_count,
  "FLAVOR"                             AS spins_flavor,
  "NFP - PROTEIN"                      AS nfp_protein,
  "NFP RANGES - PROTEIN VALUE"         AS nfp_protein_range,
  "NFP - SUGARS"                       AS nfp_sugars,
  "NFP - CALORIES"                     AS nfp_calories,
  "STORAGE"                            AS storage,
  "UNIT OF MEASURE"                    AS unit_of_measure,
  "Units",
  "Units, Yago"                        AS units_yago,
  "Base Units"                         AS base_units,
  "Base Units, Yago"                   AS base_units_yago,
  "Dollars",
  "Base Dollars"                       AS base_dollars,
  "TDP",
  "TDP, Yago"                          AS tdp_yago,
  "Average Weekly TDP"                 AS avg_weekly_tdp,
  "Max % ACV"                          AS max_acv,
  "Avg % ACV"                          AS avg_acv,
  "# of Stores"                        AS store_count,
  "# of Stores Selling"                AS stores_selling,
  "% of Stores Selling"                AS pct_stores_selling,
  "Average Weekly Units SPM"           AS avg_weekly_units_spm,
  "Average Weekly Units Per Store Selling Per Item"
                                       AS avg_weekly_units_per_store_selling_per_item,
  "Units SPM Per Item"                 AS units_spm_per_item,
  "ARP",
  "ARP, Yago"                          AS arp_yago,
  "Base ARP"                           AS base_arp,
  "ARP % Discount, Any Promo"          AS arp_pct_discount_any_promo,
  "Units, Promo"                       AS units_promo,
  "Units, Non-Promo"                   AS units_non_promo,
  "Units, % Promo"                     AS units_pct_promo,
  "TDP, Any Promo"                     AS tdp_any_promo,
  "TDP, Non-Promo"                     AS tdp_non_promo,
  "Promo Weeks"                        AS promo_weeks,
  "Incr Units"                         AS incr_units,
  "Incr Dollars"                       AS incr_dollars,
  "Units ,% Lift, TPR"                 AS units_lift_tpr,
  "Units ,% Lift, Any Display"         AS units_lift_any_display,
  "Units ,% Lift, Any Feature"         AS units_lift_any_feature,
  "First Week Selling"                 AS first_week_selling,
  "Number of Weeks Selling"            AS number_of_weeks_selling
FROM spins_weekly_pos
WHERE
  "Brand" IN ('BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF', 'BUILT')
  OR "Subcategory" = 'WELLNESS & NUTRITION BARS'
```

**Output table:** `built_filtered_weekly`

---

### Query 1 — Enriched weekly base table

**Purpose:** Join filtered weekly data against the flavor mapping to attach
`parent_brand`, `brand_line`, `spins_flavor`, `specific_flavor_normalized`,
`pack_count`, and `size_oz`. No geography parser is required — `channel_outlet`,
`geography_level`, `retail_account`, `retail_account_level`, and `geography_raw`
come directly from SPINS. `channel` is an alias for `channel_outlet`;
`geography_display` is an alias for `geography_raw`.

**Military exclusion:** Applied in all downstream scoring queries as
`channel_outlet != 'CONVENTIONAL|MILITARY'` and `retail_account != 'DECA'`.

**`Units/TDP` is never computed** in Query 1 or any downstream query. The
metric shortlist explicitly flags it as "Avoid in Final UX". Velocity is always
`avg_weekly_units_spm` or `avg_weekly_units_per_store_selling_per_item`.

**Output table:** `built_enriched_weekly`

---

### Query 2 — Universal comparison pool (distances 1–5, pre-built)

**Purpose:** Build every valid (focal_upc, candidate_upc) pair across all
comparison modes in a single self-join pass. `comparison_type` and
`relationship_distance` are internal backend columns — the UI maps them to
plain-English labels at render time per Section 2.4. This query is unchanged
from v4; the SQL enum strings are not renamed.

```sql
SELECT
  f.week_end,
  f.geography_raw,
  f.geography_display,
  f.geography_level,
  f.channel_outlet,
  f.channel,
  f.retail_account,
  f.retail_account_level,

  -- Focal item
  f.upc                               AS focal_upc,
  f.parent_brand                      AS focal_brand,
  f.brand_line                        AS focal_brand_line,
  f.description                       AS focal_description,
  f.specific_flavor_normalized        AS focal_flavor,
  f.spins_flavor                      AS focal_spins_flavor,
  f.pack_count                        AS focal_pack_count,
  f.size_oz                           AS focal_size_oz,

  -- Candidate item
  c.upc                               AS candidate_upc,
  c.parent_brand                      AS candidate_brand,
  c.brand_line                        AS candidate_brand_line,
  c.description                       AS candidate_description,
  c.specific_flavor_normalized        AS candidate_flavor,
  c.spins_flavor                      AS candidate_spins_flavor,
  c.pack_count                        AS candidate_pack_count,
  c.size_oz                           AS candidate_size_oz,

  -- Internal relationship classification (backend / ML only; not shown in UI as enum)
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand AND f.pack_count != c.pack_count
      THEN 'SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER'
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand != c.parent_brand
      THEN 'SAME_SPECIFIC_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized
      THEN 'SAME_FLAVOR_SAME_BRAND'
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand != c.parent_brand
      THEN 'SAME_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor != c.spins_flavor AND f.parent_brand = c.parent_brand
      THEN 'CROSS_FLAVOR_SAME_BRAND'
    ELSE 'CROSS_FLAVOR_CROSS_BRAND'
  END AS comparison_type,

  -- Internal relationship distance (ML feature; never shown as a number in UI)
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand AND f.pack_count != c.pack_count THEN 1
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand != c.parent_brand THEN 2
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized THEN 3
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand != c.parent_brand THEN 4
    WHEN f.spins_flavor != c.spins_flavor AND f.parent_brand = c.parent_brand THEN 5
    ELSE 6
  END AS relationship_distance,

  -- Pack size gap (used internally as ML feature; displayed in UI as
  -- "Pack size gap (Xct → Ypk)" never as a raw integer)
  CASE
    WHEN f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized = c.specific_flavor_normalized
      THEN ABS(f.pack_count - c.pack_count)
    ELSE NULL
  END AS pack_distance,

  -- Price-per-unit ratio (controls for value differences across pack formats)
  CASE
    WHEN c.pack_count > 0 AND f.pack_count > 0
      THEN (f.arp / NULLIF(f.pack_count, 0))
         / NULLIF((c.arp / NULLIF(c.pack_count, 0)), 0)
    ELSE NULL
  END AS price_per_unit_ratio,

  -- Candidate weekly metrics
  c.base_units                        AS candidate_base_units,
  c.units                             AS candidate_units,
  c.tdp                               AS candidate_tdp,
  c.avg_weekly_units_spm              AS candidate_velocity_spm,
  c.avg_weekly_units_per_store_selling_per_item
                                      AS candidate_velocity_store_selling,
  c.arp                               AS candidate_arp,
  c.store_count                       AS candidate_store_count,
  c.stores_selling                    AS candidate_stores_selling,
  c.pct_stores_selling                AS candidate_pct_stores_selling,
  c.tdp_any_promo                     AS candidate_tdp_any_promo,
  c.tdp_non_promo                     AS candidate_tdp_non_promo,
  c.promo_weeks                       AS candidate_promo_weeks,
  c.units_pct_promo                   AS candidate_units_pct_promo,
  c.arp_pct_discount_any_promo        AS candidate_arp_discount_any_promo,
  c.units_lift_tpr                    AS candidate_units_lift_tpr,
  c.units_lift_any_display            AS candidate_units_lift_any_display,
  c.units_lift_any_feature            AS candidate_units_lift_any_feature,
  c.first_week_selling                AS candidate_first_week_selling,
  c.incr_units                        AS candidate_incr_units,
  ic.competitor_tier                  AS candidate_competitor_tier

FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON  f.week_end = c.week_end
  AND f.geography_raw = c.geography_raw
  AND f.retail_account = c.retail_account
  AND f.channel_outlet = c.channel_outlet
  AND f.upc != c.upc
  AND (
    f.specific_flavor_normalized = c.specific_flavor_normalized
    OR f.spins_flavor = c.spins_flavor
    OR (f.parent_brand = c.parent_brand AND f.parent_brand = 'BUILT')
  )
LEFT JOIN item_catalog ic ON c.upc = ic.upc
WHERE
  (f.parent_brand = 'BUILT' OR c.parent_brand = 'BUILT')
  AND f.channel_outlet != 'CONVENTIONAL|MILITARY'
  AND f.retail_account != 'DECA'
```

**Output table:** `comparison_pool_weekly`

Dist 1–5 pairs are pre-built. Dist 6 (cross-FLAVOR competitive) is on-demand
via Query 2b — too large to pre-materialize across 63 brands × all geographies.

---

### Query 2b — On-demand competitive pool (distance 6, user-triggered)

Parameterized by `focal_upc`, `competitor_brand`, `retail_account`,
`channel_outlet`, `window_weeks`. Results sorted by `competitor_tier` ASC
(Tier 1 first). The UI scope bar for the Competitive screen reads
"Full competitive — all brands, all FLAVOR groups" from `comparison_scope_label`;
the `comparison_type = 'CROSS_FLAVOR_CROSS_BRAND'` enum is stored internally.

---

### Query 2c — Cross-flavor heatmap aggregation

Powers the geography × SKU heatmap on the Cross-flavor screen. Returns
`base_units_pct_chg` and a `heatmap_bucket` for each (SKU, geography) cell.
Parameterized by `spins_flavor`, `channel_outlet`, `retail_account`,
`window_type`. Runs at render time against `built_prepost_features` — not
pre-materialized. The scope bar on the cross-flavor screen reads "Cross-flavor
comparison — same FLAVOR group, BUILT only".

Five heatmap buckets match CSS class names:
`hm-strong-neg` (< −10%), `hm-mild-neg` (−10% to −3%), `hm-neutral` (−3% to
+3%), `hm-mild-pos` (+3% to +10%), `hm-strong-pos` (> +10%).

---

### Query 2d — Scope bar metadata

Lightweight aggregate against `comparison_pool_weekly`. Returns `comparison_type`,
`relationship_distance`, `pool_sku_count`, and `pool_sku_names` for the active
focal × geography × comparison type selection. The UI uses `pool_sku_count` and
`pool_sku_names` to populate the `scope-bar-dist` slot; the `scope-bar-value`
slot reads the plain-English label from Section 2.4, not the raw `comparison_type`
enum.

---

### Query 3 — Pre/post window aggregation

**Purpose:** For each focal SKU, compute before/after metrics across all four
window sizes (4w, 13w, 26w, YTD) in a single CASE WHEN pass. The `window_type`
column groups results; the UI filters at render time. YTD is anchored to
January 1 of the current year. All velocity columns use the `_spm` suffix
throughout; `Units/TDP` is never computed.

Key output columns: `pre_base_units`, `post_base_units`, `pre_avg_tdp`,
`post_avg_tdp`, `pre_avg_velocity_spm`, `post_avg_velocity_spm`,
`pre_avg_velocity_store_selling`, `post_avg_velocity_store_selling`,
`pre_pct_stores_selling`, `post_pct_stores_selling`, `pre_avg_arp`,
`post_avg_arp`, `pre_promo_weeks`, `post_promo_weeks`, `pre_weeks_count`,
`post_weeks_count`, `pre_units_pct_promo`, `post_units_pct_promo`,
`pre_arp_discount_any_promo`, `post_arp_discount_any_promo`,
`channel_outlet`, `retail_account`, `geography_level`, `window_type`.

**Output table:** `built_prepost_features`

---

### Query 4 — Donor pre/post aggregation

Same window logic as Query 3 applied to each donor SKU, keyed to the focal
SKU's `first_week_selling`. `window_type` grouping column matches Query 3.
All velocity columns use `_spm` suffix. `pre_promo_weeks` and `post_promo_weeks`
included for the donor side — needed by the Pre/post screen's donor cards.

**Output table:** `donor_prepost_features`

---

### Query 5 — Final ML feature table assembly

Joins focal and donor pre/post features; computes all derived change signals.
One row = one (focal_upc, donor_upc, geography, window_type) training example.

Key derived features: `focal_base_units_pct_chg`, `donor_base_units_pct_chg`,
`base_units_delta_diff`, `focal_tdp_pct_chg`, `focal_velocity_spm_pct_chg`,
`donor_velocity_spm_pct_chg`, `velocity_spm_delta_diff`, `focal_arp_pct_chg`,
`focal_promo_week_delta`, `donor_promo_week_delta`, `promo_confounded`,
`pack_distance`, `focal_price_per_unit`, `incremental_share`.

**`pack_distance`** (the absolute difference in pack count between focal and
donor) is a first-class ML feature. In the UI it is described as "Pack size
gap" with the specific values spelled out (e.g. "Pack size gap (1ct → 4pk)"),
never as a raw integer.

**`incremental_share`** is computed deterministically as focal base unit gain
divided by (focal gain + absolute donor loss), clamped to [0, 1]. It is stored
in `scored_cannibalization` for the second score bar on the SKU Summary screen.
It is not a training target.

**Deterministic label construction:**

| Label | Rule |
|---|---|
| `CANNIBALIZING` | Donor base units fell > 10% AND focal base units rose > 3% |
| `WATCH` | Donor base units fell 3–10% AND focal base units positive |
| `INCREMENTAL` | Donor base units flat or positive (≤ −3% change) |
| `NEUTRAL` | Insufficient evidence — excluded from training |

**`Units/TDP` is not computed anywhere in this query.** `focal_post_velocity_per_tdp`
(present in v1) was removed; velocity is `avg_weekly_units_spm` throughout.

**Output table:** `ml_training_features`

---

### Query 6 — Rolling stats + z-scores (event detection)

Rolling 4-week and 8-week averages, standard deviations, z-scores, and
week-over-week deltas for `base_units`, `avg_weekly_units_spm`, and `tdp`.
Win/loss matrix in Pool Health screen shows `0` when `rolling_8w_stddev_base_units`
is NULL (fewer than 8 prior weeks of data).

**Output table:** `event_detection_weekly`

---

### Query 7 — New UPC detection

Anti-join of current-week BUILT UPCs against all prior weeks.
**Output table:** `new_upc_candidates`

---

### Query 8 — New UPC classification

Classifies new UPCs as `NEW_PACK_SIZE`, `NEW_FLAVOR_CANDIDATE`, or
`DUPLICATE_OR_RELAUNCH`.
**Output table:** `new_upc_classifications`

---

### Query 9 — Ramp monitoring

Covers all BUILT SKUs in their first 16 weeks post-launch. Computes
`weeks_since_launch`, `peak_tdp`, `rolling_4w_avg_velocity_spm`,
`distribution_trend` (RAMPING / STABLE / DECLINING), `scoring_status`, and
`underperforming_flag` directly in Druid SQL.

`scoring_status` values and their UI meaning:

| Weeks since launch | `scoring_status` | UI badge | UI ramp ribbon |
|---|---|---|---|
| 1–6 | `SUPPRESSED` | Ramp · no score | "RAMP WEEK N of 13 · Cannibalization scoring suppressed" |
| 7–8 | `LOW_CONFIDENCE` | Active · Low confidence | "RAMP WEEK N of 13 · Early signal · Low confidence" |
| 9–12 | `ACTIVE` | Active | "RAMP WEEK N of 13 · Signal maturing" |
| 13+ | `ACTIVE` | Standard badge | "RAMP WEEK N of 13 · Scoring fully active" |

`underperforming_flag = TRUE` fires the "Launch underperforming" event when
`weeks_since_launch ≥ 6` AND `velocity_vs_4w_avg_ratio < 0.85` AND
`distribution_trend IN ('STABLE', 'DECLINING')`.

**Output table:** `new_product_ramp_monitor`

---

## Section 4. Label Construction

Labels are constructed deterministically — no ground truth exists in SPINS.

### Primary label: `cannibalization_status`

| Label | Rule |
|---|---|
| `CANNIBALIZING` | Donor base units fell > 10% AND focal base units rose > 3% in same window |
| `WATCH` | Donor base units fell 3–10% AND focal base units positive |
| `INCREMENTAL` | Donor base units flat or positive (≤ −3% change) regardless of focal |
| `NEUTRAL` | Insufficient evidence — suppressed from training; do not score |

### Secondary label: `demand_vs_distribution`

| Label | Rule |
|---|---|
| `DEMAND_LED` | Focal `avg_weekly_units_spm` rose alongside base units |
| `DISTRIBUTION_LED` | Focal TDP rose > 15% but focal `avg_weekly_units_spm` flat or fell |
| `MIXED` | Both changed but neither cleanly dominates |

### Label quality guardrails

- **Minimum weeks:** Both pre and post windows must have ≥ 8 non-null weeks
  (`pre_weeks_count`, `post_weeks_count`). Fewer → label `NEUTRAL`, exclude.
- **Promo contamination:** If donor `post_promo_weeks` increased > 2, or
  `post_units_pct_promo` rose sharply, or `post_arp_discount_any_promo` deepened
  > 5 points → `promo_confounded = TRUE`. Train in secondary pass only.
- **Ramp exclusion:** `scoring_status = 'SUPPRESSED'` (weeks 1–6) → excluded
  from training and scoring entirely. `LOW_CONFIDENCE` (weeks 7–8) → train with
  weight 0.5; scored with `cannibal_confidence = 'Low'`.
- **Pack size weighting:** Training examples weighted inversely by `pack_distance`.
  Closer pack sizes have stronger substitution priors.

---

## Section 5. ML Model Architecture

### Model 1 — Cannibalization risk classifier

**Type:** LightGBM binary classifier (CANNIBALIZING=1, INCREMENTAL+NEUTRAL=0)
**Output:** `cannibal_prob` (0.0–1.0), converted to Watch / Incremental / Cannibalizing

**Key features (in priority order):**

| Feature | Why it matters |
|---|---|
| `donor_base_units_pct_chg` | Primary signal — did the incumbent actually lose? |
| `focal_base_units_pct_chg` | Confirmation — did the focal actually gain? |
| `base_units_delta_diff` | Net transfer signal |
| `focal_tdp_pct_chg` | Distribution expansion confounder |
| `focal_pct_stores_selling_pct_chg` | Separates new doors from better selling in existing doors |
| `focal_velocity_spm_pct_chg` | Per-store demand signal — separates reach from pull |
| `donor_velocity_spm_pct_chg` | Donor productivity — did it also lose per-store? |
| `focal_velocity_store_selling_pct_chg` | Cleaner store-selling productivity signal |
| `donor_velocity_store_selling_pct_chg` | Donor productivity among stores actually selling |
| `velocity_spm_delta_diff` | Net productivity transfer |
| `pack_distance` | Pack size gap — closer sizes have higher substitution prior |
| `relationship_distance` | Structural substitution prior by comparison type (internal; 1–6) |
| `focal_price_per_unit` | Price-per-bar ratio across pack formats |
| `focal_post_promo_weeks` | Controls for promo-driven launch lift |
| `donor_post_promo_weeks` | Controls for donor promo defense activity |
| `focal_post_units_pct_promo` / `donor_post_units_pct_promo` | Promo-mix controls |
| `focal_post_arp_discount_any_promo` / `donor_post_arp_discount_any_promo` | Promo depth controls |
| `units_lift_tpr`, `units_lift_any_display`, `units_lift_any_feature` | Flags promo-driven movement |
| `base_units_yago_pct_chg`, `units_yago_pct_chg` | Seasonality / YAGO baseline controls |
| `channel_outlet`, `retail_account`, `geography_level` | Context features; prevents over-generalization |
| `focal_arp_pct_chg` | Price change as demand shift confound |
| `window_type` | Feature encoding for four window sizes |

`Units/TDP` is not used as a feature anywhere.

```python
import lightgbm as lgb

model_cannibal = lgb.LGBMClassifier(
    objective='binary',
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=63,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    min_child_samples=20,
    class_weight='balanced',
    random_state=42
)
model_cannibal.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)]
)
```

### Model 2 — Donor SKU ranker

**Type:** LightGBM LambdaRank. Groups by (focal_upc, geography). Ranks donors
by likelihood of being the primary demand source. Output surfaced in SKU Summary
screen as "Donor ranking by LambdaRank model."

```python
model_ranker = lgb.LGBMRanker(
    objective='lambdarank',
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    label_gain=[0, 1, 3, 7]
)
```

### Model 3 — Significant event detector

**Type:** LightGBM binary classifier. Determines whether a metric shift clears
both the statistical significance gate and the business rule gate. Output feeds
the Priority Events landing page.

---

## Section 6. Scoring Pipeline

### Scoring frequency
- Full rescore: weekly, after new SPINS data lands in Druid
- Partial rescore: on-demand per focal SKU when a user opens the tool

### Scored output schema: `scored_cannibalization`

**v5 change:** `comparison_scope_label` now stores plain-English labels from
Section 2.4, not "dist N" strings. `comparison_type` enum is unchanged.

```sql
CREATE TABLE scored_cannibalization (
  __time                              TIMESTAMP,
  focal_upc                           VARCHAR,
  focal_description                   VARCHAR,   -- denormalized for context bar
  geography                           VARCHAR,
  geography_display                   VARCHAR,   -- human-readable for context bar
  geography_level                     VARCHAR,   -- RMA / CRMA (direct from SPINS)
  retail_account                      VARCHAR,   -- direct from SPINS
  retail_account_level                VARCHAR,   -- e.g. TOTAL CORPORATE
  channel_outlet                      VARCHAR,   -- direct from SPINS, e.g. CONVENTIONAL|FOOD
  channel                             VARCHAR,   -- compatibility alias for channel_outlet
  specific_flavor_normalized          VARCHAR,
  spins_flavor                        VARCHAR,
  focal_pack_count                    INTEGER,
  window_type                         VARCHAR,   -- '4w' / '13w' / '26w' / 'ytd'
  comparison_type                     VARCHAR,   -- internal enum, e.g. SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER
  comparison_scope_label              VARCHAR,   -- plain-English UI label, e.g. 'Pack size comparison'
  relationship_distance               INTEGER,   -- internal ML feature (1–6); never shown as a number in UI
  cannibal_prob                       DOUBLE,
  cannibal_status                     VARCHAR,   -- Incremental / Watch / Cannibalizing
  cannibal_confidence                 VARCHAR,   -- High / Medium / Low
  incremental_share                   DOUBLE,    -- second score bar on SKU Summary
  demand_vs_dist                      VARCHAR,   -- Demand_Led / Distribution_Led / Mixed
  focal_pct_stores_selling_pct_chg    DOUBLE,
  focal_velocity_store_selling_pct_chg DOUBLE,
  donor_velocity_store_selling_pct_chg DOUBLE,
  focal_post_units_pct_promo          DOUBLE,
  donor_post_units_pct_promo          DOUBLE,
  focal_post_arp_discount_any_promo   DOUBLE,
  donor_post_arp_discount_any_promo   DOUBLE,
  donor_rank_1_upc                    VARCHAR,
  donor_rank_1_description            VARCHAR,   -- denormalized for donor chips
  donor_rank_2_upc                    VARCHAR,
  donor_rank_2_description            VARCHAR,
  significant_event                   BOOLEAN,
  event_label                         VARCHAR,
  p_value                             DOUBLE,    -- Provenance panel
  z_score_donor                       DOUBLE,    -- Provenance panel
  promo_confounded                    BOOLEAN,   -- Provenance panel
  scoring_status                      VARCHAR,   -- SUPPRESSED / LOW_CONFIDENCE / ACTIVE
  shap_feature_1                      VARCHAR,
  shap_value_1                        DOUBLE,
  shap_feature_2                      VARCHAR,
  shap_value_2                        DOUBLE,
  shap_feature_3                      VARCHAR,
  shap_value_3                        DOUBLE,
  model_version                       VARCHAR,
  scored_at                           TIMESTAMP
)
```

### Event queue schema: `event_queue`

```sql
CREATE TABLE event_queue (
  __time                TIMESTAMP,
  focal_upc             VARCHAR,
  focal_description     VARCHAR,
  geography             VARCHAR,
  geography_level       VARCHAR,
  retail_account        VARCHAR,
  channel_outlet        VARCHAR,   -- direct SPINS field
  event_type            VARCHAR,
  event_label           VARCHAR,
  confidence            VARCHAR,
  cannibal_prob         DOUBLE,
  cannibal_status       VARCHAR,
  comparison_type       VARCHAR,   -- internal enum; mapped to badge text at render
  relationship_distance INTEGER,   -- internal; used to derive badge text, not displayed as a number
  pct_change            DOUBLE,
  p_value               DOUBLE,
  z_score               DOUBLE,
  donor_upc             VARCHAR,
  donor_description     VARCHAR,
  shap_top_3            VARCHAR,   -- JSON array of [{feature, value}]
  scored_at             TIMESTAMP,
  model_version         VARCHAR
)
```

**`event_type` values and their UI rendering:**

| event_type | Event card title | Badge color | Relationship badge (from `comparison_type`) |
|---|---|---|---|
| `DEMAND_TRANSFER` | "Significant demand transfer detected" | Red | Pack size comparison |
| `LAUNCH_UNDERPERFORMING` | "Launch underperforming in [geo]" | Amber | — |
| `PACK_OVERLAP_RISK` | "Same-flavor pack overlap risk elevated" | Amber | Pack size comparison |
| `CROSS_FLAVOR_SIGNAL` | "Cross-flavor signal: [SKU] declining in [geo]" | Amber | Cross-flavor (BUILT portfolio) |
| `INCREMENTAL_CHANNEL` | "[Channel] is behaving incrementally" | Green | — |
| `FORECAST_RISK` | "Forecasted risk if [channel] expands broadly" | Blue | — |
| `NEW_PACK_SIZE` | Amber alert banner (not a card) | Amber banner | — |

**Relationship badge rendering rule:** The event card relationship badge is
derived from `comparison_type` at render time using the lookup table in
Section 2.4. It is never derived from `relationship_distance` as a number.
`NEW_PACK_SIZE`, `INCREMENTAL_CHANNEL`, `FORECAST_RISK`, and
`LAUNCH_UNDERPERFORMING` events do not show a relationship badge.

**`NEW_PACK_SIZE` banner text template:**
```
"New pack size auto-detected: [focal_description]"
"First seen [first_seen_week] · provisionally enrolled in pack size
monitoring · pending taxonomy review · cannibalization scoring active
at week 8"
```

---

## Section 7. SHAP Explainability

Every scored row carries its top-3 SHAP drivers. These populate the Explanation
screen driver bars and the Mo narrative template.

**v5 SHAP narrative template:**

```
"{focal_description} is flagged as {cannibal_status} in {geography} because
{shap_feature_1} changed by {shap_value_1_pct}% while {donor_description}
{donor_direction} over the same period. Pack size gap ({focal_pack}ct → {donor_pack}pk):
{substitution_read}. {promo_note}."
```

Where:
- `substitution_read`: "high substitution likelihood" if `pack_distance` ≤ 4, "low substitution likelihood" if > 4
- `promo_note`: "Promo weeks delta: +{n} — not confounded." if `promo_confounded = FALSE`, "Promo activity increased — interpret with caution." if `TRUE`

**Fixed Explanation screen driver rows (always shown regardless of SHAP rank):**

| Row | Feature label in UI | Tag style |
|---|---|---|
| Variable | `shap_feature_1` human-readable label | Depends on sign |
| Variable | `shap_feature_2` human-readable label | Depends on sign |
| Variable | `shap_feature_3` human-readable label | Depends on sign |
| Fixed | Pack size gap (Xct → Ypk) | Blue — structural prior |
| Fixed | Promo weeks delta | Gray if not confounded; amber if confounded |

```python
import shap

explainer = shap.TreeExplainer(model_cannibal)
shap_values = explainer.shap_values(X_score)

def top_shap_drivers(shap_row, feature_names, n=3):
    import numpy as np
    idx = np.argsort(np.abs(shap_row))[::-1][:n]
    return [(feature_names[i], float(shap_row[i])) for i in idx]
```

---

## Section 8. Data Quality Guardrails

### Minimum evidence thresholds before scoring

| Check | Threshold | Action if fails |
|---|---|---|
| Pre-window weeks (`pre_weeks_count`) | ≥ 8 | Label NEUTRAL, exclude from training |
| Post-window weeks (`post_weeks_count`) | ≥ 8 | Label NEUTRAL, exclude from training |
| Donor pre base units | > 0 | Exclude pair — donor not established |
| Focal TDP post | > 0 | Exclude — focal never distributed |
| Geography data coverage | ≥ 4 geographies per UPC | Flag as data-sparse |
| Ramp status | `scoring_status != 'SUPPRESSED'` | Exclude from scoring entirely |

### Confidence tiers

| Tier | Criteria |
|---|---|
| High | ≥ 12 pre-weeks, ≥ 10 post-weeks, ≥ 2 donors in pool, p < 0.05, `scoring_status = 'ACTIVE'` |
| Medium | 8–12 pre-weeks OR 1 donor OR p < 0.10 OR `scoring_status = 'LOW_CONFIDENCE'` |
| Low | < 8 weeks either window, or below significance threshold — analyst drill-down only |
| Suppressed | `scoring_status = 'SUPPRESSED'` — not scored, not shown |

**UI confidence floor filter:**
- "High only" → `cannibal_confidence = 'High'`
- "Medium + High" (default) → `cannibal_confidence IN ('High', 'Medium')`
- "All (includes Low)" → no confidence filter

---

## Section 9. Significant Event Detection & Outlier Flagging

### 9.1 Two-layer detection design

```
Layer 1: Statistical significance  →  did this metric shift more than noise?
Layer 2: Business rule thresholds  →  is the shift large enough to matter?
Both must fire                      →  event surfaced with confidence label
Either fires alone                  →  suppressed or downgraded to Low
```

### 9.2 Outlier detection (z-score method)

Z-score computed against 8-week rolling baseline in `event_detection_weekly`.

| Z-score | Classification | UI action |
|---|---|---|
| ≥ 3.0 or ≤ −3.0 | EXTREME_OUTLIER | Always surface if practical threshold also met |
| ≥ 2.0 or ≤ −2.0 | OUTLIER | Surface if corroborated by business rule |
| ≥ 1.5 or ≤ −1.5 | WATCH | Queue for monitoring, do not surface |
| < 1.5 | NORMAL | Suppress |

### 9.3 Statistical significance — Welch's t-test on windows

```python
from scipy import stats

def test_window_significance(pre_series, post_series,
                              practical_threshold_pct=0.05, alpha=0.10):
    if len(pre_series) < 4 or len(post_series) < 4:
        return {'significant': False, 'reason': 'INSUFFICIENT_WEEKS',
                'p_value': None, 'pct_change': None}
    t_stat, p_val = stats.ttest_ind(pre_series, post_series, equal_var=False)
    pct_chg = (post_series.mean() - pre_series.mean()) / (abs(pre_series.mean()) + 1e-9)
    return {
        'significant':  (p_val < alpha) and (abs(pct_chg) > practical_threshold_pct),
        'pct_change':   pct_chg,
        'p_value':      p_val,
        'direction':    'UP' if pct_chg > 0 else 'DOWN',
    }
```

### 9.4 Business rule thresholds by event type

| Event type | Statistical gate | Business rule gate |
|---|---|---|
| Demand transfer | Focal p < 0.10, donor p < 0.10 | Focal base units +3%, donor −10% |
| Launch underperforming | Focal p < 0.10 | TDP +15% AND velocity_spm −5% |
| Pack overlap risk | Donor p < 0.10 | Donor base units −5% in same specific flavor/geo |
| Distribution-led gain | TDP p < 0.10 | TDP +15%, base units +3%, velocity_spm flat/down |
| Cross-flavor signal | Distance-3/4 candidate p < 0.10 | Candidate base units −5% concurrent with focal launch |
| Velocity outlier | Velocity z ≥ 2.0 | velocity_spm deviation ≥ 25% from 8-week rolling avg |

### 9.5 Event assembly

```python
def assemble_events(scored_row, sig_result, outlier_result):
    # ... suppression logic (unchanged from v4) ...

    donor_pct_chg = scored_row.get('donor_base_units_pct_chg', 0)
    tdp_pct_chg   = scored_row.get('focal_tdp_pct_chg', 0)
    vel_pct_chg   = scored_row.get('focal_velocity_spm_pct_chg', 0)
    rel_dist      = scored_row.get('relationship_distance', 1)

    if donor_pct_chg < -0.10 and pct_chg > 0.03:
        event_label = 'Significant Demand Transfer Detected'
        event_type  = 'DEMAND_TRANSFER'
    elif tdp_pct_chg > 0.15 and vel_pct_chg < -0.03:
        event_label = 'Distribution-Led Gain Detected'
        event_type  = 'DEMAND_TRANSFER'
    elif donor_pct_chg < -0.05 and rel_dist in (3, 4):
        event_label = f'Cross-Flavor Signal: {scored_row.get("donor_description","?")} Declining'
        event_type  = 'CROSS_FLAVOR_SIGNAL'
    elif donor_pct_chg < -0.05:
        event_label = 'Pack Overlap Risk Elevated'
        event_type  = 'PACK_OVERLAP_RISK'
    elif pct_chg < -0.10 and tdp_pct_chg >= 0:
        event_label = 'Launch Underperforming in Geography'
        event_type  = 'LAUNCH_UNDERPERFORMING'
    elif abs(z_score) >= 2.0:
        event_label = 'Velocity Outlier Detected'
        event_type  = 'DEMAND_TRANSFER'
    else:
        event_label = 'Watch — Monitor Before Expanding'
        event_type  = 'PACK_OVERLAP_RISK'

    return {
        'focal_upc':           scored_row['focal_upc'],
        'focal_description':   scored_row['focal_description'],
        'geography':           scored_row['geography'],
        'event_type':          event_type,
        'event_label':         event_label,
        'confidence':          confidence,
        'cannibal_prob':       cannibal_prob,
        'cannibal_status':     scored_row['cannibal_status'],
        'comparison_type':     scored_row['comparison_type'],      # internal enum
        'relationship_distance': scored_row['relationship_distance'],  # internal int
        'pct_change':          pct_chg,
        'p_value':             sig_result['p_value'],
        'z_score':             z_score,
        'donor_upc':           scored_row.get('donor_rank_1_upc'),
        'donor_description':   scored_row.get('donor_rank_1_description'),
        'shap_top_3':          scored_row.get('shap_drivers'),
        'scored_at':           scored_row['scored_at'],
        'model_version':       scored_row['model_version']
    }
```

**Note:** `comparison_type` and `relationship_distance` are written to
`event_queue` as internal values. The UI badge text is derived at render time
using the lookup table in Section 2.4 — neither the enum string nor the
distance integer appears in the browser.

### 9.6 How events surface in the tool

```
event_type           →  Card border color (red/amber/green/blue)
event_label          →  Card title
geography            →  Card subtitle
focal_description    →  Focal SKU name (denormalized)
donor_description    →  Donor SKU name (denormalized)
confidence           →  Dot color + label (High / Medium)
cannibal_status      →  Status badge
comparison_type      →  Relationship badge text (via Section 2.4 lookup)
shap_top_3           →  Pre-populated into Explanation drawer on drill-down
p_value              →  Provenance panel "significance level"
z_score_donor        →  Provenance panel "deviation from baseline"
promo_confounded     →  Provenance panel "Promo confounded"
```

`NEW_PACK_SIZE` events render as a fixed amber banner above the event cards,
not as a scrollable card. Shown when any `NEW_PACK_SIZE` event exists with
`scored_at >= CURRENT_TIMESTAMP - 7 DAYS`.

---

## Section 10. New Product & New Pack Size Detection

### Confidence ladder by ramp week

| Weeks since launch | `scoring_status` | `cannibal_confidence` | UI badge | UI ramp ribbon |
|---|---|---|---|---|
| 1–6 | `SUPPRESSED` | n/a | Ramp · no score | "RAMP WEEK N of 13 · Cannibalization scoring suppressed" |
| 7–8 | `LOW_CONFIDENCE` | `Low` | Active · Low confidence | "RAMP WEEK N of 13 · Early signal · Low confidence" |
| 9–12 | `ACTIVE` | `Medium` (data-dependent) | Active | "RAMP WEEK N of 13 · Signal maturing" |
| 13+ | `ACTIVE` | `Medium` or `High` | Standard badge | "RAMP WEEK N of 13 · Scoring fully active" |

Ramp ribbon hides once `weeks_since_launch > 16`.

### Underperforming vs. still-ramping distinction

- **STABLE + declining velocity** (`distribution_trend = 'STABLE'`, `underperforming_flag = TRUE`): "Launch underperforming" fires. TDP has plateaued; velocity still falling — genuine demand weakness.
- **DECLINING distribution** (`distribution_trend = 'DECLINING'`, `underperforming_flag = TRUE`): TDP peaked and is now contracting. "Launch underperforming" fires with interpretation note: "TDP peaked at [peak_tdp], now declining."

### Auto-enrollment flow

New `NEW_PACK_SIZE` UPCs auto-enroll into `pack_ladder_pairs_weekly` with
`manual_review_needed = Y`. First scoring run uses shortened pre-window
(minimum 4 weeks available). `LOW_CONFIDENCE` for weeks 7–8; upgrades to
`Medium` at week 9 if data quality checks pass. The Priority Events banner
reads "provisionally enrolled in pack size monitoring" (not "pack ladder
monitoring" — the internal term for the user-facing concept).

---

## Section 11. Execution Order Summary

| Step | Query / Action | Output | Tool |
|---|---|---|---|
| 0 | Category extract normalization + BUILT/category filter | `built_filtered_weekly` | Druid SQL |
| 1 | Flavor/product enrichment; direct SPINS retail fields; no geo parser | `built_enriched_weekly` | Druid SQL + lookup |
| 2 | Comparison pair construction (distances 1–5, pre-built) | `comparison_pool_weekly` | Druid SQL self-join |
| 2b | On-demand competitive pairs (distance 6) | Returned to UI directly | Druid SQL parameterized |
| 2c | Cross-flavor heatmap aggregation | Returned to UI directly | Druid SQL parameterized |
| 2d | Scope bar metadata | Returned to UI directly | Druid SQL parameterized |
| 3 | Focal pre/post aggregation (4 windows) | `built_prepost_features` | Druid SQL |
| 4 | Donor pre/post aggregation (4 windows) | `donor_prepost_features` | Druid SQL |
| 5 | Feature table + labels + `incremental_share` | `ml_training_features` | Druid SQL or Spark |
| 6 | Rolling stats + z-scores | `event_detection_weekly` | Druid SQL (window fns) |
| 7 | New UPC detection | `new_upc_candidates` | Druid SQL |
| 8 | New UPC classification | `new_upc_classifications` | Druid SQL |
| 9 | Ramp monitoring + `scoring_status` | `new_product_ramp_monitor` | Druid SQL |
| 10 | Train cannibalization classifier | `model_cannibal_v5.pkl` | Python / LightGBM |
| 11 | Train donor ranker | `model_ranker_v5.pkl` | Python / LightGBM |
| 12 | Train event detector | `model_event_v5.pkl` | Python / LightGBM |
| 13 | Score all focal × retail account × geography × window pairs | `scored_cannibalization` | Python → Druid ingest |
| 14 | Assemble events + suppression + cross-flavor type | `event_queue` | Python → Druid ingest |
| 15 | Auto-enroll new pack sizes | `pack_ladder_pairs_weekly` update | Python |
| 16 | Write `NEW_PACK_SIZE` events to event queue | `event_queue` | Python → Druid ingest |
| 17 | Weekly rescore trigger | Incremental update | Druid supervisor task |

---

## Section 12. Key Design Decisions

**Why plain-English labels in the UI instead of "dist N" notation?**
The `relationship_distance` integer is a precise ML concept: it encodes the
prior substitution probability and is a direct input to the LightGBM model.
Exposing it as "dist 1", "dist 3", etc. in the browser forces users to learn
an internal taxonomy that adds no business value and creates confusion. The
plain-English labels ("Pack size comparison", "Cross-flavor (BUILT portfolio)")
communicate the same information in terms the user already understands. The
internal enum and integer are preserved in every Druid table, the ML feature
set, the scoring pipeline, and the event assembly logic — the change is purely
at the render layer.

**Why `Channel/Outlet` and literal SPINS values in the Geography and Action screens?**
Previous versions derived channel labels ("Grocery", "Club") from a knowledge-based
parser applied to geography strings. With the expanded SPINS extract, `Channel/Outlet`
is a direct source field — no inference needed. Using `CONVENTIONAL|FOOD` directly
eliminates a translation layer, makes the tool self-consistent with what analysts see
in SPINS exports, and removes the risk of mis-classification as the panel universe grows.

**Why SPM / store-selling velocity and never `Units/TDP`?**
The SPINS metric shortlist explicitly flags `Units/TDP` as "Avoid in Final UX"
because users confuse it with per-store productivity. `Units/TDP` is
distribution-point-normalized (a TDP counts ACV-weighted points, not stores).
`avg_weekly_units_spm` and `avg_weekly_units_per_store_selling_per_item` map
cleanly to "is each selling store actually moving more units?". The expanded
extract provides store-selling productivity directly.

**Why four window sizes pre-computed rather than on-demand?**
The modal filter exposes 4w, 13w, 26w, and YTD. If window-switching triggered
a new Druid scan, latency would break the interactive feel. Pre-computing all
four in a single CASE WHEN pass (Query 3) adds ~3× to the row count of
`built_prepost_features` (~30K–150K rows total) — trivially small.

**Why `incremental_share` as a scored output rather than a label?**
`incremental_share` depends on knowing both focal and donor outcomes
simultaneously, which is only available at score time, not at label construction
time for individual pairs. It is computed deterministically in Query 5 and stored
for the second score bar. High `cannibal_prob` + low `incremental_share` = strong
zero-sum transfer; high `cannibal_prob` + moderate `incremental_share` = partial
transfer with genuine new demand.

**Why cross-flavor signals (distance 3/4) surface on the Priority Events page?**
A distance-3 concurrent decline in the same geography during the focal SKU's
launch window is evidence of same-SPINS-FLAVOR cannibalization. Surfacing it at
Medium confidence (never High — the structural prior at distance 3 is weaker)
lets the user decide whether to investigate the Cross-flavor screen. The event
card badge says "Cross-flavor (BUILT portfolio)", not "dist 3".

**Why pre-build distance 3 pairs but not distance 6?**
Distance 3 (SAME_FLAVOR_SAME_BRAND) involves a bounded BUILT × BUILT set — at
most ~91 SKUs × ~91 SKUs, constrained by SPINS `FLAVOR`. Pre-building is cheap
and enables the heatmap query (Query 2c) to run against materialized data.
Distance 6 (CROSS_FLAVOR_CROSS_BRAND) would involve 63 competitor brands ×
all BUILT SKUs × all geographies — unacceptably large. Query 2b handles distance
6 on demand against the pre-filtered `built_enriched_weekly` table.

**Why `competitor_tier` in `item_catalog` rather than hard-coded in the UI?**
Tier classification controls display order on the Competitive screen. Hard-coding
creates a maintenance problem whenever a competitor enters or exits the category.
Storing in `item_catalog` means a single CSV update propagates everywhere.

**Why denormalize `focal_description`, `donor_rank_1_description`, and five
context bar fields into `scored_cannibalization`?**
The context bar and Priority Events cards need human-readable names without a
secondary join at render time. Denormalizing keeps every screen render to a
single table lookup.

**Why encode `scoring_status` in Druid (Query 9) rather than Python?**
Moving it into Query 9 makes `new_product_ramp_monitor` the single source of
truth for ramp state. The Python pipeline reads `scoring_status` from Druid
rather than recomputing it, eliminating the risk of Python and Druid disagreeing
about whether a SKU is in the suppression window.

---

## Section 13. Client Azure Implementation Appendix — Druid SQL, Python, and Pilot Upload Plan

This section supersedes any earlier shorthand query descriptions. It is written
for the client implementation conversation around storing SPINS data in Apache
Druid inside Aevah on the client's cloud.

### 13.1 Expanded SPINS extract contract

The current SPINS sample `All_items_extract_41926-h100.csv` has 214 columns.
The implementation must ingest the expanded field set, not the older narrow
extract. Treat the sample as the schema contract, not as a statistically useful
training file.

Minimum required source fields for v5/v10:

| Use | Required columns |
|---|---|
| Time grain | `Time Period End Date`, `Time Period` |
| Retail scope | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography` |
| Product identity | `Department`, `Category`, `Subcategory`, `Brand`, `UPC`, `Description`, `PACK COUNT`, `FLAVOR` |
| Distribution | `Avg % ACV`, `Max % ACV`, `TDP`, `Average Weekly TDP`, `# of Stores`, `# of Stores Selling`, `% of Stores Selling` |
| Demand / velocity | `Units`, `Base Units`, `Average Weekly Units SPM`, `Units SPM Per Item`, `Average Weekly Units Per Store Selling Per Item`, `Average Weekly Units per Store Selling` |
| Price | `Dollars`, `Base Dollars`, `ARP`, `Base ARP`, `ARP, Promo`, `ARP, Non-Promo`, `ARP % Discount, Any Promo` |
| Promo | `Units, Promo`, `Units, Non-Promo`, `Units, % Promo`, `TDP, Any Promo`, `TDP, Non-Promo`, `Promo Weeks`, lift and discount fields for TPR/display/feature/SPK |
| Baseline / seasonality | All `, Yago` companions, especially `Units, Yago`, `Base Units, Yago`, `TDP, Yago`, velocity Yago, price Yago, and promo Yago |
| Product attributes | `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `NFP - SUGARS`, `NFP - CALORIES`, `STORAGE`, `UNIT OF MEASURE` |

Avoid `Units/TDP` and `Dollars/TDP` in the final UX and model feature set.
They may be ingested for QA, but the production model should prefer store,
store-selling, and SPM velocity metrics.

### 13.2 Druid ingestion spec

Recommended datasource names:

| Datasource / lookup | Type | Purpose |
|---|---|---|
| `spins_weekly_pos_raw` | Druid datasource | Raw expanded SPINS weekly POS extract |
| `built_specific_flavor_mapping` | Lookup or small datasource | BUILT UPC to brand line, mapped FLAVOR, specific flavor, pack count |
| `flavor_canonical_overrides` | Lookup | Taxonomy-reviewed raw/mapped/canonical FLAVOR corrections |
| `item_catalog` | Lookup or small datasource | Competitor tier and product attributes |

Ingestion rules:

```json
{
  "type": "index_parallel",
  "spec": {
    "dataSchema": {
      "dataSource": "spins_weekly_pos_raw",
      "timestampSpec": {
        "column": "Time Period End Date",
        "format": "MM/dd/yyyy"
      },
      "dimensionsSpec": {
        "useSchemaDiscovery": true,
        "dimensionExclusions": []
      },
      "granularitySpec": {
        "type": "uniform",
        "segmentGranularity": "MONTH",
        "queryGranularity": "DAY",
        "rollup": false
      }
    },
    "ioConfig": {
      "type": "index_parallel",
      "inputSource": {
        "type": "azure",
        "uris": ["azure://<container>/<path>/spins/*.csv"]
      },
      "inputFormat": {
        "type": "csv",
        "findColumnsFromHeader": true
      }
    },
    "tuningConfig": {
      "type": "index_parallel",
      "maxRowsInMemory": 250000,
      "maxRowsPerSegment": 5000000
    }
  }
}
```

Post-ingestion smoke tests:

```sql
SELECT COUNT(*) AS row_count FROM spins_weekly_pos_raw;

SELECT
  MIN(__time) AS min_week,
  MAX(__time) AS max_week,
  COUNT(DISTINCT "UPC") AS upc_count,
  COUNT(DISTINCT "Retail Account") AS retail_account_count,
  COUNT(DISTINCT "Geography") AS geography_count
FROM spins_weekly_pos_raw;

SELECT
  "Channel/Outlet",
  "Geography Level",
  COUNT(*) AS rows
FROM spins_weekly_pos_raw
GROUP BY 1,2
ORDER BY rows DESC;
```

### 13.3 Druid SQL build sequence

Run these queries in order. In Druid, create each derived table with `REPLACE
INTO <table> OVERWRITE ALL SELECT ...` where supported. If the deployed Druid
version does not support SQL `REPLACE INTO`, use native ingestion tasks from each
query result.

#### Q0 — Normalize expanded SPINS fields

```sql
REPLACE INTO built_filtered_weekly OVERWRITE ALL
SELECT
  TIME_PARSE("Time Period End Date") AS __time,
  "Channel/Outlet" AS channel_outlet,
  "Geography Level" AS geography_level,
  "Retail Account" AS retail_account,
  "Retail Account Level" AS retail_account_level,
  "Geography" AS geography,
  "Time Period" AS time_period,
  "Department" AS department,
  "Category" AS category,
  "Subcategory" AS subcategory,
  "Brand" AS source_brand,
  "UPC" AS upc,
  "Description" AS description,
  CAST("PACK COUNT" AS BIGINT) AS source_pack_count,
  "FLAVOR" AS spins_flavor_raw,
  "NFP - PROTEIN" AS nfp_protein,
  "NFP RANGES - PROTEIN VALUE" AS nfp_protein_range,
  "NFP - SUGARS" AS nfp_sugars,
  "NFP - CALORIES" AS nfp_calories,
  "STORAGE" AS storage,
  "UNIT OF MEASURE" AS unit_of_measure,
  CAST("Units" AS DOUBLE) AS units,
  CAST("Units, Yago" AS DOUBLE) AS units_yago,
  CAST("Base Units" AS DOUBLE) AS base_units,
  CAST("Base Units, Yago" AS DOUBLE) AS base_units_yago,
  CAST("Dollars" AS DOUBLE) AS dollars,
  CAST("Base Dollars" AS DOUBLE) AS base_dollars,
  CAST("Avg % ACV" AS DOUBLE) AS avg_acv,
  CAST("Max % ACV" AS DOUBLE) AS max_acv,
  CAST("TDP" AS DOUBLE) AS tdp,
  CAST("TDP, Yago" AS DOUBLE) AS tdp_yago,
  CAST("Average Weekly TDP" AS DOUBLE) AS avg_weekly_tdp,
  CAST("# of Stores" AS DOUBLE) AS store_count,
  CAST("# of Stores Selling" AS DOUBLE) AS stores_selling,
  CAST("% of Stores Selling" AS DOUBLE) AS pct_stores_selling,
  CAST("Average Weekly Units SPM" AS DOUBLE) AS avg_weekly_units_spm,
  CAST("Units SPM Per Item" AS DOUBLE) AS units_spm_per_item,
  CAST("Average Weekly Units Per Store Selling Per Item" AS DOUBLE)
    AS avg_weekly_units_per_store_selling_per_item,
  CAST("Average Weekly Units per Store Selling" AS DOUBLE)
    AS avg_weekly_units_per_store_selling,
  CAST("ARP" AS DOUBLE) AS arp,
  CAST("ARP, Yago" AS DOUBLE) AS arp_yago,
  CAST("Base ARP" AS DOUBLE) AS base_arp,
  CAST("ARP % Discount, Any Promo" AS DOUBLE) AS arp_pct_discount_any_promo,
  CAST("Units, Promo" AS DOUBLE) AS units_promo,
  CAST("Units, Non-Promo" AS DOUBLE) AS units_non_promo,
  CAST("Units, % Promo" AS DOUBLE) AS units_pct_promo,
  CAST("TDP, Any Promo" AS DOUBLE) AS tdp_any_promo,
  CAST("TDP, Non-Promo" AS DOUBLE) AS tdp_non_promo,
  CAST("Promo Weeks" AS DOUBLE) AS promo_weeks,
  CAST("Base ARP, Promo" AS DOUBLE) AS base_arp_promo,
  CAST("ARP, Promo" AS DOUBLE) AS arp_promo,
  CAST("ARP, Non-Promo" AS DOUBLE) AS arp_non_promo,
  CAST("Incr Units" AS DOUBLE) AS incr_units,
  CAST("Incr Dollars" AS DOUBLE) AS incr_dollars,
  CAST("Units ,% Lift, TPR" AS DOUBLE) AS units_lift_tpr,
  CAST("Units ,% Lift, Any Display" AS DOUBLE) AS units_lift_any_display,
  CAST("Units ,% Lift, Any Feature" AS DOUBLE) AS units_lift_any_feature,
  "First Week Selling" AS first_week_selling,
  CAST("Number of Weeks Selling" AS BIGINT) AS number_of_weeks_selling
FROM spins_weekly_pos_raw
WHERE
  "Subcategory" = 'WELLNESS & NUTRITION BARS'
  OR "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF');
```

#### Q1 — Product enrichment and canonical FLAVOR

```sql
REPLACE INTO built_enriched_weekly OVERWRITE ALL
SELECT
  f.*,
  CASE
    WHEN f.source_brand IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
      THEN 'BUILT'
    ELSE f.source_brand
  END AS parent_brand,
  COALESCE(m.brand, f.source_brand) AS brand_line,
  m.flavor_family AS spins_flavor_mapped,
  COALESCE(o.spins_flavor_canonical, m.flavor_family, f.spins_flavor_raw)
    AS spins_flavor_canonical,
  COALESCE(o.spins_flavor_canonical, m.flavor_family, f.spins_flavor_raw)
    AS spins_flavor,
  COALESCE(m.specific_flavor_normalized, f.description) AS specific_flavor_normalized,
  COALESCE(CAST(m.pack_count AS BIGINT), f.source_pack_count) AS pack_count,
  CAST(m.size_oz AS DOUBLE) AS size_oz,
  CASE
    WHEN m.flavor_family IS NOT NULL
     AND o.spins_flavor_canonical IS NOT NULL
     AND m.flavor_family <> o.spins_flavor_canonical
      THEN 1 ELSE 0
  END AS taxonomy_override_flag,
  CASE
    WHEN f.channel_outlet = 'CONVENTIONAL|MILITARY' OR f.retail_account LIKE '%DECA%'
      THEN 1 ELSE 0
  END AS military_excluded_flag
FROM built_filtered_weekly f
LEFT JOIN built_specific_flavor_mapping m
  ON f.upc = m.upc
LEFT JOIN flavor_canonical_overrides o
  ON f.upc = o.upc;
```

#### Q2 — Comparison pair pool

```sql
REPLACE INTO comparison_pool_weekly OVERWRITE ALL
SELECT
  f.__time,
  f.upc AS focal_upc,
  f.description AS focal_description,
  f.parent_brand AS focal_parent_brand,
  f.brand_line AS focal_brand_line,
  f.spins_flavor AS focal_spins_flavor,
  f.specific_flavor_normalized AS focal_specific_flavor,
  f.pack_count AS focal_pack_count,
  c.upc AS candidate_upc,
  c.description AS candidate_description,
  c.parent_brand AS candidate_parent_brand,
  c.brand_line AS candidate_brand_line,
  c.spins_flavor AS candidate_spins_flavor,
  c.specific_flavor_normalized AS candidate_specific_flavor,
  c.pack_count AS candidate_pack_count,
  f.channel_outlet,
  f.retail_account,
  f.retail_account_level,
  f.geography_level,
  f.geography,
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand
     AND f.pack_count <> c.pack_count
      THEN 'SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER'
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand <> c.parent_brand
      THEN 'SAME_SPECIFIC_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor = c.spins_flavor
     AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized <> c.specific_flavor_normalized
      THEN 'SAME_FLAVOR_SAME_BRAND'
    WHEN f.spins_flavor = c.spins_flavor
     AND f.parent_brand <> c.parent_brand
      THEN 'SAME_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor <> c.spins_flavor
     AND f.parent_brand = c.parent_brand
      THEN 'CROSS_FLAVOR_SAME_BRAND'
    ELSE 'CROSS_FLAVOR_CROSS_BRAND'
  END AS comparison_type,
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand
     AND f.pack_count <> c.pack_count THEN 1
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand <> c.parent_brand THEN 2
    WHEN f.spins_flavor = c.spins_flavor
     AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized <> c.specific_flavor_normalized THEN 3
    WHEN f.spins_flavor = c.spins_flavor
     AND f.parent_brand <> c.parent_brand THEN 4
    WHEN f.spins_flavor <> c.spins_flavor
     AND f.parent_brand = c.parent_brand THEN 5
    ELSE 6
  END AS relationship_distance,
  CASE
    WHEN f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized = c.specific_flavor_normalized
      THEN ABS(f.pack_count - c.pack_count)
    ELSE NULL
  END AS pack_distance,
  f.base_units AS focal_base_units,
  c.base_units AS candidate_base_units,
  f.units AS focal_units,
  c.units AS candidate_units,
  f.tdp AS focal_tdp,
  c.tdp AS candidate_tdp,
  f.avg_weekly_units_spm AS focal_velocity_spm,
  c.avg_weekly_units_spm AS candidate_velocity_spm,
  f.arp AS focal_arp,
  c.arp AS candidate_arp,
  f.promo_weeks AS focal_promo_weeks,
  c.promo_weeks AS candidate_promo_weeks
FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON f.__time = c.__time
 AND f.channel_outlet = c.channel_outlet
 AND f.retail_account = c.retail_account
 AND f.geography = c.geography
 AND f.upc <> c.upc
WHERE
  (f.parent_brand = 'BUILT' OR c.parent_brand = 'BUILT')
  AND f.military_excluded_flag = 0
  AND c.military_excluded_flag = 0
  AND (
    f.specific_flavor_normalized = c.specific_flavor_normalized
    OR f.spins_flavor = c.spins_flavor
    OR (f.parent_brand = c.parent_brand AND f.parent_brand = 'BUILT')
  );
```

#### Q3 — Focal pre/post, prior-quarter, and YoY features

```sql
REPLACE INTO built_prepost_features OVERWRITE ALL
WITH anchors AS (
  SELECT
    upc AS focal_upc,
    MIN(__time) AS launch_week
  FROM built_enriched_weekly
  WHERE parent_brand = 'BUILT'
  GROUP BY 1
)
SELECT
  p.focal_upc,
  e.channel_outlet,
  e.retail_account,
  e.retail_account_level,
  e.geography_level,
  e.geography,
  w.window_type,
  SUM(CASE WHEN e.__time >= TIME_SHIFT(a.launch_week, 'P1W', -w.n_weeks)
            AND e.__time < a.launch_week THEN e.base_units ELSE 0 END) AS pre_base_units,
  SUM(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.base_units ELSE 0 END) AS post_base_units,
  SUM(CASE WHEN e.__time >= TIME_SHIFT(a.launch_week, 'P1W', -2*w.n_weeks)
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', -w.n_weeks) THEN e.base_units ELSE 0 END) AS prior_period_base_units,
  SUM(CASE WHEN e.__time >= TIME_SHIFT(a.launch_week, 'P1Y', -1)
            AND e.__time < TIME_SHIFT(TIME_SHIFT(a.launch_week, 'P1Y', -1), 'P1W', w.n_weeks) THEN e.base_units ELSE 0 END) AS yago_same_period_base_units,
  AVG(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.tdp END) AS post_avg_tdp,
  AVG(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.avg_weekly_units_spm END) AS post_avg_velocity_spm,
  AVG(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks)
           THEN e.avg_weekly_units_per_store_selling_per_item END) AS post_avg_store_selling_velocity,
  AVG(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.units_pct_promo END) AS post_units_pct_promo,
  SUM(CASE WHEN e.__time >= a.launch_week
            AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.promo_weeks ELSE 0 END) AS post_promo_weeks,
  COUNT(DISTINCT CASE WHEN e.__time >= TIME_SHIFT(a.launch_week, 'P1W', -w.n_weeks)
                       AND e.__time < a.launch_week THEN e.__time END) AS pre_weeks_count,
  COUNT(DISTINCT CASE WHEN e.__time >= a.launch_week
                       AND e.__time < TIME_SHIFT(a.launch_week, 'P1W', w.n_weeks) THEN e.__time END) AS post_weeks_count
FROM anchors a
JOIN built_enriched_weekly e ON a.focal_upc = e.upc
JOIN (
  SELECT '4w' AS window_type, 4 AS n_weeks UNION ALL
  SELECT '13w', 13 UNION ALL
  SELECT '26w', 26 UNION ALL
  SELECT 'ytd', 52
) w ON 1=1
JOIN (SELECT DISTINCT upc AS focal_upc FROM built_enriched_weekly WHERE parent_brand = 'BUILT') p
  ON p.focal_upc = a.focal_upc
GROUP BY 1,2,3,4,5,6,7;
```

#### Q4–Q9 — Feature, event, new UPC, and ramp tables

```sql
-- Q4 donor_prepost_features: same structure as Q3, keyed by
-- (focal_upc, candidate_upc, channel_outlet, retail_account, geography, window_type)
-- using comparison_pool_weekly and candidate metrics.

REPLACE INTO ml_training_features OVERWRITE ALL
SELECT
  p.focal_upc,
  p.candidate_upc AS donor_upc,
  p.channel_outlet,
  p.retail_account,
  p.geography_level,
  p.geography,
  f.window_type,
  p.comparison_type,
  p.relationship_distance,
  p.pack_distance,
  f.pre_base_units AS focal_pre_base_units,
  f.post_base_units AS focal_post_base_units,
  d.pre_base_units AS donor_pre_base_units,
  d.post_base_units AS donor_post_base_units,
  (f.post_base_units - f.pre_base_units) / NULLIF(ABS(f.pre_base_units), 0) AS focal_base_units_pct_chg,
  (d.post_base_units - d.pre_base_units) / NULLIF(ABS(d.pre_base_units), 0) AS donor_base_units_pct_chg,
  f.post_avg_tdp,
  f.post_avg_velocity_spm,
  f.post_avg_store_selling_velocity,
  f.post_units_pct_promo,
  f.post_promo_weeks,
  f.prior_period_base_units,
  f.yago_same_period_base_units,
  GREATEST(f.post_base_units - f.pre_base_units, 0) AS focal_units_gained,
  GREATEST(d.pre_base_units - d.post_base_units, 0) AS estimated_donor_units_lost,
  LEAST(1.0, GREATEST(0.0,
    GREATEST(d.pre_base_units - d.post_base_units, 0)
    / NULLIF(GREATEST(f.post_base_units - f.pre_base_units, 0), 0)
  )) AS cannibalization_rate,
  LEAST(1.0, GREATEST(0.0,
    GREATEST(f.post_base_units - f.pre_base_units, 0)
    / NULLIF(GREATEST(f.post_base_units - f.pre_base_units, 0)
            + GREATEST(d.pre_base_units - d.post_base_units, 0), 0)
  )) AS incremental_share,
  CASE
    WHEN (d.post_base_units - d.pre_base_units) / NULLIF(ABS(d.pre_base_units), 0) < -0.10
     AND (f.post_base_units - f.pre_base_units) / NULLIF(ABS(f.pre_base_units), 0) > 0.03
      THEN 'CANNIBALIZING'
    WHEN (d.post_base_units - d.pre_base_units) / NULLIF(ABS(d.pre_base_units), 0) BETWEEN -0.10 AND -0.03
     AND f.post_base_units > f.pre_base_units
      THEN 'WATCH'
    WHEN d.post_base_units >= d.pre_base_units * 0.97
      THEN 'INCREMENTAL'
    ELSE 'NEUTRAL'
  END AS label
FROM comparison_pool_weekly p
JOIN built_prepost_features f
  ON p.focal_upc = f.focal_upc
 AND p.channel_outlet = f.channel_outlet
 AND p.retail_account = f.retail_account
 AND p.geography = f.geography
JOIN donor_prepost_features d
  ON p.focal_upc = d.focal_upc
 AND p.candidate_upc = d.donor_upc
 AND p.channel_outlet = d.channel_outlet
 AND p.retail_account = d.retail_account
 AND p.geography = d.geography
 AND f.window_type = d.window_type;
```

```sql
-- Q6 rolling/event detection
REPLACE INTO event_detection_weekly OVERWRITE ALL
SELECT
  upc,
  channel_outlet,
  retail_account,
  geography,
  __time,
  base_units,
  AVG(base_units) OVER (
    PARTITION BY upc, channel_outlet, retail_account, geography
    ORDER BY __time ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
  ) AS rolling_13w_avg_base_units,
  STDDEV(base_units) OVER (
    PARTITION BY upc, channel_outlet, retail_account, geography
    ORDER BY __time ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
  ) AS rolling_13w_stddev_base_units,
  (base_units - AVG(base_units) OVER (
    PARTITION BY upc, channel_outlet, retail_account, geography
    ORDER BY __time ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
  )) / NULLIF(STDDEV(base_units) OVER (
    PARTITION BY upc, channel_outlet, retail_account, geography
    ORDER BY __time ROWS BETWEEN 13 PRECEDING AND 1 PRECEDING
  ), 0) AS z_score_base_units
FROM built_enriched_weekly;
```

```sql
-- Q7 new_upc_candidates
REPLACE INTO new_upc_candidates OVERWRITE ALL
SELECT
  upc,
  MIN(__time) AS first_seen_week,
  ANY_VALUE(description) AS description,
  ANY_VALUE(parent_brand) AS parent_brand,
  ANY_VALUE(brand_line) AS brand_line,
  ANY_VALUE(spins_flavor_raw) AS spins_flavor_raw,
  ANY_VALUE(spins_flavor) AS spins_flavor,
  ANY_VALUE(specific_flavor_normalized) AS specific_flavor_normalized,
  ANY_VALUE(pack_count) AS pack_count
FROM built_enriched_weekly
WHERE parent_brand = 'BUILT'
GROUP BY upc
HAVING MIN(__time) >= TIME_SHIFT(CURRENT_TIMESTAMP, 'P1W', -16);

-- Q8 new_upc_classifications
REPLACE INTO new_upc_classifications OVERWRITE ALL
SELECT
  n.*,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM built_enriched_weekly e
      WHERE e.parent_brand = n.parent_brand
        AND e.specific_flavor_normalized = n.specific_flavor_normalized
        AND e.spins_flavor = n.spins_flavor
        AND e.pack_count <> n.pack_count
        AND e.upc <> n.upc
    ) THEN 'NEW_PACK_SIZE'
    ELSE 'NEW_FLAVOR_CANDIDATE'
  END AS new_upc_type,
  CASE
    WHEN n.spins_flavor_raw <> n.spins_flavor THEN 1 ELSE 0
  END AS taxonomy_review_needed
FROM new_upc_candidates n;

-- Q9 ramp monitor
REPLACE INTO new_product_ramp_monitor OVERWRITE ALL
SELECT
  c.*,
  TIMESTAMPDIFF(WEEK, c.first_seen_week, CURRENT_TIMESTAMP) AS weeks_since_launch,
  CASE
    WHEN TIMESTAMPDIFF(WEEK, c.first_seen_week, CURRENT_TIMESTAMP) <= 6 THEN 'SUPPRESSED'
    WHEN TIMESTAMPDIFF(WEEK, c.first_seen_week, CURRENT_TIMESTAMP) <= 8 THEN 'LOW_CONFIDENCE'
    ELSE 'ACTIVE'
  END AS scoring_status
FROM new_upc_classifications c;
```

#### Q10–Q13 — Scoring outputs for v10 UI

```sql
-- These are populated by Python scoring write-back, then read by the v10 UI.
-- Tables:
-- scored_cannibalization
-- cannibalization_rate_weekly
-- cannibalization_rate_forecast_weekly
-- event_queue
```

### 13.4 Python training and scoring implementation

Create these scripts in the production repository. For the first client pilot,
run them manually from an Azure VM or Aevah job runner. Later, schedule them
after each Druid ingestion task completes.

#### `requirements.txt`

```text
pandas>=2.2
numpy>=1.26
scikit-learn>=1.4
lightgbm>=4.3
shap>=0.45
requests>=2.31
sqlalchemy>=2.0
pydruid>=0.6.9
joblib>=1.3
pyarrow>=15.0
```

#### `config.py`

```python
DRUID_SQL_URL = "https://<client-druid-router>/druid/v2/sql"
DRUID_INGEST_URL = "https://<client-druid-router>/druid/indexer/v1/task"
MODEL_DIR = "models"
RANDOM_SEED = 42
FEATURE_TABLE = "ml_training_features"
```

#### `druid_client.py` Druid SQL reader

```python
import requests
import pandas as pd

def druid_sql(sql: str, url: str, auth=None) -> pd.DataFrame:
    payload = {"query": sql, "resultFormat": "object"}
    r = requests.post(url, json=payload, auth=auth, timeout=300)
    r.raise_for_status()
    return pd.DataFrame(r.json())
```

This tiny helper is the source of the later imports:

```python
from druid_client import druid_sql
```

`pydruid` is also a valid alternative, especially if the production code wants
a DB-API or SQLAlchemy-style connection instead of a direct `requests.post`
wrapper:

```python
import pandas as pd
from pydruid.db import connect

def druid_sql(sql: str, host: str, port: int = 8888, path: str = "/druid/v2/sql/", scheme: str = "https") -> pd.DataFrame:
    conn = connect(host=host, port=port, path=path, scheme=scheme)
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()
```

For the pilot scripts, the direct HTTP helper is still the simplest default:
it matches Druid's native SQL API, keeps authentication and timeout behavior
obvious, and avoids adding SQLAlchemy/DB-API behavior unless the surrounding
job runner already standardizes on it.

#### Model training

```python
import joblib
import lightgbm as lgb
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, average_precision_score
from config import DRUID_SQL_URL, MODEL_DIR, RANDOM_SEED, FEATURE_TABLE
from druid_client import druid_sql

FEATURES = [
    "relationship_distance", "pack_distance",
    "focal_base_units_pct_chg", "donor_base_units_pct_chg",
    "post_avg_tdp", "post_avg_velocity_spm", "post_avg_store_selling_velocity",
    "post_units_pct_promo", "post_promo_weeks",
    "prior_period_base_units", "yago_same_period_base_units",
    "cannibalization_rate", "incremental_share"
]

def train_models():
    df = druid_sql(f"SELECT * FROM {FEATURE_TABLE}", DRUID_SQL_URL)
    df = df[df["label"].isin(["CANNIBALIZING", "WATCH", "INCREMENTAL"])].copy()
    df["target"] = (df["label"] == "CANNIBALIZING").astype(int)
    df[FEATURES] = df[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0)

    groups = df["focal_upc"].astype(str) + "|" + df["geography"].astype(str)
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_SEED)
    train_idx, test_idx = next(split.split(df, df["target"], groups))

    X_train, y_train = df.iloc[train_idx][FEATURES], df.iloc[train_idx]["target"]
    X_test, y_test = df.iloc[test_idx][FEATURES], df.iloc[test_idx]["target"]

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=600,
        learning_rate=0.04,
        num_leaves=31,
        feature_fraction=0.85,
        bagging_fraction=0.85,
        bagging_freq=5,
        class_weight="balanced",
        random_state=RANDOM_SEED
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)]
    )

    pred = model.predict_proba(X_test)[:, 1]
    print("AUC", roc_auc_score(y_test, pred))
    print("Average precision", average_precision_score(y_test, pred))

    joblib.dump({"model": model, "features": FEATURES}, f"{MODEL_DIR}/model_cannibal_v5.pkl")

if __name__ == "__main__":
    train_models()
```

#### Donor ranker

```python
import joblib
import lightgbm as lgb
from config import DRUID_SQL_URL, MODEL_DIR
from druid_client import druid_sql
from train_cannibal import FEATURES

df = druid_sql("SELECT * FROM ml_training_features", DRUID_SQL_URL)
df["rank_label"] = df["label"].map({"CANNIBALIZING": 3, "WATCH": 1, "INCREMENTAL": 0, "NEUTRAL": 0}).fillna(0)
df = df.sort_values(["focal_upc", "geography", "donor_upc"])
group_sizes = df.groupby(["focal_upc", "geography"]).size().tolist()

ranker = lgb.LGBMRanker(
    objective="lambdarank",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    random_state=42
)
ranker.fit(df[FEATURES].fillna(0), df["rank_label"], group=group_sizes)
joblib.dump({"model": ranker, "features": FEATURES}, f"{MODEL_DIR}/model_ranker_v5.pkl")
```

#### Rate forecaster

```python
import joblib
import lightgbm as lgb
from config import DRUID_SQL_URL, MODEL_DIR
from druid_client import druid_sql

RATE_FEATURES = [
    "relationship_distance", "pack_distance", "post_avg_tdp",
    "post_avg_velocity_spm", "post_units_pct_promo",
    "prior_period_base_units", "yago_same_period_base_units",
    "planned_tdp_delta", "planned_price_delta", "planned_promo_weeks",
    "assortment_overlap_index"
]

df = druid_sql("SELECT * FROM ml_training_features WHERE window_type = '13w'", DRUID_SQL_URL)
df = df.fillna(0)
models = {}
for alpha in [0.10, 0.50, 0.90]:
    m = lgb.LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        n_estimators=400,
        learning_rate=0.04,
        num_leaves=31,
        random_state=42
    )
    m.fit(df[RATE_FEATURES], df["cannibalization_rate"])
    models[alpha] = m
joblib.dump({"models": models, "features": RATE_FEATURES}, f"{MODEL_DIR}/model_rate_forecast_v5.pkl")
```

#### Scoring and write-back

```python
import json
import joblib
import numpy as np
import pandas as pd
import requests
from config import DRUID_SQL_URL, DRUID_INGEST_URL, MODEL_DIR
from druid_client import druid_sql

SCENARIOS = {
    "hold": {"planned_tdp_delta": 0, "planned_price_delta": 0, "planned_promo_weeks": 0, "assortment_overlap_index": 0.60},
    "selective": {"planned_tdp_delta": 17, "planned_price_delta": 0, "planned_promo_weeks": 0, "assortment_overlap_index": 0.45},
    "broad": {"planned_tdp_delta": 49, "planned_price_delta": 0, "planned_promo_weeks": 2, "assortment_overlap_index": 0.85},
    "reduce": {"planned_tdp_delta": -7, "planned_price_delta": 0, "planned_promo_weeks": 0, "assortment_overlap_index": 0.25},
    "test": {"planned_tdp_delta": 9, "planned_price_delta": 0, "planned_promo_weeks": 0, "assortment_overlap_index": 0.35},
}

def score():
    cannibal = joblib.load(f"{MODEL_DIR}/model_cannibal_v5.pkl")
    rate_bundle = joblib.load(f"{MODEL_DIR}/model_rate_forecast_v5.pkl")
    df = druid_sql("SELECT * FROM ml_training_features WHERE window_type = '13w'", DRUID_SQL_URL)
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

    df["cannibal_prob"] = cannibal["model"].predict_proba(df[cannibal["features"]])[:, 1]
    df["cannibal_status"] = pd.cut(
        df["cannibal_prob"],
        bins=[-0.01, 0.35, 0.65, 1.0],
        labels=["Incremental", "Watch", "Cannibalizing"]
    ).astype(str)

    # Write scored_cannibalization through the agreed Aevah/Druid ingestion path.
    # In production this should write JSON/Parquet to Azure Blob, then submit a Druid ingestion task.
    df.to_parquet("scored_cannibalization.parquet", index=False)

    forecast_rows = []
    for scenario_id, assumptions in SCENARIOS.items():
        sf = df.copy()
        for k, v in assumptions.items():
            sf[k] = v
        for horizon in range(1, 14):
            row = sf.copy()
            row["scenario_id"] = scenario_id
            row["forecast_horizon_week"] = horizon
            row["scenario_assumption_json"] = json.dumps(assumptions)
            for alpha, col in [(0.10, "low"), (0.50, "base"), (0.90, "high")]:
                row[f"cannibalization_rate_forecast_{col}"] = rate_bundle["models"][alpha].predict(
                    row[rate_bundle["features"]]
                )
            forecast_rows.append(row)
    forecast = pd.concat(forecast_rows, ignore_index=True)
    forecast.to_parquet("cannibalization_rate_forecast_weekly.parquet", index=False)

if __name__ == "__main__":
    score()
```

### 13.5 UI wiring for `mo_cannibalization_tool_v10.html`

The v10 UI should stop using hardcoded screen values once Druid is connected.
Use these endpoint contracts:

| UI screen | Backend source |
|---|---|
| Priority Events | `event_queue` filtered by confidence, `scored_at`, and selected scope |
| SKU Summary | `scored_cannibalization` by focal UPC, channel/outlet, retail account, geography, window |
| Pack Ladder | `scored_cannibalization` filtered to `comparison_type = SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER` |
| Cross-Flavor | Query 2c / `comparison_pool_weekly` filtered to same canonical `spins_flavor` |
| Competitive | Query 2b on demand |
| Pool Health | `built_prepost_features` + `event_detection_weekly`; default 13 weeks, previous 13 weeks, same 13 weeks year ago |
| Ramp Monitor | `new_product_ramp_monitor` |
| Explanation | SHAP fields on `scored_cannibalization` |
| Forecast Next Move | `cannibalization_rate_forecast_weekly` filtered by `scenario_id` |
| Action | `event_queue` + forecast tables |

Example fetch:

```javascript
async function fetchForecast({ focalUpc, scenarioId, channelOutlet, retailAccount, geography }) {
  const res = await fetch('/api/mo/forecast', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ focalUpc, scenarioId, channelOutlet, retailAccount, geography })
  });
  if (!res.ok) throw new Error('Forecast request failed');
  return await res.json();
}
```

### 13.6 Pilot data extract for model definition and feature engineering

The 99-row `All_items_extract_41926-h100.csv` is useful for schema validation
only. It is too small for model definition or feature engineering. For actual
model testing, create a deterministic pilot extract with complete time series.

Recommended model-definition extract:

1. Include **100% of BUILT rows** across all available weeks, retail accounts,
   geographies, and channels. BUILT volume is the target surface and should not
   be sampled away.
2. Include all rows for the key comparison universe:
   `WELLNESS & NUTRITION BARS` in `CONVENTIONAL|FOOD`,
   `CONVENTIONAL|MULTI OUTLET`, `CONVENTIONAL|MASS MERCH`, and
   `CONVENTIONAL|CONVENIENCE`. Exclude `CONVENTIONAL|MILITARY` from scoring.
3. Include Tier 1 competitor brands for the same accounts/geographies:
   RXBAR, BAREBELLS, QUEST, PERFECT BAR, THINK!, ALOHA, NO COW, FULFIL,
   PURE PROTEIN, 1ST PHORM, SIMPLYPROTEIN, and NUGO NUTRITION.
4. Keep all weeks needed for the model windows. Minimum: 65 weeks. Preferred:
   104 weeks. Do not sample random weeks; cannibalization depends on continuity.
5. Include all columns from the expanded 214-column extract, even if the v1 model
   uses only a subset. Storage pressure should be handled by row selection first,
   not by dropping fields that may become QA or model controls.

### 13.7 If only 10% of total data can be uploaded to Druid

Do **not** upload a random 10% of rows. Random row sampling breaks time series,
launch windows, pre/post comparisons, and year-over-year controls.

Upload a stratified complete-history slice:

| Priority | What to upload | Why |
|---|---|---|
| 1 | 100% of BUILT rows | Required for focal SKU history, pack ladders, ramp monitoring, and all UI examples. |
| 2 | 100% of BUILT rows for at least 104 weeks if available | Enables prior-quarter and year-over-year Pool Health. |
| 3 | Tier 1 competitor rows in the same category and selected retail/geography cells | Enables competitive context without uploading the full category universe. |
| 4 | Top retail accounts/geographies where BUILT has meaningful TDP or sales | Preserves the business-relevant buyer/account story. |
| 5 | A small control set of low/zero BUILT geographies | Helps the model learn negative examples and category softness. |

Recommended 10% selection algorithm:

```sql
-- Build this selection in the source warehouse before Azure Blob upload.
-- Keep complete UPC × retail account × geography × week series for selected cells.
WITH built_cells AS (
  SELECT
    "Channel/Outlet",
    "Retail Account",
    "Geography Level",
    "Geography",
    SUM(CASE WHEN "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
             THEN "TDP" ELSE 0 END) AS built_tdp
  FROM full_spins_export
  WHERE "Subcategory" = 'WELLNESS & NUTRITION BARS'
  GROUP BY 1,2,3,4
),
ranked_cells AS (
  SELECT *,
         ROW_NUMBER() OVER (ORDER BY built_tdp DESC) AS built_cell_rank
  FROM built_cells
)
SELECT s.*
FROM full_spins_export s
JOIN ranked_cells c
  ON s."Channel/Outlet" = c."Channel/Outlet"
 AND s."Retail Account" = c."Retail Account"
 AND s."Geography Level" = c."Geography Level"
 AND s."Geography" = c."Geography"
WHERE
  s."Subcategory" = 'WELLNESS & NUTRITION BARS'
  AND (
    s."Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
    OR (
      c.built_cell_rank <= <N_CELLS_THAT_FITS_10_PERCENT>
      AND s."Brand" IN ('RXBAR', 'BAREBELLS', 'QUEST', 'PERFECT BAR', 'THINK!',
                        'ALOHA', 'NO COW', 'FULFIL', 'PURE PROTEIN',
                        '1ST PHORM', 'SIMPLYPROTEIN', 'NUGO NUTRITION')
    )
  );
```

If the above exceeds 10%, reduce selected cells by retail account/geography
rank. Do not reduce by randomly dropping weeks or dropping BUILT rows.

For Friday's client meeting, the recommended ask is:

- Upload the full expanded-schema file for a **complete-history pilot slice**.
- Start with 100% BUILT + Tier 1 competitors in the top BUILT accounts/geographies.
- Preserve 104 weeks if possible; accept 65 weeks as the minimum useful history.
- Confirm whether Druid storage constraints are row-count, segment-count, or
  retained-history constraints. The best mitigation differs for each.

---

## Section 14. Price Elasticity Extension for Mo

### 14.1 Product scope

Price Elasticity is a peer module beside Cannibalization in the Mo suite. The
top-level menu should expose:

```text
Mo
├── Cannibalization
└── Price Elasticity
```

Each module keeps its own Determine / Diagnose / Decide flow. Cross-navigation
should be explicit and contextual:

- From Price Elasticity to Cannibalization when a promo or price cut may be
  pulling volume from a BUILT donor pack.
- From Cannibalization to Price Elasticity when a donor-pressure event may be
  price- or promo-induced rather than assortment-induced.
- From either module to Competitive when the driver is a Tier 1 brand price gap.

### 14.2 Price elasticity questions Mo must answer

| Question | Required comparison | Default read |
|---|---|---|
| How sensitive is this BUILT SKU to price? | SKU × account × geography × week | Own-price elasticity |
| Is the 4pk priced correctly versus 1ct and 12pk? | Same `specific_flavor_normalized`, same `parent_brand`, different `pack_count` | Pack price ladder |
| Does a 4pk discount hurt the 1ct? | Same specific flavor pack pair | Cross-price elasticity |
| Is a competitor price gap affecting BUILT? | BUILT SKU or flavor vs Tier 1 competitors | Competitive price gap |
| Is this pack priced correctly vs MULO FOOD category norms? | BUILT pack size vs MULO FOOD protein bar pack-size benchmark | Pack-size norm index |
| Does flavor or protein content drive more sales and store penetration? | Specific flavor, SPINS FLAVOR, protein grams/range, sales, stores selling | Flavor vs protein driver read |
| What promo depth works best? | Discount depth × promo mechanic × account/geography | Promo elasticity |
| What happens if we change ARP or promo depth? | Scenario inputs plus historical controls | Price response forecast |
| What happens if I drop the 12pk by $3? | Current price, proposed price, own elasticity, cross-price elasticity, competitor gaps | What-if forecast |

### 14.3 Guardrails

Price elasticity should not be shown as a raw coefficient without context.
Every score must carry:

- `window_type`
- `channel_outlet`
- `retail_account`
- `geography_level`
- `geography`
- `focal_upc`
- `comparison_upc` when relevant
- `price_basis` (`ARP`, `Base ARP`, `ARP Promo`, `ARP Non-Promo`, or `price_per_bar`)
- `tdp_control_status`
- `promo_control_status`
- `competitor_gap_control_status`
- `seasonality_control_status`
- `confidence`
- `model_version`

Mo should suppress or label as Low confidence when:

- fewer than 8 usable weeks exist in either side of the window
- price movement is nearly flat, making elasticity unstable
- TDP changes materially in the same weeks as price movement and cannot be
  controlled
- promo weeks change materially but promo mechanics are missing
- competitor price is missing for the selected account/geography
- military / DECA channels appear in the scoring scope

Own-price elasticity interpretation bands use the **reported absolute value**.
The signed coefficient is still stored separately and used for scenario math.

| Reported absolute elasticity | UI label | Meaning |
|---|---|---|
| `<0.5` | Inelastic | Price changes have limited observed unit response |
| `0.5 to 1.2` | Mildly elastic | Watch price moves, but do not overreact |
| `1.2 to 2.0` | Elastic | Price changes likely affect demand |
| `>2.0` | Highly elastic | Use strong guardrails before changing price |

Cross-price coefficients keep their sign because direction matters:

| Signed coefficient | UI label | Meaning |
|---|---|---|
| `>+0.4` | Substitution pressure | Focal discount may pull from comparison item |
| `+0.1 to +0.4` | Mild substitution | Watch pair during promo weeks |
| `-0.1 to +0.1` | Neutral | Little observed interaction |
| `<-0.1` | Complement / shared lift | Items may rise together |

### 14.3.1 Elasticity sign convention and what-if math

Mo should store both a signed coefficient and a reported absolute value. The
signed coefficient is the cleanest modeling representation. For normal goods,
own-price elasticity is usually negative: price increases reduce unit demand,
and price decreases increase unit demand.

Business users usually expect own-price elasticity to be reported as a positive
absolute value. The UI should show the absolute value first and expose the signed
coefficient only in explanatory text or provenance:

```text
Reported elasticity: 1.5
Signed coefficient:  -1.5
```

For scenario calculations, always use the signed coefficient internally:

```text
percent_price_change = (new_price - current_price) / current_price
expected_percent_unit_change = signed_elasticity * percent_price_change
forecast_units = current_units * (1 + expected_percent_unit_change)
```

Example:

```text
Current ARP: $22.99
New ARP:     $19.99
Price move:  -$3.00

percent_price_change = (19.99 - 22.99) / 22.99 = -13.05%
reported_own_price_elasticity_abs = 1.5
signed_own_price_elasticity = -1.5
expected_percent_unit_change = -1.5 * -13.05% = +19.57%
```

Mo should render this in plain language:

> A $3.00 price drop from $22.99 to $19.99 is a 13.1% price decrease. With
> own-price elasticity of 1.5 absolute / -1.5 signed, expected unit lift is
> roughly 19.6% before TDP, promo, pack-ladder, and competitor guardrails.

For competitor response, use cross-price elasticity:

```text
competitor_expected_percent_unit_change =
  competitor_cross_price_elasticity * built_percent_price_change
```

If BUILT price decreases and competitor units are expected to decline, the
competitor cross-price coefficient will usually be positive in substitution
settings:

```text
BUILT price change = -13.05%
competitor cross-price elasticity = +0.25
competitor unit change = +0.25 * -13.05% = -3.26%
```

Guardrail: the simple elasticity formula is a first-pass estimate. The final Mo
forecast should adjust or caveat the result when the price drop is unusually
large, crosses a known price threshold, changes promo mechanics, changes TDP,
or creates internal pack-ladder donor pressure.

### 14.4 Derived features from `built_enriched_weekly`

Add these derived fields in a new price feature table. Do not remove the source
price and promo fields already retained in Q0.

| Feature | Definition |
|---|---|
| `price_per_bar` | `arp / pack_count` when pack count is known |
| `base_price_per_bar` | `base_arp / pack_count` |
| `promo_price_per_bar` | `arp_promo / pack_count` |
| `nonpromo_price_per_bar` | `arp_non_promo / pack_count` |
| `log_units` | `LN(NULLIF(units, 0))` |
| `log_base_units` | `LN(NULLIF(base_units, 0))` |
| `log_price_per_bar` | `LN(NULLIF(price_per_bar, 0))` |
| `price_index_vs_flavor_pack_avg` | SKU price per bar / same specific flavor pack-ladder average |
| `price_gap_vs_1ct` | focal price per bar / same flavor 1ct price per bar - 1 |
| `price_gap_vs_12pk` | focal price per bar / same flavor 12pk price per bar - 1 |
| `price_gap_vs_competitor` | BUILT price per bar / selected competitor price per bar - 1 |
| `promo_depth_bucket` | `0-5`, `10-15`, `20-25`, `30+` based on discount |
| `promo_mechanic` | `TPR`, `DISPLAY`, `FEATURE`, `SPK`, combinations, or `NONE` |
| `tdp_pct_chg_4w` / `13w` | TDP movement controls |
| `competitor_price_min_tier1` | Lowest Tier 1 competitor price per bar in same account/geography/week |
| `scenario_current_price` | Current ARP or price per bar used in a what-if |
| `scenario_new_price` | User-entered or preset scenario price |
| `scenario_price_delta_dollars` | `scenario_new_price - scenario_current_price` |
| `scenario_price_delta_pct` | `(scenario_new_price - scenario_current_price) / scenario_current_price` |
| `own_price_elasticity_signed` | Signed coefficient used in calculations; usually negative for normal goods |
| `own_price_elasticity_abs` | Positive reported value shown in the UI |
| `scenario_expected_unit_lift_pct_simple` | signed own-price coefficient × `scenario_price_delta_pct` |

### 14.5 Druid query additions

Add these outputs after Q13.

| Query | Output | Purpose |
|---|---|---|
| Q14 | `price_elasticity_weekly_features` | Weekly SKU-level price, promo, distribution, seasonality, and competitor price features |
| Q15 | `price_pack_ladder_weekly` | Same specific flavor pack-size price architecture and price gaps |
| Q16 | `price_competitive_weekly` | BUILT vs Tier 1 competitor price gaps by account/geography/week |
| Q17 | `price_elasticity_training_features` | Regression-ready windows for own-price, cross-price, and promo elasticity |
| Q18 | `scored_price_elasticity` | Python write-back with coefficients, confidence, drivers, and action labels |
| Q19 | `price_elasticity_forecast_weekly` | Scenario forecasts for ARP, promo depth, and competitor gap |
| Q20 | `mulo_food_pack_size_norms` | MULO FOOD protein bar norms for 1ct, 4pk, 8pk, and 12pk |
| Q21 | `flavor_protein_driver_features` | Flavor, protein, sales, velocity, TDP, and store penetration diagnostics |
| Q22 | `price_event_queue` | Significant price, promo, new item, benchmark, and confidence events with lineage |

Minimal Q14 shape:

```sql
REPLACE INTO price_elasticity_weekly_features OVERWRITE ALL
SELECT
  __time,
  channel_outlet,
  retail_account,
  retail_account_level,
  geography_level,
  geography,
  upc,
  description,
  department,
  category,
  subcategory,
  parent_brand,
  brand_line,
  competitor_tier,
  spins_flavor,
  specific_flavor_normalized,
  pack_count,
  nfp_protein,
  nfp_protein_range,
  units,
  base_units,
  dollars,
  base_dollars,
  tdp,
  pct_stores_selling,
  avg_weekly_units_spm,
  avg_weekly_units_per_store_selling_per_item,
  arp,
  base_arp,
  arp_promo,
  arp_non_promo,
  arp_pct_discount_any_promo,
  units_pct_promo,
  promo_weeks,
  units_lift_tpr,
  units_lift_any_display,
  units_lift_any_feature,
  units_yago,
  base_units_yago,
  arp_yago,
  CASE WHEN pack_count > 0 THEN arp / pack_count END AS price_per_bar,
  CASE WHEN pack_count > 0 THEN base_arp / pack_count END AS base_price_per_bar,
  CASE WHEN pack_count > 0 THEN arp_promo / pack_count END AS promo_price_per_bar,
  CASE WHEN pack_count > 0 THEN arp_non_promo / pack_count END AS nonpromo_price_per_bar,
  LN(NULLIF(units, 0)) AS log_units,
  LN(NULLIF(base_units, 0)) AS log_base_units,
  LN(NULLIF(CASE WHEN pack_count > 0 THEN arp / pack_count END, 0)) AS log_price_per_bar,
  CASE
    WHEN arp_pct_discount_any_promo IS NULL OR arp_pct_discount_any_promo < 0.05 THEN '0-5'
    WHEN arp_pct_discount_any_promo < 0.16 THEN '10-15'
    WHEN arp_pct_discount_any_promo < 0.26 THEN '20-25'
    ELSE '30+'
  END AS promo_depth_bucket
FROM built_enriched_weekly
WHERE channel_outlet <> 'CONVENTIONAL|MILITARY';
```

Minimal Q15 shape:

```sql
REPLACE INTO price_pack_ladder_weekly OVERWRITE ALL
SELECT
  f.__time,
  f.channel_outlet,
  f.retail_account,
  f.geography_level,
  f.geography,
  f.upc AS focal_upc,
  c.upc AS comparison_upc,
  f.specific_flavor_normalized,
  f.pack_count AS focal_pack_count,
  c.pack_count AS comparison_pack_count,
  f.price_per_bar AS focal_price_per_bar,
  c.price_per_bar AS comparison_price_per_bar,
  (f.price_per_bar / NULLIF(c.price_per_bar, 0)) - 1 AS price_gap_vs_comparison,
  f.units AS focal_units,
  c.units AS comparison_units,
  f.units_pct_promo AS focal_units_pct_promo,
  c.units_pct_promo AS comparison_units_pct_promo
FROM price_elasticity_weekly_features f
JOIN price_elasticity_weekly_features c
  ON f.__time = c.__time
 AND f.channel_outlet = c.channel_outlet
 AND f.retail_account = c.retail_account
 AND f.geography = c.geography
 AND f.parent_brand = c.parent_brand
 AND f.specific_flavor_normalized = c.specific_flavor_normalized
 AND f.upc <> c.upc
WHERE f.parent_brand = 'BUILT';
```

Minimal Q16 shape:

```sql
REPLACE INTO price_competitive_weekly OVERWRITE ALL
SELECT
  b.__time,
  b.channel_outlet,
  b.retail_account,
  b.geography_level,
  b.geography,
  b.upc AS built_upc,
  c.upc AS competitor_upc,
  c.parent_brand AS competitor_brand,
  c.competitor_tier,
  b.spins_flavor,
  b.specific_flavor_normalized,
  b.price_per_bar AS built_price_per_bar,
  c.price_per_bar AS competitor_price_per_bar,
  (b.price_per_bar / NULLIF(c.price_per_bar, 0)) - 1 AS price_gap_vs_competitor,
  b.units AS built_units,
  c.units AS competitor_units,
  b.units_pct_promo AS built_units_pct_promo,
  c.units_pct_promo AS competitor_units_pct_promo
FROM price_elasticity_weekly_features b
JOIN price_elasticity_weekly_features c
  ON b.__time = c.__time
 AND b.channel_outlet = c.channel_outlet
 AND b.retail_account = c.retail_account
 AND b.geography = c.geography
 AND b.spins_flavor = c.spins_flavor
WHERE b.parent_brand = 'BUILT'
  AND c.parent_brand <> 'BUILT'
  AND c.competitor_tier = 'TIER_1_DIRECT';
```

Minimal Q20 shape:

```sql
REPLACE INTO mulo_food_pack_size_norms OVERWRITE ALL
SELECT
  channel_outlet,
  retail_account,
  geography_level,
  geography,
  pack_count,
  APPROX_QUANTILE(price_per_bar, 0.50) AS norm_price_per_bar_median,
  AVG(price_per_bar) AS norm_price_per_bar_avg,
  AVG(arp) AS norm_arp_avg,
  AVG(avg_weekly_units_spm) AS norm_units_spm,
  AVG(avg_weekly_units_per_store_selling_per_item) AS norm_store_selling_velocity,
  AVG(pct_stores_selling) AS norm_pct_stores_selling,
  AVG(tdp) AS norm_tdp,
  AVG(units_pct_promo) AS norm_units_pct_promo,
  COUNT(DISTINCT upc) AS norm_upc_count
FROM price_elasticity_weekly_features
WHERE channel_outlet = 'CONVENTIONAL|MULTI OUTLET'
  AND department IS NOT NULL
  AND subcategory = 'WELLNESS & NUTRITION BARS'
  AND pack_count IN (1, 4, 8, 12)
GROUP BY 1,2,3,4,5;
```

If SPINS uses MULO FOOD as a literal geography or account value rather than a
channel/outlet value, filter Q20 on the literal source fields supplied in the
client extract. The business definition is: **MULO FOOD protein bar category,
pack counts 1, 4, 8, and 12**.

Minimal Q21 shape:

```sql
REPLACE INTO flavor_protein_driver_features OVERWRITE ALL
SELECT
  f.channel_outlet,
  f.retail_account,
  f.geography_level,
  f.geography,
  f.parent_brand,
  f.brand_line,
  f.spins_flavor,
  f.specific_flavor_normalized,
  f.pack_count,
  f.nfp_protein,
  f.nfp_protein_range,
  AVG(f.units) AS avg_units,
  AVG(f.base_units) AS avg_base_units,
  AVG(f.avg_weekly_units_spm) AS avg_units_spm,
  AVG(f.avg_weekly_units_per_store_selling_per_item) AS avg_store_selling_velocity,
  AVG(f.pct_stores_selling) AS avg_pct_stores_selling,
  AVG(f.tdp) AS avg_tdp,
  AVG(f.price_per_bar) AS avg_price_per_bar,
  AVG(f.units_pct_promo) AS avg_units_pct_promo,
  AVG(f.price_per_bar / NULLIF(n.norm_price_per_bar_median, 0)) AS price_index_vs_pack_norm,
  AVG(f.avg_weekly_units_spm / NULLIF(n.norm_units_spm, 0)) AS velocity_index_vs_pack_norm,
  AVG(f.pct_stores_selling / NULLIF(n.norm_pct_stores_selling, 0)) AS store_penetration_index_vs_pack_norm
FROM price_elasticity_weekly_features f
LEFT JOIN mulo_food_pack_size_norms n
  ON f.channel_outlet = n.channel_outlet
 AND f.retail_account = n.retail_account
 AND f.geography = n.geography
 AND f.pack_count = n.pack_count
WHERE f.parent_brand = 'BUILT'
GROUP BY 1,2,3,4,5,6,7,8,9,10,11;
```

The model layer can use Q21 for two objectives:

- compare flavor groups and specific flavors against sales, velocity, TDP, and
  store penetration outcomes
- estimate whether protein content / protein range adds explanatory power after
  controlling for flavor, pack size, price index, promo, and distribution

### 14.6 ML approach

Use a separate price model family. Do not overload the cannibalization classifier.

| Model | Type | Target | Output |
|---|---|---|---|
| Own-price elasticity | Regularized panel regression or LightGBM SHAP-constrained regression | `log_units` or `log_base_units` | `own_price_elasticity_signed`, `own_price_elasticity_abs` |
| Cross-price elasticity | Pairwise panel regression / LightGBM | focal demand response to comparison price | `cross_price_elasticity_signed` |
| Promo elasticity | Gradient boosted regression by promo depth/mechanic | unit lift over non-promo baseline | `promo_elasticity_signed`, `promo_elasticity_abs`, `expected_lift` |
| Price scenario forecaster | Quantile LightGBM regressor | units/base units under planned ARP, promo depth, competitor gap | low/base/high forecast |
| What-if calculator | Deterministic formula plus model guardrails | user-entered dollar or percent price moves | simple lift, adjusted lift, competitor response |
| Flavor vs protein driver | Interpretable regression / SHAP model | units, velocity, TDP, store penetration | relative driver weights for flavor and protein |

Recommended first-pass feature set:

```text
log_price_per_bar
price_gap_vs_1ct
price_gap_vs_12pk
price_gap_vs_competitor
promo_depth_bucket
units_pct_promo
promo_weeks
units_lift_tpr
units_lift_any_display
units_lift_any_feature
tdp
tdp_pct_chg_4w
avg_weekly_units_spm
avg_weekly_units_per_store_selling_per_item
units_yago
base_units_yago
arp_yago
pack_count
relationship_distance
competitor_tier
channel_outlet
retail_account
geography
week_of_year
```

### 14.7 Scored output schema

```sql
CREATE TABLE scored_price_elasticity (
  scored_at                          TIMESTAMP,
  model_version                      VARCHAR,
  window_type                        VARCHAR,
  focal_upc                          VARCHAR,
  focal_description                  VARCHAR,
  comparison_upc                     VARCHAR,
  comparison_description             VARCHAR,
  channel_outlet                     VARCHAR,
  retail_account                     VARCHAR,
  geography_level                    VARCHAR,
  geography                          VARCHAR,
  specific_flavor_normalized         VARCHAR,
  spins_flavor                       VARCHAR,
  focal_pack_count                   BIGINT,
  comparison_pack_count              BIGINT,
  price_basis                        VARCHAR,
  focal_arp                          DOUBLE,
  focal_price_per_bar                DOUBLE,
  comparison_price_per_bar           DOUBLE,
  competitor_brand                   VARCHAR,
  competitor_tier                    VARCHAR,
  price_gap_pct                      DOUBLE,
  own_price_elasticity_signed        DOUBLE,
  own_price_elasticity_abs           DOUBLE,
  cross_price_elasticity_signed      DOUBLE,
  promo_elasticity_signed            DOUBLE,
  promo_elasticity_abs               DOUBLE,
  recommended_price_low              DOUBLE,
  recommended_price_high             DOUBLE,
  scenario_current_price             DOUBLE,
  scenario_new_price                 DOUBLE,
  scenario_price_delta_dollars       DOUBLE,
  scenario_price_delta_pct           DOUBLE,
  scenario_unit_lift_pct_simple      DOUBLE,
  scenario_unit_lift_pct_adjusted    DOUBLE,
  scenario_competitor_unit_chg_pct   DOUBLE,
  mulo_pack_norm_price_per_bar       DOUBLE,
  mulo_pack_norm_velocity            DOUBLE,
  mulo_pack_norm_store_penetration   DOUBLE,
  price_index_vs_mulo_pack_norm      DOUBLE,
  velocity_index_vs_mulo_pack_norm   DOUBLE,
  store_penetration_index_vs_norm    DOUBLE,
  flavor_driver_weight               DOUBLE,
  protein_driver_weight              DOUBLE,
  recommended_action                 VARCHAR,
  elasticity_status                  VARCHAR,
  confidence                         VARCHAR,
  tdp_control_status                 VARCHAR,
  promo_control_status               VARCHAR,
  competitor_gap_control_status      VARCHAR,
  seasonality_control_status         VARCHAR,
  shap_feature_1                     VARCHAR,
  shap_value_1                       DOUBLE,
  shap_feature_2                     VARCHAR,
  shap_value_2                       DOUBLE,
  shap_feature_3                     VARCHAR,
  shap_value_3                       DOUBLE
);
```

### 14.8 UI wiring for `mo_intelligence_suite_v11.html`

| Price screen | Backend source |
|---|---|
| Pricing Events | `event_queue` plus `scored_price_elasticity` high/medium confidence alerts |
| Elasticity Summary | `scored_price_elasticity` by focal UPC and selected scope |
| Pack Price | `price_pack_ladder_weekly` plus `scored_price_elasticity` cross-price rows |
| Promo Response | `price_elasticity_training_features` aggregated by promo depth/mechanic |
| Competitive Price | `price_competitive_weekly` plus scored competitive elasticity |
| MULO Norms | `mulo_food_pack_size_norms` + `flavor_protein_driver_features` |
| Price Explanation | `price_event_queue` + SHAP fields on `scored_price_elasticity` |
| Price Forecast | `price_elasticity_forecast_weekly` by scenario |
| What-if Calculator | user-entered scenario payload plus `scored_price_elasticity` coefficients |
| Pricing Action | `scored_price_elasticity` action labels plus linked cannibalization guardrails |

The UI should keep the BUILT color theme:

- blue for informational price architecture and forecast scenarios
- amber for watch bands, promo caution, and medium confidence
- red for elastic risk, competitor gap alerts, and margin-risk warnings
- green for recommended price bands and healthy lift-to-margin reads

### 14.9 Linkage to cannibalization

Every price event should carry optional linkage fields:

```text
linked_cannibalization_event_id
linked_comparison_type
linked_donor_upc
linked_cannibalization_rate
linked_incremental_share
```

Mo should render these as plain-language bridges:

- "This promo lift may be partly sourced from the 1ct donor."
- "The 4pk price cut increased units, but the same weeks show elevated pack
  ladder donor pressure."
- "Competitive price pressure appears external: BUILT and its pack ladder are
  not showing internal donor loss."

### 14.10 Significant price event detection

Mo should maintain a dedicated `price_event_queue` rather than burying price
events inside generic forecast rows. Each event must be explainable, auditable,
and linkable to the exact inputs that created it.

Recommended event taxonomy:

| Event type | Trigger examples | User-facing label |
|---|---|---|
| `NEW_ITEM_PRICE_BASELINE` | New UPC, new pack size, first stable selling weeks after ramp suppression | New item price baseline |
| `DRASTIC_PRICE_CHANGE` | ARP or price per bar changes by more than 15% or more than configured dollar threshold | Material price move |
| `PROMO_DEPTH_SHIFT` | Promo discount depth changes by 10+ points, or promo weeks jump materially | Promo change |
| `PROMO_RESPONSE_BREAKPOINT` | Deeper discount adds weak incremental unit lift | Diminishing promo return |
| `COMPETITIVE_PRICE_GAP` | BUILT price per bar exceeds Tier 1 competitor by threshold, default 9% | Competitive gap risk |
| `PACK_NORM_GAP` | BUILT pack price per bar is materially above MULO FOOD pack-size norm | Category norm gap |
| `ELASTICITY_CONFIDENCE_DOWNGRADE` | Missing competitor price, low movement, TDP/promo confounding, or insufficient weeks | Confidence downgrade |
| `PRICE_DEFENSE_OPPORTUNITY` | Competitor gap is high but BUILT velocity/store penetration remain strong | Price defense |
| `PACK_LADDER_COMPRESSION` | 12pk value correction collapses 4pk/12pk price spread | Pack ladder risk |

Minimum deterministic triggers:

```text
price_delta_pct_abs >= 0.15
OR price_delta_dollars_abs >= 2.00
OR promo_depth_delta_pts >= 10
OR price_gap_vs_tier1_competitor >= 0.09
OR price_index_vs_mulo_pack_norm >= 1.07
OR weeks_since_first_seen BETWEEN 8 AND 16
OR elasticity_confidence changed from High/Medium to Low
```

`price_event_queue` schema:

```sql
CREATE TABLE price_event_queue (
  event_id                         VARCHAR,
  event_type                       VARCHAR,
  event_label                      VARCHAR,
  event_severity                   VARCHAR,  -- Red / Amber / Blue / Green
  confidence                       VARCHAR,
  scored_at                        TIMESTAMP,
  focal_upc                        VARCHAR,
  focal_description                VARCHAR,
  comparison_upc                   VARCHAR,
  comparison_description           VARCHAR,
  channel_outlet                   VARCHAR,
  retail_account                   VARCHAR,
  geography_level                  VARCHAR,
  geography                        VARCHAR,
  window_type                      VARCHAR,
  current_arp                      DOUBLE,
  prior_arp                        DOUBLE,
  price_delta_dollars              DOUBLE,
  price_delta_pct                  DOUBLE,
  promo_depth_delta_pts            DOUBLE,
  price_gap_vs_competitor          DOUBLE,
  price_index_vs_mulo_pack_norm    DOUBLE,
  own_price_elasticity_abs         DOUBLE,
  own_price_elasticity_signed      DOUBLE,
  simple_unit_lift_pct             DOUBLE,
  adjusted_unit_lift_pct           DOUBLE,
  recommended_action               VARCHAR,
  price_defense_label              VARCHAR,
  explanation_narrative            VARCHAR,
  shap_feature_1                   VARCHAR,
  shap_value_1                     DOUBLE,
  shap_feature_2                   VARCHAR,
  shap_value_2                     DOUBLE,
  shap_feature_3                   VARCHAR,
  shap_value_3                     DOUBLE,
  source_table                     VARCHAR,
  source_query_id                  VARCHAR,
  source_columns_json              VARCHAR,
  lineage_json                     VARCHAR,
  linked_cannibalization_event_id  VARCHAR
);
```

Explainability requirements:

- Every event has deterministic trigger fields in addition to any ML score.
- Every model-derived event includes top SHAP drivers or equivalent feature
  attribution.
- Every "price defense" recommendation shows the evidence for defending price:
  strong velocity, store penetration, category norm comparison, competitor gap,
  and promo/TDP controls.
- Every event carries provenance: source table, query id, model version, scoring
  window, selected geography/account, source columns, and transform lineage.
- Mo must avoid labels like "elastic risk" without an explanation narrative and
  at least one drill path into supporting rows.

Price defense examples:

| Situation | Mo defense read |
|---|---|
| BUILT priced above competitor but velocity and store penetration remain strong | Defend price; monitor competitor promo weeks |
| Competitor promotes below BUILT and BUILT velocity drops without TDP loss | Temporary promo response; avoid permanent ARP cut |
| 12pk is above MULO norm and store penetration is weak | Test value correction |
| 4pk units fall during 12pk discount | Treat 12pk lift as potentially sourced from BUILT pack ladder |
