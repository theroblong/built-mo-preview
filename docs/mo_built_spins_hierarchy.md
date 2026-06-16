# BUILT / SPINS Product Hierarchy Reference

SPINS attribute codes used in the Mo pipeline for pack size, protein, sugars, calories,
and sugar alcohols. These codes appear in `spins_full` and downstream tables.

Source: BUILT product hierarchy slide shared by client after the 2026-06-12 meeting.

Companion file: `mockups/mo_built_spins_hierarchy.html`

---

## Brand Totals

| Brand line |
|---|
| BUILT BAR |
| BUILT PUFF |
| BUILT SOUR PUFF |
| PPG - BUILT TOTAL |
| Top Competitors |

---

## Pack Size

| Code | Label | Pack count range |
|---|---|---|
| 1 | Singles | 1 |
| 2 | Multipack | 2–5 |
| 3 | Value Pack | 6–9 |
| 4 | Family Size | 10+ |

Pack size codes map to `focal_pack_count` and `candidate_pack_count` in
`comparison_pool_weekly`. Use them when displaying pack distance context in the UI
or filtering by pack tier.

---

## Protein (g)

| Code | Label |
|---|---|
| 5 | Under 10g |
| 6 | 10–14.99g |
| 7 | 15–19.99g |
| 8 | 20–24.999g |
| 9 | 25+g |

---

## Sugars (g)

| Code | Label |
|---|---|
| 10 | 0–5g |
| 11 | 5–10g |
| 12 | 10–15g |
| 13 | 15+g |

Note: code 13 (15+g) may represent a restricted or inactive bucket — flag if
encountered in production data.

---

## Calories

| Code | Label |
|---|---|
| 14 | Under 100 |
| 15 | 100–150 |
| 16 | 150–200 |
| 17 | 200–250 |
| 18 | 250+ |

---

## Sugar Alcohols

| Code | Label |
|---|---|
| 19 | Y (contains sugar alcohols) |
| 20 | N |

---

## Panel Data Fields

Available from SPINS panel data (confirmed 2026-06-12 client meeting):

| Field | Notes |
|---|---|
| Trips | Household purchase trip count |
| HH Count | Household reach |
| Buy Rate | Units purchased per buying household |

These fields are available under Category Insights and BUILT Insights. If surfaced in
the SPINS extract, they can enrich the SKU Summary and Mo Chat context.

---

## Company Report Templates

| Template |
|---|
| General performance |
| Promotional Analysis |
| Category Review |
| Other (TBD) |
