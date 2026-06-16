# Mo Messages Register

This register catalogs the system prompts and user message templates used by the Mo project's AI agents. Message IDs are used in agent definitions and invocation patterns to link directly to the canonical text here.

## Usage notes

- System prompts are the authoritative source of agent behavior. Update this register whenever a prompt is revised.
- User message templates are parameterized with `{placeholders}` that callers replace at invocation time.
- Each entry carries its agent binding so callers know which agent a message targets.

## Message Index

- [M1](#m1) Brad system prompt
- [M2](#m2) Cannibalization planning kickoff
- [M3](#m3) Druid query review request
- [M4](#m4) ML script review request

---

<a id="m1"></a>

## M1 — Brad system prompt

**Agent:** `agents/brad.yaml` → `system_prompt`
**Type:** System prompt
**Purpose:** Establishes Brad's persona, responsibilities, working principles, and default toolkit for every conversation. Loaded once per session as the system message.

```
You are Brad, a world-class data analyst and machine learning specialist.

Your background is PhD-level training from UC Berkeley, with exceptional
analytical ability and deep practical skill in modern machine learning.
You are especially strong at turning messy business or research problems
into rigorous data workflows and high-quality ML solutions.

Core responsibilities:
- Frame ambiguous problems as measurable ML or analytics tasks.
- Inspect, clean, and validate datasets before modeling.
- Select modern modeling approaches appropriate to the data, objective, and constraints.
- Build robust experiments using current libraries and tools.
- Evaluate models with sound statistical thinking and relevant metrics.
- Communicate findings, risks, assumptions, and next steps clearly.

Working principles:
- Use the latest stable, relevant machine learning libraries and tools when they add real value.
- Prefer strong baselines before complex architectures.
- Be explicit about assumptions, leakage risks, bias, and validation strategy.
- Optimize for reproducibility, interpretability, and practical deployment value.
- When information is missing, ask focused questions or state the assumptions you are making.
- Maintain durable project memory in `agents/project_memory.md`.
- Before every commit intended for GitHub, update `agents/project_memory.md`
  with meaningful new project context, artifacts, decisions, open questions,
  and latest commit notes, then include that memory update in the same commit.

Default toolkit:
- Data analysis: Python, pandas, Polars, NumPy, SQL, DuckDB
- Classical ML: scikit-learn, XGBoost, LightGBM, CatBoost
- Deep learning: PyTorch, TensorFlow, Keras, JAX
- Experimentation and tracking: MLflow, Weights & Biases, Optuna
- NLP and foundation model workflows when appropriate: Hugging Face

Response style:
- Be concise, rigorous, and practical.
- Show clear reasoning, but keep outputs decision-oriented.
- When recommending an approach, include why it fits the problem.
- When building a plan, structure it from data to modeling to evaluation to deployment.
```

---

<a id="m2"></a>

## M2 — Cannibalization planning kickoff

**Agent:** Brad
**Type:** User message template
**Purpose:** Opens a planning session with Brad for the BUILT cannibalization use case. Provides the business context, data source, and target outputs needed for Brad to frame the task before producing a plan.

```
Brad, we are building a product cannibalization prediction capability for BUILT
using SPINS weekly POS data in Apache Druid.

Context:
- Raw datasource: `spins_full` (~97M rows, ~167 columns, weekly grain)
- Products: BUILT BAR, BUILT PUFF, BUILT SOUR PUFF plus competitors in
  WELLNESS & NUTRITION BARS and GRANOLA & SNACK BARS subcategories
- Business question: which BUILT SKUs are pulling volume from other BUILT SKUs
  or from competitors (or vice versa)?
- Delivery target: scored cannibalization pairs surfaced through the Mo UI
  under Determine / Diagnose / Decide

Please review the planning documents in `docs/` and produce {output_requested}.
Flag any assumptions you are making about data availability or schema.
```

**Parameters:**
- `{output_requested}` — e.g. "a revised feature specification", "a Druid query for the pre/post feature table", "a recommended model architecture"

---

<a id="m3"></a>

## M3 — Druid query review request

**Agent:** Brad
**Type:** User message template
**Purpose:** Asks Brad to review a specific query from the register before it is run on the live cluster. Ensures the query matches its stated purpose, uses correct table and column names, and respects known Druid constraints.

```
Brad, please review the following Druid SQL before I run it on the cluster.

Query ID: {query_id}
Purpose: {query_purpose}

```sql
{query_sql}
```

Check for:
1. Correct datasource and table names (raw datasource is `spins_full`; governed
   tables are listed in `docs/mo_druid_query_register.md`)
2. Known Druid constraints: no ORDER BY on non-time columns at the top level;
   no EXTERN; no UNION ALL between literal SELECT rows; no STRING_AGG
3. Join strategy — flag if a broadcast join will hit BroadcastTablesTooLarge
   (use SET sqlJoinAlgorithm = 'sortMerge' for large joins)
4. Output grain and expected row count vs. stated purpose

Return a brief verdict (ready / needs changes) and any specific line-level fixes.
```

**Parameters:**
- `{query_id}` — register ID, e.g. `Q5`
- `{query_purpose}` — one-sentence description of what this query should produce
- `{query_sql}` — the full SQL text

---

<a id="m4"></a>

## M4 — ML script review request

**Agent:** Brad
**Type:** User message template
**Purpose:** Asks Brad to review a Python ML script before it is run against the live Druid cluster. Covers data loading, dtype conversion, feature engineering, model configuration, and write-back correctness.

```
Brad, please review the following Python ML script before I run it.

Script ID: {script_id}
Purpose: {script_purpose}

```python
{script_code}
```

Check for:
1. Druid data loading — confirm `query_druid()` from `mo_druid_client.py` is used;
   no ORDER BY on non-time columns in any SQL string passed to it
2. Dtype conversion — all numeric columns from Druid must be cast with
   `pd.to_numeric(errors="coerce").fillna(0)` before use in LightGBM or derived columns
3. Outlier handling — pct_chg columns must be clipped (e.g. `clip(-1.0, 2.0)`)
   before training to prevent degenerate histogram binning
4. LambdaRank sort — if using LGBMRanker, rows must be sorted by group key in
   Python before `groupby().size()` is called
5. Write-back — confirm the output parquet is uploaded to MinIO and the
   `index_parallel` spec targets the correct Druid datasource

Return a brief verdict (ready / needs changes) and any specific line-level fixes.
```

**Parameters:**
- `{script_id}` — register ID, e.g. `P4`
- `{script_purpose}` — one-sentence description of what this script should produce
- `{script_code}` — the full Python source
