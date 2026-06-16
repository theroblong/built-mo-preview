# Mo Cannibalization Model Reference

Operational reference for interpreting and working with Mo's cannibalization model
outputs. Covers scored output definitions, relationship distance semantics, confidence
label meaning, pipeline write-back mechanics, and scoring coverage facts.

Companion file: `mockups/mo_cannibalization_model_reference.html`

---

## Cannibalization Status Definitions

Sourced from `scored_cannibalization.cannibal_prob` thresholds. As of the 2026-06-09
pipeline run (60,695 rows, 85 focal UPCs):

| Status | cannibal_prob range | Row count | Meaning |
|---|---|---|---|
| **Cannibalizing** | ≥ 0.66 (in practice > 0.99 for most rows) | 28,337 | Confirmed active volume transfer from donor to focal |
| **Watch** | 0.36 – 0.64 | 19 | Elevated co-movement below confirmation threshold; early or weak signal; monitor Pre/Post, do not act on it alone |
| **Incremental** | ≤ 0.33 | 32,339 | Focal SKU is growing category demand, not pulling from donor |

The distribution is genuinely bimodal — most pairs are either clearly cannibalizing or
clearly incremental. The Watch band is narrow by design.

---

## relationship_distance Values

| Distance | Meaning | Business implication |
|---|---|---|
| **1** | BUILT sibling — same brand, pack/format variants (pack ladder) | Internal demand shift; warning signal |
| **3** | BUILT adjacent — different BUILT product line, same flavor territory | Internal demand shift; warning signal |
| **4** | Competitor (Quest, Barebells, Atkins, etc.) | Market share gain; positive signal |

Only distances 1, 3, and 4 appear in the current data. There are no distance-2 or
distance-5 rows in `scored_cannibalization`.

`is_own_brand` = distance IN (1, 3). `is_competitor` = distance = 4.

**UI priority rule:** Surface own-brand alerts first (more actionable for assortment
decisions); fall back to competitor signal if no own-brand issue exists for the selected
filter.

**Cannibalizing a competitor (dist = 4)** = market share gain = green InsightBox.  
**Cannibalizing a BUILT sibling (dist = 1 or 3)** = internal demand shift = red/amber InsightBox.

---

## cannibal_confidence Measures Data Maturity, Not Model Certainty

`cannibal_confidence` (Low / Medium / High) is assigned based on weeks of pre/post
history available, not on `cannibal_prob`. A row can have `cannibal_prob = 1.00` (model
is 100% certain) AND `cannibal_confidence = Low` (only 3 weeks of data). These measure
different things and must not be conflated.

| Druid value | UI display name | Condition |
|---|---|---|
| Low | Early signal | `focal_post_weeks_count < 8` |
| Medium | Developing | `focal_post_weeks_count ≥ 8` AND `donor_pre_weeks_count ≥ 8` |
| High | Confirmed | `focal_post_weeks_count ≥ 12` AND `donor_pre_weeks_count ≥ 10` |

The Druid column values ("Low", "Medium", "High") are unchanged — UI translation is
display-layer only. Low-confidence events are hidden by default behind a "Show early
signals" toggle on the Priority Events screen.

---

## Scoring Coverage

As of the 2026-06-09 pipeline run:

| Metric | Value |
|---|---|
| Total scored rows | 60,695 |
| Focal UPCs covered | 85 |
| Filter combos covered | 1,498 of 3,137 (47.8%) |

Coverage by channel:

| Channel | Scored combos |
|---|---|
| CONVENTIONAL\|MULTI OUTLET | 475 |
| REGIONAL & INDEP GROCERY | 404 |
| CONVENTIONAL\|FOOD | 280 |
| NATURAL EXPANDED | 247 |
| CONVENTIONAL\|CONVENIENCE | 48 |
| CONVENTIONAL\|MASS MERCH | 30 |
| VITAMINS & SUPPLEMENTS | 23 |
| CONV\|DRUG / CONV\|CLUB / CONV-SPINS | 14 |

**Root cause of gaps:** Not a bug. The Q5 (`ml_training_features`) WHERE clause enforces
intentional data-maturity gates:

- `focal_post_weeks_count >= 8` — focal SKU needs 8+ post-launch weeks in that market
- `donor_pre_13w_weeks_count >= 8` — donor needs 8+ weeks of pre-history
- `donor_pre_13w_base_units > 0`, `post_13w_base_units > 0`, `post_13w_tdp > 0`

Products that launched in a channel after the last pipeline run, or that lack established
competing products, are structurally excluded until they clear these gates.

**For demos:** MULO, CONVENTIONAL|FOOD, and REGIONAL & INDEP GROCERY are the most
reliable channels. CONVENIENCE and CLUB are thin because BUILT's distribution in those
channels is newer.

---

## Pipeline Write-Back Pattern

Scored outputs are written back to Druid via MinIO parquet upload. No direct EXTERN
or REPLACE INTO from Python is supported on this cluster (EXTERN is blocked — E05).

```
1. Python script writes scored DataFrame to a local .parquet file
2. Upload parquet to MinIO bucket via scripts/mo_writeback.py
3. mo_writeback.py generates an index_parallel ingestion spec (REPLACE INTO equivalent)
   targeting the correct Druid datasource
4. Human POSTs the spec to the Druid indexer:
      POST /druid/indexer/v1/task
5. Poll task status until SUCCESS
```

Credentials are in `scripts/.env` (gitignored). Redacted specs for sharing live in
`specs/`.
