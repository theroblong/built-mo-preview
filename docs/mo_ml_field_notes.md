# Mo ML Field Notes

Operational findings from running the Mo ML pipeline against the live Druid cluster.
These are facts discovered during execution that are not in planning documents or script
stubs. Read before writing or modifying any pipeline script.

Companion file: `mockups/mo_ml_field_notes.html`

---

## Data Quirks

### DQ1 — focal pct_chg columns are NULL for all rows

`focal_base_units_pct_chg`, `focal_tdp_pct_chg`, and `focal_velocity_spm_pct_chg` are
NULL for every row in `ml_training_features`.

**Why:** SPINS has no sales history for a product before its `first_week_selling` date.
The pre-window for the focal SKU is structurally empty.

**How to apply:** Exclude all focal `pct_chg` columns from feature sets in P3 and P4.
Use donor-side columns for signals instead. Any `fillna(0)` on these columns produces
zero-variance features that add noise without signal.

---

### DQ2 — Druid returns numeric columns as object dtype

All numeric columns from `/druid/v2/sql/` arrive as Python `object` dtype (strings or
`None`) in the JSON response. Passing them directly to LightGBM or using them in
arithmetic raises `ValueError: pandas dtypes must be int, float or bool`.

**Why:** Druid's JSON serializer does not guarantee numeric types. A single `NULL` value
in a column forces pandas to infer `object` for the entire column.

**How to apply:** In every script that trains or scores, convert immediately after loading:

```python
df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
```

Never skip this step, even for columns that look numeric in the Druid console.

---

### DQ3 — Extreme outliers in pct_chg columns break LightGBM histogram binning

`donor_base_units_pct_chg` can reach values like 5,098 when the pre-window denominator
is near zero (a donor SKU that barely sold before the focal launched). This collapses
LightGBM's histogram bins and produces "No further splits with positive gain, best
gain: -inf" for ALL trees — the model trains but learns nothing.

**Why:** LightGBM's histogram algorithm allocates bins across the observed range. With
variance ~3,730 the bins are too wide to separate any meaningful signal.

**How to apply:** Always clip pct_chg columns before training:

```python
for col in pct_chg_cols:
    df[col] = df[col].clip(-1.0, 2.0)
```

---

### DQ4 — Druid SQL forbids ORDER BY on non-time columns

Any query with `ORDER BY <non-time-col>` at the top level returns a Druid 400 error:
`"SQL query requires ordering a table by non-time column"`. This silently swallows if
the calling code has a bare `except: pass`.

**Why:** Druid's SQL planner only allows top-level ordering by `__time`. Arbitrary column
sorts are unsupported at the query layer.

**How to apply:** Never use `ORDER BY` on non-time columns in Druid SQL. Sort in Python
after fetching:

```python
df = df.sort_values("some_col", ascending=False).reset_index(drop=True)
```

This burned us in the `cannibal_guardrail` block of `price_elasticity.py` — the 400
was silently caught and the guardrail always returned false.

---

### DQ5 — price_elasticity_training_features column names differ from assumed names

Confirmed schema (verified with `SELECT * LIMIT 1`):

| Assumed name | Actual name |
|---|---|
| `pre_13w_avg_velocity_spm` | `pre_13w_velocity_spm` |
| `post_13w_avg_base_units` | `post_13w_base_units` |
| `promo_confound_flag` | `promo_confounded` |
| `promo_depth_bucket` | does not exist in this table |
| `seasonality_index` | does not exist in this table |

**How to apply:** Always verify schema with `SELECT * LIMIT 1` before writing any new
script against a datasource for the first time.

---

## LightGBM Patterns

### LG1 — LambdaRank requires Python-side sort before groupby

Druid does not support `ORDER BY` on non-time columns (see DQ4). `LGBMRanker` requires
rows to be physically sorted by group key before `group_sizes` is computed — its internal
grouping is positional, not key-based. Out-of-order rows produce wrong group assignments
and silent ranking errors.

**How to apply:** In every ranking script (P2, P4), sort in Python before computing groups:

```python
df = df.sort_values("focal_upc").reset_index(drop=True)
group_sizes = df.groupby("focal_upc", sort=False).size().tolist()
```

---

### LG2 — "No further splits" warnings are expected and harmless at ROC-AUC 1.0

P1 and P3 both emit `No further splits with positive gain, best gain: -inf` warnings at
the leaf level but achieve ROC-AUC 1.0. The warning fires when a leaf is already pure;
other leaves in the same tree continue splitting normally.

**Why:** Labels in these scripts are derived from the same features used for training,
making the classification task trivially solvable. The model memorizes the rule.

**How to apply:** Do not treat these warnings as errors in the Mo context. A flat logloss
curve with AUC near 1.0 confirms the model is learning correctly. The warning only
becomes a real problem when it fires on ALL trees AND the model was expected to generalize
— see DQ3 for the degenerate-binning case where the same symptom indicates an actual
data problem.
