"""MO_70 — Retailer × SKU velocity extract for Brian (BUILT actual + forecast + category).

Three deliverables:

  outputs/velocity_extract_built.csv       — BUILT: 52wk actuals + 13wk forecast
  outputs/velocity_extract_category.csv    — Category: 13wk avg velocity by brand × retailer
  outputs/velocity_extract.html            — interactive HTML (BUILT primary, category context)
  mockups/velocity_extract.html            — copy for sharing

SCOPE
-----
- BUILT extract:    52 weeks actuals + 13 weeks forecast from retailer_sales_forecast
- Category extract: 13-week trailing average for all brands in built_filtered_weekly
- MULO aggregates excluded throughout

VELOCITY COLUMNS
----------------
velocity_spm          avg_weekly_units_spm (SPINS native — units per store per week, actuals)
forecast_vel_base     forecast_units_base / last_known_tdp (implied forecast velocity, q50)
forecast_vel_low      forecast_units_low  / last_known_tdp
forecast_vel_high     forecast_units_high / last_known_tdp
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from mo_druid_client import query_druid
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from mo_druid_client import query_druid

# ── Config ────────────────────────────────────────────────────────────────────
MULO_CHANNEL   = "CONVENTIONAL|MULTI OUTLET"
MULO_GEOS_SQL  = "'MULO', 'W/ AK/HI', 'MULO W/ C-STORES', 'W/ C-STORES'"
BUILT_BRANDS   = ("'BUILT'", "'BUILT BAR'", "'BUILT PUFF'", "'BUILT SOUR PUFF'")
OUT_DIR        = Path("outputs")
MOCKUPS_DIR    = Path("mockups")
GENERATED_AT   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

OUT_DIR.mkdir(exist_ok=True)
MOCKUPS_DIR.mkdir(exist_ok=True)


# ── 1a. BUILT actuals — 52 weeks, aggregated across geographies ───────────────
print("1/4  BUILT actuals (52wk) …")
built_actuals = query_druid(f"""
    SELECT
        TIME_FLOOR(__time, 'P1W')                    AS __time,
        upc,
        LATEST(description)                           AS description,
        LATEST(source_brand)                          AS brand,
        channel_outlet,
        retail_account,
        SUM(CAST(base_units           AS DOUBLE))     AS base_units,
        AVG(CAST(avg_weekly_units_spm AS DOUBLE))     AS velocity_spm,
        SUM(CAST(tdp                  AS DOUBLE))     AS tdp,
        AVG(CAST(pct_stores_selling   AS DOUBLE))     AS pct_stores_selling,
        AVG(CAST(arp                  AS DOUBLE))     AS arp
    FROM "built_filtered_weekly"
    WHERE source_brand IN ({', '.join(BUILT_BRANDS)})
      AND channel_outlet != '{MULO_CHANNEL}'
      AND geography_raw NOT IN ({MULO_GEOS_SQL})
      AND base_units > 0
      AND __time >= TIMESTAMPADD(WEEK, -52, CURRENT_TIMESTAMP)
    GROUP BY 1, upc, channel_outlet, retail_account
    LIMIT 500000
""")
print(f"    {len(built_actuals):,} rows")

df_act = pd.DataFrame(built_actuals)
df_act["__time"] = pd.to_datetime(df_act["__time"], utc=True)
df_act["week"]   = df_act["__time"].dt.strftime("%Y-%m-%d")
for col in ["base_units", "velocity_spm", "tdp", "pct_stores_selling", "arp"]:
    df_act[col] = pd.to_numeric(df_act[col], errors="coerce")
df_act = df_act.rename(columns={"channel_outlet": "channel", "retail_account": "retailer"})


# ── 1b. BUILT last-known TDP per (upc, retailer, channel) ────────────────────
# Used to compute implied forecast velocity = forecast_units / last_tdp
print("2/4  BUILT forecast (13wk) …")
tdp_anchor = (
    df_act.sort_values("__time")
    .groupby(["upc", "retailer", "channel"])["tdp"]
    .last()
    .reset_index()
    .rename(columns={"tdp": "last_tdp"})
)


# ── 1c. BUILT forecast — 13 weeks forward ────────────────────────────────────
built_fct = query_druid(f"""
    SELECT
        __time,
        upc,
        LATEST(description)                                AS description,
        channel_outlet,
        retail_account,
        forecast_week_number,
        AVG(CAST(forecast_units_low  AS DOUBLE))           AS forecast_units_low,
        AVG(CAST(forecast_units_base AS DOUBLE))           AS forecast_units_base,
        AVG(CAST(forecast_units_high AS DOUBLE))           AS forecast_units_high
    FROM "retailer_sales_forecast"
    WHERE upc IN (SELECT DISTINCT upc FROM "built_filtered_weekly"
                  WHERE source_brand IN ({', '.join(BUILT_BRANDS)}) AND base_units > 0)
    GROUP BY 1, upc, channel_outlet, retail_account, forecast_week_number
    LIMIT 200000
""")
print(f"    {len(built_fct):,} forecast rows")

df_fct = pd.DataFrame(built_fct)
if not df_fct.empty:
    df_fct["__time"] = pd.to_datetime(df_fct["__time"], utc=True)
    df_fct["week"]   = df_fct["__time"].dt.strftime("%Y-%m-%d")
    for col in ["forecast_units_low", "forecast_units_base", "forecast_units_high"]:
        df_fct[col] = pd.to_numeric(df_fct[col], errors="coerce")
    df_fct = df_fct.rename(columns={"channel_outlet": "channel", "retail_account": "retailer"})
    # attach last-known TDP for implied velocity
    df_fct = df_fct.merge(tdp_anchor, on=["upc", "retailer", "channel"], how="left")
    df_fct["forecast_vel_low"]  = (df_fct["forecast_units_low"]  / df_fct["last_tdp"]).round(2)
    df_fct["forecast_vel_base"] = (df_fct["forecast_units_base"] / df_fct["last_tdp"]).round(2)
    df_fct["forecast_vel_high"] = (df_fct["forecast_units_high"] / df_fct["last_tdp"]).round(2)


# ── 2. Category 13-week summary ───────────────────────────────────────────────
# Anchor off the max date in the actuals data — CURRENT_TIMESTAMP may be beyond
# the data's last week (data ends 2026-04-19; Druid server clock is later).
data_max_ts = df_act["__time"].max()
data_max_str = data_max_ts.strftime("%Y-%m-%d")
cat_cutoff   = (data_max_ts - pd.Timedelta(weeks=13)).strftime("%Y-%m-%d")
print(f"3/4  Category 13wk summary (data max: {data_max_str}, cutoff: {cat_cutoff}) …")
cat_rows = query_druid(f"""
    SELECT
        upc,
        LATEST(description)                           AS description,
        LATEST(source_brand)                          AS brand,
        channel_outlet,
        retail_account,
        SUM(CAST(base_units           AS DOUBLE))     AS base_units_13w,
        AVG(CAST(avg_weekly_units_spm AS DOUBLE))     AS avg_velocity_spm,
        AVG(CAST(tdp                  AS DOUBLE))     AS avg_tdp,
        AVG(CAST(pct_stores_selling   AS DOUBLE))     AS avg_pct_stores,
        AVG(CAST(arp                  AS DOUBLE))     AS avg_arp,
        COUNT(DISTINCT __time)                        AS weeks_present
    FROM "built_filtered_weekly"
    WHERE channel_outlet != '{MULO_CHANNEL}'
      AND geography_raw NOT IN ({MULO_GEOS_SQL})
      AND base_units > 0
      AND __time >= TIMESTAMP '{cat_cutoff}'
      AND __time <= TIMESTAMP '{data_max_str}'
    GROUP BY upc, channel_outlet, retail_account
    LIMIT 500000
""")
print(f"    {len(cat_rows):,} rows")

df_cat = pd.DataFrame(cat_rows)
if not df_cat.empty:
    for col in ["base_units_13w", "avg_velocity_spm", "avg_tdp", "avg_pct_stores", "avg_arp"]:
        df_cat[col] = pd.to_numeric(df_cat[col], errors="coerce")
    df_cat["weeks_present"] = pd.to_numeric(df_cat["weeks_present"], errors="coerce")
    df_cat = df_cat.rename(columns={"channel_outlet": "channel", "retail_account": "retailer"})
    df_cat["avg_velocity_spm"] = df_cat["avg_velocity_spm"].round(2)
    df_cat["avg_arp"]          = df_cat["avg_arp"].round(2)
    df_cat["avg_tdp"]          = df_cat["avg_tdp"].round(1)
    df_cat["avg_pct_stores"]   = df_cat["avg_pct_stores"].round(3)
    df_cat = df_cat.sort_values("avg_velocity_spm", ascending=False)


# ── 3. Write CSVs ─────────────────────────────────────────────────────────────
print("4/4  Writing outputs …")

# BUILT CSV: actuals rows + forecast rows, labeled by type
df_act_out = df_act[["week","upc","description","brand","channel","retailer",
                      "base_units","velocity_spm","tdp","pct_stores_selling","arp"]].copy()
df_act_out["type"] = "actual"
df_act_out["forecast_units_low"]  = None
df_act_out["forecast_units_base"] = None
df_act_out["forecast_units_high"] = None
df_act_out["forecast_vel_low"]    = None
df_act_out["forecast_vel_base"]   = None
df_act_out["forecast_vel_high"]   = None

if not df_fct.empty:
    df_fct_out = df_fct[["week","upc","description","channel","retailer",
                          "forecast_units_low","forecast_units_base","forecast_units_high",
                          "forecast_vel_low","forecast_vel_base","forecast_vel_high"]].copy()
    df_fct_out["type"]             = "forecast"
    df_fct_out["brand"]            = "BUILT"
    df_fct_out["base_units"]       = None
    df_fct_out["velocity_spm"]     = None
    df_fct_out["tdp"]              = None
    df_fct_out["pct_stores_selling"] = None
    df_fct_out["arp"]              = None
    df_built_out = pd.concat([df_act_out, df_fct_out], ignore_index=True)
else:
    df_built_out = df_act_out

col_order = ["week","type","upc","description","brand","channel","retailer",
             "base_units","velocity_spm","tdp","pct_stores_selling","arp",
             "forecast_units_low","forecast_units_base","forecast_units_high",
             "forecast_vel_low","forecast_vel_base","forecast_vel_high"]
df_built_out[col_order].to_csv(OUT_DIR / "velocity_extract_built.csv", index=False)

df_cat.to_csv(OUT_DIR / "velocity_extract_category.csv", index=False)

print(f"    outputs/velocity_extract_built.csv     ({len(df_built_out):,} rows)")
print(f"    outputs/velocity_extract_category.csv  ({len(df_cat):,} rows)")


# ── 4. Build HTML ─────────────────────────────────────────────────────────────
# Build sparklines per series (upc × retailer × channel) from actuals
spark_map: dict[str, list] = {}
for key, g in df_act.groupby(["upc", "retailer", "channel"]):
    upc, retailer, channel = key
    series = g.sort_values("week")[["week","velocity_spm"]].dropna(subset=["velocity_spm"])
    pts = [round(v, 2) for v in series["velocity_spm"]]
    # append forecast q50 as continuation
    if not df_fct.empty:
        fct_g = df_fct[(df_fct["upc"]==upc) &
                        (df_fct["retailer"]==retailer) &
                        (df_fct["channel"]==channel)].sort_values("week")
        fpts = [round(v,2) if not math.isnan(v) else None
                for v in fct_g["forecast_vel_base"].tolist()]
        spark_map[f"{upc}|{retailer}|{channel}"] = {"actual": pts, "forecast": fpts}
    else:
        spark_map[f"{upc}|{retailer}|{channel}"] = {"actual": pts, "forecast": []}

# 13wk summary for BUILT
built_13w = (
    df_act[df_act["__time"] >= df_act["__time"].max() - pd.Timedelta(weeks=13)]
    .groupby(["upc","description","brand","channel","retailer"])
    .agg(vel_13w_avg=("velocity_spm","mean"),
         avg_base_units=("base_units","mean"),
         avg_tdp=("tdp","mean"),
         avg_pct_stores=("pct_stores_selling","mean"),
         avg_arp=("arp","mean"),
         weeks_13=("week","count"))
    .reset_index()
)

# 52wk stats per series
_g52 = df_act.groupby(["upc","channel","retailer"])["velocity_spm"]
built_52w = pd.DataFrame({
    "vel_52w_avg": _g52.mean(),
    "vel_52w_min": _g52.min(),
    "vel_52w_max": _g52.max(),
    "vel_52w_med": _g52.median(),
}).reset_index()

# 13wk forecast avg velocity
if not df_fct.empty:
    fct_avg = (
        df_fct.groupby(["upc","channel","retailer"])["forecast_vel_base"]
        .mean().reset_index()
        .rename(columns={"forecast_vel_base": "fct_vel_avg"})
    )
else:
    fct_avg = pd.DataFrame(columns=["upc","channel","retailer","fct_vel_avg"])

built_summary = (
    built_13w
    .merge(built_52w, on=["upc","channel","retailer"], how="left")
    .merge(fct_avg,   on=["upc","channel","retailer"], how="left")
    .sort_values("vel_13w_avg", ascending=False)
)
for c in ["vel_13w_avg","vel_52w_avg","vel_52w_min","vel_52w_max","vel_52w_med","fct_vel_avg","avg_arp"]:
    if c in built_summary.columns:
        built_summary[c] = built_summary[c].round(2)
built_summary["avg_base_units"] = built_summary["avg_base_units"].round(1)
built_summary["avg_tdp"]        = built_summary["avg_tdp"].round(1)

brands_built   = sorted(df_act["brand"].dropna().unique().tolist())
channels_built = sorted(df_act["channel"].dropna().unique().tolist())
retailers_built= sorted(df_act["retailer"].dropna().unique().tolist())

brands_cat    = sorted(df_cat["brand"].dropna().unique().tolist()) if not df_cat.empty else []
channels_cat  = sorted(df_cat["channel"].dropna().unique().tolist()) if not df_cat.empty else []
retailers_cat = sorted(df_cat["retailer"].dropna().unique().tolist()) if not df_cat.empty else []

built_rows_json = built_summary.to_dict(orient="records")
cat_rows_json   = df_cat.to_dict(orient="records") if not df_cat.empty else []
spark_json      = spark_map

html = f"""<title>Velocity Extract — BUILT + Category</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg:#0d1117;--surface:#161b22;--surface2:#1c2128;--border:#30363d;
    --text:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;--built:#e05c2a;
    --green:#3fb950;--amber:#d29922;--font:system-ui,-apple-system,sans-serif;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:13px;padding:24px}}
  h1{{font-size:20px;font-weight:600;color:#fff;margin-bottom:4px}}
  .meta{{color:var(--muted);font-size:12px;margin-bottom:20px}}
  .meta span{{color:var(--accent)}}

  /* tabs */
  .tabs{{display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:20px}}
  .tab{{padding:8px 20px;cursor:pointer;color:var(--muted);font-size:13px;
        border-bottom:2px solid transparent;margin-bottom:-1px;font-weight:500}}
  .tab.active{{color:#fff;border-bottom-color:var(--built)}}
  .tab:hover:not(.active){{color:var(--text)}}
  .panel{{display:none}}.panel.active{{display:block}}

  /* strip */
  .strip{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
  .stat{{background:var(--surface);border:1px solid var(--border);border-radius:6px;
         padding:10px 14px;min-width:120px}}
  .stat .val{{font-size:20px;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}}
  .stat .lbl{{color:var(--muted);font-size:11px;margin-top:2px}}

  /* filters */
  .filters{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center}}
  .filters label{{color:var(--muted);font-size:11px}}
  select,input[type=text]{{background:var(--surface);border:1px solid var(--border);
    color:var(--text);padding:5px 8px;border-radius:4px;font-size:12px}}
  select:focus,input:focus{{outline:none;border-color:var(--accent)}}
  button.reset{{background:var(--surface2);border:1px solid var(--border);
    color:var(--muted);padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px}}
  button.reset:hover{{border-color:var(--accent);color:var(--accent)}}
  .filter-group{{display:flex;align-items:center;gap:6px}}

  /* table */
  .tbl-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:6px}}
  table{{width:100%;border-collapse:collapse}}
  thead tr{{background:var(--surface2);position:sticky;top:0;z-index:10}}
  th{{padding:7px 10px;text-align:left;color:var(--muted);font-size:11px;font-weight:600;
      letter-spacing:.03em;text-transform:uppercase;border-bottom:1px solid var(--border);
      white-space:nowrap;cursor:pointer;user-select:none}}
  th:hover{{color:var(--accent)}}
  th.sort-asc::after{{content:' ▲';color:var(--accent)}}
  th.sort-desc::after{{content:' ▼';color:var(--accent)}}
  tbody tr{{border-bottom:1px solid var(--border)}}
  tbody tr:hover{{background:var(--surface2)}}
  td{{padding:5px 10px;vertical-align:middle}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}
  .chip{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
         font-weight:600;background:var(--surface2);border:1px solid var(--border);color:var(--muted)}}
  .chip.built{{background:#2a1208;border-color:#7a2e10;color:var(--built)}}
  .vel-cell{{display:flex;align-items:center;gap:6px;justify-content:flex-end}}
  .vel-bar{{height:6px;border-radius:3px;background:var(--accent);min-width:2px}}
  #b-count,#c-count{{color:var(--muted);font-size:11px;margin-bottom:8px}}

  /* forecast badge on sparkline */
  canvas.spark{{display:block}}

  @media(prefers-color-scheme:light){{
    :root{{--bg:#f6f8fa;--surface:#fff;--surface2:#f0f2f5;--border:#d0d7de;
          --text:#1f2328;--muted:#656d76;--accent:#0969da;--built:#c0410f}}
  }}
</style>

<h1>Velocity Extract — BUILT + Category</h1>
<p class="meta">
  BUILT 52wk actuals + 13wk forecast &nbsp;·&nbsp;
  Category 13wk avg &nbsp;·&nbsp;
  MULO excluded &nbsp;·&nbsp;
  Generated <span>{GENERATED_AT}</span> &nbsp;·&nbsp;
  Source: <span>built_filtered_weekly · retailer_sales_forecast</span>
</p>

<div class="tabs">
  <div class="tab active" onclick="switchTab('built',this)">BUILT (actuals + forecast)</div>
  <div class="tab" onclick="switchTab('cat',this)">Full Category (13wk avg)</div>
</div>

<!-- ── BUILT PANEL ─────────────────────────────────────────────────────────── -->
<div id="panel-built" class="panel active">
  <div class="strip" id="b-strip"></div>
  <div class="filters">
    <div class="filter-group"><label>Channel</label>
      <select id="b-f-ch" onchange="bFilter()">
        <option value="">All</option>
        {''.join(f'<option>{c}</option>' for c in channels_built)}
      </select></div>
    <div class="filter-group"><label>Retailer</label>
      <select id="b-f-rt" onchange="bFilter()">
        <option value="">All</option>
        {''.join(f'<option>{r}</option>' for r in retailers_built)}
      </select></div>
    <div class="filter-group"><label>Search</label>
      <input type="text" id="b-f-q" placeholder="UPC or description…"
             oninput="bFilter()" style="width:180px"></div>
    <button class="reset" onclick="bReset()">Reset</button>
    <button class="reset" onclick="bExport()" style="border-color:var(--green);color:var(--green)">⬇ Export CSV</button>
  </div>
  <div id="b-count"></div>
  <div class="tbl-wrap"><table id="b-tbl">
    <thead>
    <tr>
      <th colspan="4" style="border-right:1px solid var(--border)"></th>
      <th colspan="6" style="color:var(--accent);text-align:center;border-right:1px solid var(--border)">Velocity SPM (units / store / week)</th>
      <th colspan="4"></th>
    </tr>
    <tr>
      <th onclick="bSort('description')" data-col="description">Description</th>
      <th onclick="bSort('upc')" data-col="upc">UPC</th>
      <th onclick="bSort('channel')" data-col="channel">Channel</th>
      <th onclick="bSort('retailer')" data-col="retailer" style="border-right:1px solid var(--border)">Retailer</th>
      <th onclick="bSort('vel_13w_avg')" data-col="vel_13w_avg" class="sort-desc">13wk Avg</th>
      <th onclick="bSort('vel_52w_avg')" data-col="vel_52w_avg">52wk Avg</th>
      <th onclick="bSort('vel_52w_min')" data-col="vel_52w_min">52wk Min</th>
      <th onclick="bSort('vel_52w_max')" data-col="vel_52w_max">52wk Max</th>
      <th onclick="bSort('vel_52w_med')" data-col="vel_52w_med">52wk Med</th>
      <th onclick="bSort('fct_vel_avg')" data-col="fct_vel_avg" style="border-right:1px solid var(--border)">13wk Fct Avg</th>
      <th onclick="bSort('avg_base_units')" data-col="avg_base_units">Base Units/wk</th>
      <th onclick="bSort('avg_tdp')" data-col="avg_tdp">Avg TDP</th>
      <th onclick="bSort('avg_arp')" data-col="avg_arp">ARP</th>
      <th>Trend</th>
    </tr></thead>
    <tbody id="b-tbody"></tbody>
  </table></div>
</div>

<!-- ── CATEGORY PANEL ─────────────────────────────────────────────────────── -->
<div id="panel-cat" class="panel">
  <div class="strip" id="c-strip"></div>
  <div class="filters">
    <div class="filter-group"><label>Brand</label>
      <select id="c-f-br" onchange="cFilter()">
        <option value="">All</option>
        {''.join(f'<option>{b}</option>' for b in brands_cat)}
      </select></div>
    <div class="filter-group"><label>Channel</label>
      <select id="c-f-ch" onchange="cFilter()">
        <option value="">All</option>
        {''.join(f'<option>{c}</option>' for c in channels_cat)}
      </select></div>
    <div class="filter-group"><label>Retailer</label>
      <select id="c-f-rt" onchange="cFilter()">
        <option value="">All</option>
        {''.join(f'<option>{r}</option>' for r in retailers_cat)}
      </select></div>
    <div class="filter-group"><label>Search</label>
      <input type="text" id="c-f-q" placeholder="UPC, brand, or description…"
             oninput="cFilter()" style="width:180px"></div>
    <button class="reset" onclick="cReset()">Reset</button>
    <button class="reset" onclick="cExport()" style="border-color:var(--green);color:var(--green)">⬇ Export CSV</button>
  </div>
  <div id="c-count"></div>
  <div class="tbl-wrap"><table id="c-tbl">
    <thead><tr>
      <th onclick="cSort('brand')" data-col="brand">Brand</th>
      <th onclick="cSort('description')" data-col="description">Description</th>
      <th onclick="cSort('upc')" data-col="upc">UPC</th>
      <th onclick="cSort('channel')" data-col="channel">Channel</th>
      <th onclick="cSort('retailer')" data-col="retailer">Retailer</th>
      <th onclick="cSort('avg_velocity_spm')" data-col="avg_velocity_spm" class="sort-desc">Velocity SPM (13wk avg)</th>
      <th onclick="cSort('base_units_13w')" data-col="base_units_13w">Base Units (13w total)</th>
      <th onclick="cSort('avg_tdp')" data-col="avg_tdp">Avg TDP</th>
      <th onclick="cSort('avg_pct_stores')" data-col="avg_pct_stores">% Stores</th>
      <th onclick="cSort('avg_arp')" data-col="avg_arp">ARP</th>
    </tr></thead>
    <tbody id="c-tbody"></tbody>
  </table></div>
</div>

<script>
const BUILT_DATA  = {json.dumps(built_rows_json)};
const CAT_DATA    = {json.dumps(cat_rows_json)};
const SPARKS      = {json.dumps(spark_json)};
const BUILT_BRANDS= new Set(["BUILT","BUILT BAR","BUILT PUFF","BUILT SOUR PUFF"]);

const fmt0   = n => n==null||isNaN(n) ? "—" : Math.round(n).toLocaleString();
const fmt1   = n => n==null||isNaN(n) ? "—" : n.toFixed(1);
const fmt2   = n => n==null||isNaN(n) ? "—" : n.toFixed(2);
const fmtPct = n => n==null||isNaN(n) ? "—" : (n*100).toFixed(1)+"%";
const fmtARP = n => n==null||isNaN(n) ? "—" : "$"+n.toFixed(2);

// ── BUILT tab ──────────────────────────────────────────────────────────────
let bFiltered=[...BUILT_DATA], bSortCol="vel_13w_avg", bSortAsc=false;
const bMaxVel = Math.max(...BUILT_DATA.map(r=>r.vel_13w_avg||0));

function bStatsStrip(){{
  const rtl=new Set(bFiltered.map(r=>r.retailer));
  const med=[...bFiltered].sort((a,b)=>(a.vel_13w_avg||0)-(b.vel_13w_avg||0));
  const mv=med.length?med[Math.floor(med.length/2)].vel_13w_avg:0;
  const top=bFiltered[0]||{{}};
  document.getElementById("b-strip").innerHTML=`
    <div class="stat"><div class="val">${{bFiltered.length.toLocaleString()}}</div><div class="lbl">SKU × Retailer series</div></div>
    <div class="stat"><div class="val">${{rtl.size}}</div><div class="lbl">Retailers</div></div>
    <div class="stat"><div class="val">${{fmt2(top.vel_13w_avg)}}</div><div class="lbl">Highest 13wk velocity</div></div>
    <div class="stat"><div class="val">${{fmt2(mv)}}</div><div class="lbl">Median 13wk velocity</div></div>
  `;
}}

function bRenderTable(){{
  const tbody=document.getElementById("b-tbody");
  tbody.innerHTML="";
  const visible=bFiltered.slice(0,500);
  document.getElementById("b-count").textContent=
    `Showing ${{visible.length.toLocaleString()}} of ${{bFiltered.length.toLocaleString()}} series`;
  for(const r of visible){{
    const vel=r.vel_13w_avg||0;
    const bar=bMaxVel>0?(vel/bMaxVel*100):0;
    const sk=`${{r.upc}}|${{r.retailer}}|${{r.channel}}`;
    const tr=document.createElement("tr");
    tr.innerHTML=`
      <td style="min-width:180px">${{r.description||'—'}}</td>
      <td style="font-size:11px;color:var(--muted);white-space:nowrap">${{r.upc||'—'}}</td>
      <td style="font-size:11px;white-space:nowrap">${{r.channel||'—'}}</td>
      <td style="border-right:1px solid var(--border);white-space:nowrap">${{r.retailer||'—'}}</td>
      <td class="num"><div class="vel-cell">${{fmt2(r.vel_13w_avg)}}
        <div class="vel-bar" style="width:${{Math.max(2,bar)}}px"></div></div></td>
      <td class="num">${{fmt2(r.vel_52w_avg)}}</td>
      <td class="num">${{fmt2(r.vel_52w_min)}}</td>
      <td class="num">${{fmt2(r.vel_52w_max)}}</td>
      <td class="num">${{fmt2(r.vel_52w_med)}}</td>
      <td class="num" style="border-right:1px solid var(--border);color:var(--amber)">${{fmt2(r.fct_vel_avg)}}</td>
      <td class="num">${{fmt0(r.avg_base_units)}}</td>
      <td class="num">${{fmt1(r.avg_tdp)}}</td>
      <td class="num">${{fmtARP(r.avg_arp)}}</td>
      <td><canvas class="spark" width="100" height="24" data-key="${{sk}}"></canvas></td>
    `;
    tbody.appendChild(tr);
  }}
  // draw sparklines: solid actual, dashed forecast continuation
  for(const c of tbody.querySelectorAll("canvas.spark")){{
    const d=SPARKS[c.dataset.key];
    if(!d)continue;
    const act=d.actual||[], fct=d.forecast||[];
    const all=[...act,...fct].filter(v=>v!=null);
    if(!all.length)continue;
    const mn=Math.min(...all),mx=Math.max(...all);
    const range=mx-mn||1;
    const ctx=c.getContext("2d");
    ctx.clearRect(0,0,100,24);
    const totalPts=act.length+fct.length;
    const xS=i=>i/(totalPts-1)*98+1;
    const yS=v=>22-(v-mn)/range*20;
    // actual line
    if(act.length>1){{
      ctx.beginPath();ctx.strokeStyle="#58a6ff";ctx.lineWidth=1.5;
      act.forEach((v,i)=>{{if(v!=null){{i===0?ctx.moveTo(xS(i),yS(v)):ctx.lineTo(xS(i),yS(v))}}}});
      ctx.stroke();
    }}
    // forecast dashed
    if(fct.length>1){{
      ctx.beginPath();ctx.strokeStyle="#d29922";ctx.lineWidth=1.5;ctx.setLineDash([3,2]);
      const offset=act.length-1;
      fct.forEach((v,i)=>{{if(v!=null){{
        const x=xS(offset+i);const y=yS(v);
        i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
      }}}});
      ctx.stroke();ctx.setLineDash([]);
    }}
  }}
}}

function bFilter(){{
  const ch=document.getElementById("b-f-ch").value;
  const rt=document.getElementById("b-f-rt").value;
  const q=document.getElementById("b-f-q").value.toLowerCase().trim();
  bFiltered=BUILT_DATA.filter(r=>{{
    if(ch&&r.channel!==ch)return false;
    if(rt&&r.retailer!==rt)return false;
    if(q&&!((r.description||"").toLowerCase().includes(q)||(r.upc||"").includes(q)))return false;
    return true;
  }});
  bSortAndRender();
}}

function bSort(col){{
  if(bSortCol===col){{bSortAsc=!bSortAsc;}}else{{bSortCol=col;bSortAsc=false;}}
  document.querySelectorAll("#b-tbl th[data-col]").forEach(t=>t.classList.remove("sort-asc","sort-desc"));
  const th=document.querySelector(`#b-tbl th[data-col="${{bSortCol}}"]`);
  if(th)th.classList.add(bSortAsc?"sort-asc":"sort-desc");
  bSortAndRender();
}}
function bSortAndRender(){{
  bFiltered.sort((a,b)=>{{
    const av=a[bSortCol]!=null&&!Number.isNaN(a[bSortCol])?a[bSortCol]:(typeof a[bSortCol]==="string"?a[bSortCol]:0);
    const bv=b[bSortCol]!=null&&!Number.isNaN(b[bSortCol])?b[bSortCol]:(typeof b[bSortCol]==="string"?b[bSortCol]:0);
    return typeof av==="number"?(bSortAsc?av-bv:bv-av):(bSortAsc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av)));
  }});
  bStatsStrip();bRenderTable();
}}
function bReset(){{
  ["b-f-ch","b-f-rt"].forEach(id=>document.getElementById(id).value="");
  document.getElementById("b-f-q").value="";
  bFiltered=[...BUILT_DATA];bSortAsc=false;bSortCol="vel_13w_avg";
  bSortAndRender();
}}

function bExport(){{
  const cols=["description","upc","brand","channel","retailer",
              "vel_13w_avg","vel_52w_avg","vel_52w_min","vel_52w_max","vel_52w_med","fct_vel_avg",
              "avg_base_units","avg_tdp","avg_pct_stores","avg_arp"];
  const hdr=["Description","UPC","Brand","Channel","Retailer",
             "Velocity SPM 13wk Avg","Velocity SPM 52wk Avg","Velocity SPM 52wk Min",
             "Velocity SPM 52wk Max","Velocity SPM 52wk Med","Forecast Velocity SPM 13wk Avg",
             "Base Units/wk","Avg TDP","% Stores Selling","ARP"];
  _downloadCSV(bFiltered,cols,hdr,"velocity_built.csv");
}}

// ── Category tab ───────────────────────────────────────────────────────────
let cFiltered=[...CAT_DATA],cSortCol="avg_velocity_spm",cSortAsc=false;
const cMaxVel=Math.max(...CAT_DATA.map(r=>r.avg_velocity_spm||0));

function cStatsStrip(){{
  const brands=new Set(cFiltered.map(r=>r.brand));
  const rtl=new Set(cFiltered.map(r=>r.retailer));
  const med=[...cFiltered].sort((a,b)=>(a.avg_velocity_spm||0)-(b.avg_velocity_spm||0));
  const mv=med.length?med[Math.floor(med.length/2)].avg_velocity_spm:0;
  document.getElementById("c-strip").innerHTML=`
    <div class="stat"><div class="val">${{cFiltered.length.toLocaleString()}}</div><div class="lbl">SKU × Retailer series</div></div>
    <div class="stat"><div class="val">${{brands.size}}</div><div class="lbl">Brands</div></div>
    <div class="stat"><div class="val">${{rtl.size}}</div><div class="lbl">Retailers</div></div>
    <div class="stat"><div class="val">${{fmt2(mv)}}</div><div class="lbl">Median velocity SPM</div></div>
  `;
}}

function cRenderTable(){{
  const tbody=document.getElementById("c-tbody");
  tbody.innerHTML="";
  const visible=cFiltered.slice(0,500);
  document.getElementById("c-count").textContent=
    `Showing ${{visible.length.toLocaleString()}} of ${{cFiltered.length.toLocaleString()}} series`;
  for(const r of visible){{
    const isBuilt=BUILT_BRANDS.has((r.brand||"").toUpperCase());
    const vel=r.avg_velocity_spm||0;
    const bar=cMaxVel>0?(vel/cMaxVel*100):0;
    const tr=document.createElement("tr");
    tr.innerHTML=`
      <td><span class="chip ${{isBuilt?'built':''}}">${{r.brand||'—'}}</span></td>
      <td style="min-width:180px">${{r.description||'—'}}</td>
      <td style="font-size:11px;color:var(--muted)">${{r.upc||'—'}}</td>
      <td style="font-size:11px">${{r.channel||'—'}}</td>
      <td>${{r.retailer||'—'}}</td>
      <td class="num"><div class="vel-cell">${{fmt2(r.avg_velocity_spm)}}
        <div class="vel-bar" style="width:${{Math.max(2,bar)}}px"></div></div></td>
      <td class="num">${{fmt0(r.base_units_13w)}}</td>
      <td class="num">${{fmt1(r.avg_tdp)}}</td>
      <td class="num">${{fmtPct(r.avg_pct_stores)}}</td>
      <td class="num">${{fmtARP(r.avg_arp)}}</td>
    `;
    tbody.appendChild(tr);
  }}
}}

function cFilter(){{
  const br=document.getElementById("c-f-br").value;
  const ch=document.getElementById("c-f-ch").value;
  const rt=document.getElementById("c-f-rt").value;
  const q=document.getElementById("c-f-q").value.toLowerCase().trim();
  cFiltered=CAT_DATA.filter(r=>{{
    if(br&&r.brand!==br)return false;
    if(ch&&r.channel!==ch)return false;
    if(rt&&r.retailer!==rt)return false;
    if(q&&!((r.description||"").toLowerCase().includes(q)||(r.upc||"").includes(q)||(r.brand||"").toLowerCase().includes(q)))return false;
    return true;
  }});
  cSortAndRender();
}}
function cSort(col){{
  if(cSortCol===col){{cSortAsc=!cSortAsc;}}else{{cSortCol=col;cSortAsc=false;}}
  document.querySelectorAll("#c-tbl th[data-col]").forEach(t=>t.classList.remove("sort-asc","sort-desc"));
  const th=document.querySelector(`#c-tbl th[data-col="${{cSortCol}}"]`);
  if(th)th.classList.add(cSortAsc?"sort-asc":"sort-desc");
  cSortAndRender();
}}
function cSortAndRender(){{
  cFiltered.sort((a,b)=>{{
    const av=a[cSortCol]!=null&&!Number.isNaN(a[cSortCol])?a[cSortCol]:(typeof a[cSortCol]==="string"?a[cSortCol]:0);
    const bv=b[cSortCol]!=null&&!Number.isNaN(b[cSortCol])?b[cSortCol]:(typeof b[cSortCol]==="string"?b[cSortCol]:0);
    return typeof av==="number"?(cSortAsc?av-bv:bv-av):(cSortAsc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av)));
  }});
  cStatsStrip();cRenderTable();
}}
function cReset(){{
  ["c-f-br","c-f-ch","c-f-rt"].forEach(id=>document.getElementById(id).value="");
  document.getElementById("c-f-q").value="";
  cFiltered=[...CAT_DATA];cSortAsc=false;cSortCol="avg_velocity_spm";
  cSortAndRender();
}}

function cExport(){{
  const cols=["brand","description","upc","channel","retailer",
              "avg_velocity_spm","base_units_13w","avg_tdp","avg_pct_stores","avg_arp"];
  const hdr=["Brand","Description","UPC","Channel","Retailer",
             "Velocity SPM 13wk Avg","Base Units 13wk Total","Avg TDP","% Stores Selling","ARP"];
  _downloadCSV(cFiltered,cols,hdr,"velocity_category.csv");
}}

function _downloadCSV(data,cols,hdr,filename){{
  const esc=v=>{{
    if(v==null)return "";
    const s=String(v);
    return s.includes(",")||s.includes('"')||s.includes("\\n") ? `"${{s.replace(/"/g,'""')}}"` : s;
  }};
  const rows=[hdr.join(","),...data.map(r=>cols.map(c=>esc(r[c])).join(","))];
  const blob=new Blob(["﻿"+rows.join("\\n")],{{type:"text/csv;charset=utf-8"}});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);a.download=filename;a.click();
}}

function switchTab(name,el){{
  document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
  el.classList.add("active");
  document.getElementById("panel-"+name).classList.add("active");
}}

// init
bSortAndRender();
cSortAndRender();
</script>
"""

html_path = OUT_DIR / "velocity_extract.html"
html_path.write_text(html, encoding="utf-8")
(MOCKUPS_DIR / "velocity_extract.html").write_text(html, encoding="utf-8")
print(f"    outputs/velocity_extract.html")
print(f"    mockups/velocity_extract.html")
print("\nDone.")
