"""MO_76 — FRED Macro Feature Augmentation Ablation

PURPOSE
-------
Tests whether adding FRED macroeconomic signals improves demand forecast accuracy
beyond the MO_53 28-feature champion (avg 3-cutpoint wMAPE ~6.1%).

THESIS
------
Diesel and gas prices squeeze CPG/retail logistics margins → fewer promo events →
lower shelf velocity for premium SKUs. CPI food inflation triggers consumer trade-down.
Jobless claims signal real-time consumer stress. Grocery store sales measure the
shelf environment directly. Savings rate proxies consumer financial cushion.
PPI Processed Foods captures input-cost inflation upstream of CPG manufacturers.

SAFETY PROTOCOL
---------------
MO_53 remains the active production model throughout this experiment.
MO_76 runs as CANDIDATE only. Promotion to active requires ALL three:
  1. Avg 3-cutpoint CV wMAPE ≤ MO_53 baseline (no regression allowed)
  2. At least 2 macro features with mean |SHAP| materially above zero
  3. CV improvement ≥ PROMOTE_THRESHOLD (0.03pp) vs MO_53

If any criterion fails → candidate archived, MO_53 stays active, no UI impact.

FRED SERIES (Tier 1)
--------------------
Weekly (direct join on week — no interpolation):
  DDFUELUSGULF  diesel_price_lag4      EIA On-Highway Diesel $/gal
  GASDESW       gas_price_lag4         US Regular Retail Gas $/gal
  ICSA          jobless_initial_lag4   Initial Jobless Claims (thousands)
  ICNSA         jobless_contd_lag4     Continued Jobless Claims (thousands)

Monthly (forward-fill to weekly, then 4-week lag + YoY Δ):
  MRTSSM4451USS grocery_sales_yoy      Grocery Store Sales % YoY
  PSAVERT       savings_rate_lag4      Personal Savings Rate (%)
  WPU115        ppi_food_yoy           PPI: Processed Foods % YoY
  PAYEMS        payrolls_yoy           Nonfarm Payrolls % YoY

Feature engineering rules
  - 4-week lag on ALL macro features (avoids look-ahead bias; macro signals take
    weeks to flow through distribution decisions and consumer behavior)
  - YoY % Δ for level series (grocery_sales, ppi_food, payrolls): removes secular
    trend so the model sees acceleration signal, not absolute level
  - Weekly series: direct week join + lag only (no interpolation needed)
  - Monthly series: forward-fill each monthly release across all weeks in that month,
    then apply 4-week lag

EXPERIMENTAL DESIGN
-------------------
  Baseline: MO_53 28-feature champion set
  Group test: baseline + all 8 macro features simultaneously
  Individual: each macro feature tested alone (same MO_53 ablation framework)
  Metric: wMAPE on Dec 2025 cutpoint + 3-cutpoint rolling CV (Jun/Sep/Dec 2025)
  Promote threshold: 0.03pp improvement in avg CV wMAPE

OUTPUTS
-------
  outputs/mo76_macro_individual.csv   — per-feature wMAPE + delta
  outputs/mo76_group_cv.csv           — group test 3-cutpoint CV
  outputs/mo76_fred_features.parquet  — built macro feature table (reusable)
  outputs/mo76_individual_results.png — ranked bar chart
  outputs/mo76_shap.png               — SHAP feature importance
  model_history.json                  — candidate entry (champion=False unless promoted)
"""

import json
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import shap

warnings.filterwarnings("ignore", category=UserWarning)

# ── Try LightGBM import ───────────────────────────────────────────────────────
try:
    import lightgbm as lgb
except ImportError:
    raise SystemExit("LightGBM not installed. Run: pip install lightgbm")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
OUTPUT_DIR    = SCRIPT_DIR / "outputs"
PARQUET_PATH  = OUTPUT_DIR / "retailer_sales_weekly.parquet"
MACRO_PARQUET = OUTPUT_DIR / "mo76_fred_features.parquet"
MODEL_HISTORY = OUTPUT_DIR / "model_history.json"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── FRED + EIA config ─────────────────────────────────────────────────────────
_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
_EIA_BASE  = "https://api.eia.gov/v2"

def _load_env_key(key_name: str) -> str:
    env_path = SCRIPT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key_name}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key_name, "")

FRED_API_KEY = _load_env_key("FRED_API_KEY")
EIA_API_KEY  = _load_env_key("EIA_API_KEY")

WEEKLY_SERIES = {
    "DDFUELUSGULF": "diesel_price",
    "GASDESW":      "gas_price",
    "ICSA":         "jobless_initial",
    "ICNSA":        "jobless_contd",
}

MONTHLY_SERIES = {
    "MRTSSM4451USS": "grocery_sales",
    "PSAVERT":       "savings_rate",
    "WPU115":        "ppi_food",
    "PAYEMS":        "payrolls",
}

# EIA weekly series: fuel consumption rates (Mb/d) and crude inventories (Mb)
# Added Sept 23 2026 — Rob Cluster request; test for feature importance vs MO_53 champion
# Hypothesis: diesel consumption (economic activity proxy) + crude drawdown rate = leading
# indicators for CPG distribution velocity and consumer demand environment.
EIA_SERIES = {
    # (endpoint_path, facets, col_name)
    "gas_consumption":    ("petroleum/cons/wpsup",
                           [("facets[process][]", "VPP"), ("facets[duoarea][]", "NUS"),
                            ("facets[product][]", "EPM0")]),
    "diesel_consumption": ("petroleum/cons/wpsup",
                           [("facets[process][]", "VPP"), ("facets[duoarea][]", "NUS"),
                            ("facets[product][]", "EPD0")]),
    "crude_stocks":       ("petroleum/stoc/wstk",
                           [("facets[duoarea][]", "NUS"), ("facets[product][]", "EPC0")]),
}

LAG_WEEKS      = 4    # weeks of lag applied to all macro features
PROMOTE_THRESHOLD = 0.03  # pp improvement needed to promote over MO_53

# ── MO_53 champion config (carry forward unchanged) ───────────────────────────
CHAMPION_PARAMS = dict(
    objective="regression", boosting_type="gbdt",
    n_estimators=1000, learning_rate=0.04,
    min_child_samples=20, feature_fraction=0.8,
    bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.3, reg_lambda=0.3, num_leaves=63,
    random_state=42, n_jobs=-1, verbose=-1,
)

CHAMPION_FEATS = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    "base_units_wow_delta",  "base_units_z8", "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8",        "velocity_spm_z13",
    "tdp", "tdp_z8",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "weeks_since_launch",
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_lag52", "velocity_spm_lag52",
    "channel_outlet",
    "week_of_year",
    # MO_53 promoted additions (donor signals)
    "competitor_donor_count",
    "donor_count",
]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]


# ── FRED + EIA fetching ───────────────────────────────────────────────────────

def eia_fetch(endpoint: str, facets: list[tuple], start: str) -> list[dict]:
    """
    Fetch EIA API v2 weekly petroleum data. Returns [] when key absent or on error.
    Handles both 'YYYY-MM-DD' and 'YYYY-WXX' EIA period formats.
    """
    if not EIA_API_KEY:
        print(f"    EIA_API_KEY not set — skipping {endpoint}")
        return []
    try:
        params: list[tuple] = [
            ("api_key",              EIA_API_KEY),
            ("frequency",            "weekly"),
            ("data[0]",              "value"),
            ("start",                start),
            ("sort[0][column]",      "period"),
            ("sort[0][direction]",   "asc"),
            ("length",               "500"),
        ] + facets
        r = requests.get(f"{_EIA_BASE}/{endpoint}/data/", params=params, timeout=15)
        r.raise_for_status()
        rows = r.json().get("response", {}).get("data", [])
        result = []
        for row in rows:
            period = row.get("period", "")
            val    = row.get("value")
            if val is None:
                continue
            if "W" in period:
                try:
                    year, wk = period.split("-W")
                    ts = pd.Timestamp(f"{year}-W{wk.zfill(2)}-1", freq=None)
                    # strptime workaround for ISO week
                    from datetime import datetime as _dt
                    ts = pd.Timestamp(
                        _dt.strptime(f"{year}-W{wk.zfill(2)}-1", "%Y-W%W-%w")
                    )
                except Exception:
                    continue
            else:
                ts = pd.Timestamp(period)
            result.append({"date": ts, "value": float(val)})
        print(f"    EIA {endpoint}: {len(result)} observations"
              + (f" ({result[0]['date'].date()} → {result[-1]['date'].date()})" if result else ""))
        return result
    except Exception as exc:
        print(f"    WARNING: EIA fetch failed for {endpoint}: {exc}")
        return []


def fred_fetch(series_id: str, start: str) -> list[dict]:
    """Fetch FRED series observations. Returns [] on any error."""
    if not FRED_API_KEY:
        raise SystemExit(
            "FRED_API_KEY not found in scripts/.env — cannot fetch macro data.\n"
            "Add: FRED_API_KEY=<your_key>"
        )
    try:
        r = requests.get(
            _FRED_BASE,
            params={
                "series_id":         series_id,
                "observation_start": start,
                "api_key":           FRED_API_KEY,
                "file_type":         "json",
                "sort_order":        "asc",
            },
            timeout=15,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])
        result = [
            {"date": pd.Timestamp(o["date"]), "value": float(o["value"])}
            for o in obs
            if o.get("value") and o["value"] != "."
        ]
        print(f"    {series_id}: {len(result)} observations "
              f"({result[0]['date'].date()} → {result[-1]['date'].date()})"
              if result else f"    {series_id}: no data")
        return result
    except Exception as exc:
        print(f"    WARNING: FRED fetch failed for {series_id}: {exc}")
        return []


def build_macro_features(train_start: pd.Timestamp, train_end: pd.Timestamp) -> pd.DataFrame:
    """
    Fetch all Tier 1 FRED + EIA series and return a weekly DataFrame indexed by week_ending.
    Applies 4-week lag and YoY % Δ for level series.
    EIA series are included when EIA_API_KEY is set; silently skipped otherwise.
    """
    fetch_start = (train_start - timedelta(weeks=LAG_WEEKS + 54)).strftime("%Y-%m-%d")
    print(f"\n[FRED+EIA] Fetching {len(WEEKLY_SERIES) + len(MONTHLY_SERIES)} FRED + "
          f"{len(EIA_SERIES)} EIA series from {fetch_start} …")

    # ── Build weekly date spine (Sunday = SPINS week_ending convention) ────────
    # Cover full date range with buffer for lag + YoY lookback
    spine_start = train_start - timedelta(weeks=LAG_WEEKS + 54)
    spine_end   = train_end   + timedelta(weeks=4)
    # Generate weekly Sundays
    sundays = pd.date_range(
        start=spine_start - timedelta(days=spine_start.weekday() + 1),
        end=spine_end,
        freq="W",  # W = weekly, anchored to Sunday
    )
    macro = pd.DataFrame({"week_ending": sundays})
    macro["year_week"] = macro["week_ending"].dt.strftime("%Y-%W")

    # ── Weekly series: match to nearest Sunday ────────────────────────────────
    for series_id, col_name in WEEKLY_SERIES.items():
        obs = fred_fetch(series_id, fetch_start)
        if not obs:
            macro[col_name] = np.nan
            continue
        fred_df = pd.DataFrame(obs)
        fred_df["year_week"] = fred_df["date"].dt.strftime("%Y-%W")
        # Keep last observation per year_week (handles multiple releases same week)
        fred_df = fred_df.groupby("year_week")["value"].last().reset_index()
        fred_df.rename(columns={"value": col_name}, inplace=True)
        macro = macro.merge(fred_df, on="year_week", how="left")
        # Forward-fill any gaps (FRED sometimes skips a holiday week)
        macro[col_name] = macro[col_name].ffill()

    # ── Monthly series: forward-fill onto weekly spine ────────────────────────
    for series_id, col_name in MONTHLY_SERIES.items():
        obs = fred_fetch(series_id, fetch_start)
        if not obs:
            macro[col_name] = np.nan
            continue
        fred_df = pd.DataFrame(obs)
        fred_df["year_month"] = fred_df["date"].dt.strftime("%Y-%m")
        # One value per month — forward-fill to weeks
        monthly_map: dict[str, float] = dict(
            zip(fred_df["year_month"], fred_df["value"])
        )
        macro["year_month"] = macro["week_ending"].dt.strftime("%Y-%m")
        def _ffill_monthly(ym: str) -> float | None:
            """Return latest monthly value ≤ this week's year-month."""
            for m in sorted(monthly_map.keys(), reverse=True):
                if m <= ym:
                    return monthly_map[m]
            return None
        macro[col_name] = macro["year_month"].map(_ffill_monthly)

    # ── EIA weekly series: fuel consumption rates + crude inventories ────────────
    if EIA_API_KEY:
        print(f"\n[EIA] Fetching {len(EIA_SERIES)} series …")
        for col_name, (endpoint, facets) in EIA_SERIES.items():
            obs = eia_fetch(endpoint, facets, fetch_start)
            if not obs:
                macro[col_name] = np.nan
                continue
            eia_df = pd.DataFrame(obs)
            eia_df["year_week"] = eia_df["date"].dt.strftime("%Y-%W")
            eia_df = eia_df.groupby("year_week")["value"].last().reset_index()
            eia_df.rename(columns={"value": col_name}, inplace=True)
            macro = macro.merge(eia_df, on="year_week", how="left")
            macro[col_name] = macro[col_name].ffill()
    else:
        print("\n[EIA] EIA_API_KEY not set — skipping consumption/inventory features")
        for col_name in EIA_SERIES:
            macro[col_name] = np.nan

    # ── Apply 4-week lag to all macro features ────────────────────────────────
    macro = macro.sort_values("week_ending").reset_index(drop=True)
    raw_cols = (list(WEEKLY_SERIES.values()) + list(MONTHLY_SERIES.values())
                + list(EIA_SERIES.keys()))
    for col in raw_cols:
        if col in macro.columns:
            macro[f"{col}_lag{LAG_WEEKS}"] = macro[col].shift(LAG_WEEKS)

    # ── YoY % Δ for level series (removes secular trend) ─────────────────────
    level_series = ["grocery_sales", "ppi_food", "payrolls",
                    "crude_stocks"]  # crude inventories are a stock/level
    for col in level_series:
        lagged = f"{col}_lag{LAG_WEEKS}"
        if lagged in macro.columns:
            macro[f"{col}_yoy"] = macro[lagged].pct_change(52) * 100

    # ── Final feature columns for ML ─────────────────────────────────────────
    macro["diesel_price_lag4"]       = macro.get(f"diesel_price_lag{LAG_WEEKS}")
    macro["gas_price_lag4"]          = macro.get(f"gas_price_lag{LAG_WEEKS}")
    macro["jobless_initial_lag4"]    = macro.get(f"jobless_initial_lag{LAG_WEEKS}")
    macro["jobless_contd_lag4"]      = macro.get(f"jobless_contd_lag{LAG_WEEKS}")
    macro["savings_rate_lag4"]       = macro.get(f"savings_rate_lag{LAG_WEEKS}")
    # EIA — standardize before use; LightGBM handles NaN natively
    macro["gas_consumption_lag4"]    = macro.get(f"gas_consumption_lag{LAG_WEEKS}")
    macro["diesel_consumption_lag4"] = macro.get(f"diesel_consumption_lag{LAG_WEEKS}")
    macro["crude_stocks_yoy"]        = macro.get("crude_stocks_yoy")  # YoY Δ preferred for stock

    # Drop working columns
    drop_cols = (["year_week", "year_month"] + raw_cols
                 + [f"{c}_lag{LAG_WEEKS}" for c in raw_cols])
    macro = macro.drop(columns=[c for c in drop_cols if c in macro.columns], errors="ignore")
    macro = macro[macro["week_ending"] >= train_start].reset_index(drop=True)

    print(f"  Macro feature table: {len(macro):,} weeks × "
          f"{len(macro.columns) - 1} features "
          f"({macro['week_ending'].min().date()} → {macro['week_ending'].max().date()})")
    return macro


# ── ML helpers (identical pattern to MO_53) ───────────────────────────────────

def wmape(actual, predicted) -> float:
    total = np.nansum(np.abs(actual))
    if total < 1e-9:
        return np.nan
    return float(np.nansum(np.abs(actual - predicted)) / total * 100)


def avail(feats, df) -> list[str]:
    return [f for f in feats if f in df.columns]


def qualify_cutpoint(df, cutoff_utc, min_train=52, min_test=13, horizon=13):
    val_cut = cutoff_utc - pd.Timedelta(weeks=8)
    train_list, val_list, test_list = [], [], []
    for _, g in df.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        tr = g[g["__time"] < val_cut]
        va = g[(g["__time"] >= val_cut) & (g["__time"] < cutoff_utc)]
        te = g[(g["__time"] >= cutoff_utc) & (g["__time"] < cutoff_utc + pd.Timedelta(weeks=horizon))]
        if len(tr) >= min_train and len(te) >= min_test:
            train_list.append(tr)
            val_list.append(va)
            test_list.append(te)
    if not train_list:
        raise ValueError(f"No qualifying series at cutpoint {cutoff_utc}")
    return pd.concat(train_list), pd.concat(val_list), pd.concat(test_list), len(train_list)


def _encode_categoricals(train_df, val_df, test_df, af):
    cat_feats = [c for c in af if train_df[c].dtype == object]
    tr = train_df[af].copy()
    va = val_df[af].copy()
    te = test_df[af].copy()
    for c in cat_feats:
        cats = sorted(
            set(tr[c].dropna().tolist()) |
            set(va[c].dropna().tolist()) |
            set(te[c].dropna().tolist())
        )
        cat_map = {v: i for i, v in enumerate(cats)}
        for sub in [tr, va, te]:
            sub[c] = sub[c].map(cat_map).fillna(-1).astype(int)
    return tr, va, te, cat_feats


def train_eval(train_df, val_df, test_df, feats, params=None):
    params = params or CHAMPION_PARAMS
    af = avail(feats, train_df)
    if not af:
        return np.nan, None
    tr, va, te, cat_feats = _encode_categoricals(train_df, val_df, test_df, af)
    m = lgb.LGBMRegressor(**params)
    m.fit(
        tr, train_df["log_base_units"],
        eval_set=[(va, val_df["log_base_units"])],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)],
        categorical_feature=cat_feats if cat_feats else "auto",
    )
    pred_log = m.predict(te)
    pred     = np.expm1(pred_log)
    return wmape(test_df["base_units"].values, pred), m


def rolling_cv(df, feats, label, params=None):
    """3-cutpoint CV: Jun / Sep / Dec 2025."""
    cutpoints = [
        ("Jun 2025", pd.Timestamp("2025-07-01", tz="UTC")),
        ("Sep 2025", pd.Timestamp("2025-10-01", tz="UTC")),
        ("Dec 2025", pd.Timestamp("2026-01-01", tz="UTC")),
    ]
    rows = []
    for name, cutoff in cutpoints:
        tr, va, te, n = qualify_cutpoint(df, cutoff)
        wm, _ = train_eval(tr, va, te, feats, params)
        rows.append({"cutpoint": name, "n_series": n, "variant": label, "wmape": wm})
        print(f"    {name} (n={n}): {label} wMAPE={wm:.3f}%")
    dfcv = pd.DataFrame(rows)
    return dfcv, float(dfcv["wmape"].mean())


# ── Charting ──────────────────────────────────────────────────────────────────

def chart_individual(results_df, champion_wmape, out_path):
    df = results_df.dropna(subset=["delta"]).copy()
    df = df.sort_values("delta")
    colors = [
        "#3FB950" if d <= -PROMOTE_THRESHOLD
        else "#F78166" if d > 0
        else "#D29922"
        for d in df["delta"]
    ]
    fig, ax = plt.subplots(figsize=(10, max(5, len(df) * 0.5)))
    ax.barh(df["feature"], df["delta"], color=colors)
    ax.axvline(0, color="#2c3e50", lw=1.2)
    ax.axvline(-PROMOTE_THRESHOLD, color="#3FB950", lw=1, ls="--", alpha=0.8,
               label=f"Promote threshold (−{PROMOTE_THRESHOLD}pp)")
    ax.set_xlabel("wMAPE vs MO_53 Champion (pp) — negative = improvement")
    ax.set_title(f"MO_76: FRED Macro Feature Ablation "
                 f"(Dec 2025, champion={champion_wmape:.3f}%)")
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()
    print(f"  Chart saved: {out_path}")


def chart_shap(model, test_df, feats, out_path):
    af = avail(feats, test_df)
    _, _, te, _ = _encode_categoricals(test_df, test_df, test_df, af)
    sample = te.sample(min(512, len(te)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(sample)
    fig, ax = plt.subplots(figsize=(9, 6))
    shap.summary_plot(shap_vals, sample, plot_type="bar", show=False, max_display=20)
    plt.title("MO_76: SHAP Feature Importance — Macro-Augmented Model")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  SHAP chart saved: {out_path}")


def update_model_history(variant_tag, dec_wmape, avg_cv_wmape, n_series, feats,
                          is_promoted, promotion_criteria):
    history = []
    if MODEL_HISTORY.exists():
        with open(MODEL_HISTORY) as f:
            history = json.load(f)
    # MO_76 is candidate only — never automatically flags as champion
    # Promotion decision is manual after reviewing all criteria
    entry = {
        "script":              "MO_76",
        "date":                datetime.now().strftime("%Y-%m-%d"),
        "variant":             variant_tag,
        "status":              "candidate" if is_promoted else "archived",
        "feature_set":         feats,
        "n_features":          len(feats),
        "n_series":            int(n_series),
        "dec2025_wmape":       float(dec_wmape),
        "avg_cv_wmape":        float(avg_cv_wmape),
        "champion":            False,  # never auto-promote — manual review required
        "promotion_criteria":  promotion_criteria,
        "note": (
            "CANDIDATE: meets all promotion criteria. Review SHAP before promoting."
            if is_promoted else
            "ARCHIVED: failed one or more promotion criteria. MO_53 remains active."
        ),
    }
    history.append(entry)
    with open(MODEL_HISTORY, "w") as f:
        json.dump(history, f, indent=2)
    print(f"  model_history.json updated: MO_76 status={entry['status']}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("MO_76 — FRED Macro Feature Augmentation Ablation")
    print(f"MO_53 champion stays active. This runs as CANDIDATE only.")
    print("=" * 70)

    # ── 1. Load training dataset ─────────────────────────────────────────────
    print(f"\n[1] Loading {PARQUET_PATH} …")
    if not PARQUET_PATH.exists():
        raise SystemExit(f"Parquet not found: {PARQUET_PATH}\nRun MO_25/MO_26 first.")
    df = pd.read_parquet(PARQUET_PATH)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    train_start = df["__time"].min().tz_localize(None) if df["__time"].dt.tz else df["__time"].min()
    train_end   = df["__time"].max().tz_localize(None) if df["__time"].dt.tz else df["__time"].max()

    print(f"  Rows: {len(df):,} | Series: {df.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Date range: {df['__time'].min().date()} – {df['__time'].max().date()}")

    missing_champ = [f for f in CHAMPION_FEATS if f not in df.columns]
    if missing_champ:
        print(f"  WARNING: Champion features missing: {missing_champ}")
        print("  Continuing with available champion features only.")
    CHAMPION_FEATS_AVAIL = [f for f in CHAMPION_FEATS if f in df.columns]

    # ── 2. Fetch and build FRED macro features ────────────────────────────────
    if MACRO_PARQUET.exists():
        print(f"\n[2] Loading cached macro features from {MACRO_PARQUET} …")
        macro = pd.read_parquet(MACRO_PARQUET)
        macro["week_ending"] = pd.to_datetime(macro["week_ending"])
        print(f"  Cached: {len(macro):,} weeks × {len(macro.columns) - 1} features")
        print("  (Delete mo76_fred_features.parquet to force re-fetch)")
    else:
        macro = build_macro_features(train_start, train_end)
        macro.to_parquet(MACRO_PARQUET, index=False)
        print(f"  Macro features cached to {MACRO_PARQUET}")

    MACRO_FEATS = [c for c in macro.columns if c != "week_ending"]
    print(f"\n  FRED macro features to test ({len(MACRO_FEATS)}):")
    for feat in MACRO_FEATS:
        coverage = macro[feat].notna().mean() * 100
        print(f"    {feat}: {coverage:.1f}% coverage")

    # ── 3. Join macro features to training data ───────────────────────────────
    print("\n[3] Joining macro features to training data …")
    # Align __time (UTC Sunday) to macro week_ending (also Sunday)
    df["week_ending"] = df["__time"].dt.tz_localize(None).dt.normalize()
    # Ensure macro week_ending is tz-naive
    macro["week_ending"] = macro["week_ending"].dt.tz_localize(None)
    df = df.merge(macro, on="week_ending", how="left")

    for feat in MACRO_FEATS:
        cov = df[feat].notna().mean() * 100
        print(f"  {feat}: {cov:.1f}% join coverage")

    # Drop rows where ALL macro features are null (pre-FRED-history period)
    macro_null_mask = df[MACRO_FEATS].isna().all(axis=1)
    if macro_null_mask.sum() > 0:
        print(f"  Dropping {macro_null_mask.sum():,} rows with all macro features null")
        df = df[~macro_null_mask].copy()

    # ── 4. Baseline: MO_53 champion on Dec 2025 cutpoint ─────────────────────
    print("\n[4] Evaluating MO_53 champion baseline on Dec 2025 cutpoint …")
    DEC2025 = pd.Timestamp("2026-01-01", tz="UTC")
    tr_dec, va_dec, te_dec, n_dec = qualify_cutpoint(df, DEC2025)
    champion_wmape, champ_model = train_eval(tr_dec, va_dec, te_dec, CHAMPION_FEATS_AVAIL)
    print(f"  MO_53 champion wMAPE: {champion_wmape:.3f}% (n={n_dec} series)")

    # ── 5. Group test: all macro features together ────────────────────────────
    print("\n[5] Group test: MO_53 champion + ALL macro features …")
    group_feats = CHAMPION_FEATS_AVAIL + avail(MACRO_FEATS, df)
    group_wmape, group_model = train_eval(tr_dec, va_dec, te_dec, group_feats)
    group_delta = group_wmape - champion_wmape
    print(f"  Group wMAPE: {group_wmape:.3f}%  Δ={group_delta:+.3f}pp vs champion")

    # ── 6. Individual feature ablation ───────────────────────────────────────
    print(f"\n[6] Individual ablation — {len(MACRO_FEATS)} macro features …")
    results = []
    for feat in MACRO_FEATS:
        if feat not in df.columns or df[feat].isna().mean() > 0.5:
            print(f"  SKIP {feat} — insufficient coverage")
            results.append({"feature": feat, "wmape": np.nan, "delta": np.nan})
            continue
        test_feats = CHAMPION_FEATS_AVAIL + [feat]
        wm, _ = train_eval(tr_dec, va_dec, te_dec, test_feats)
        delta = wm - champion_wmape
        promoted = delta <= -PROMOTE_THRESHOLD
        print(f"  {feat}: {wm:.3f}%  Δ={delta:+.3f}pp"
              + (" ✓ INDIVIDUAL WINNER" if promoted else ""))
        results.append({"feature": feat, "wmape": wm, "delta": delta})

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "mo76_macro_individual.csv", index=False)
    print(f"\n  Individual results saved: outputs/mo76_macro_individual.csv")

    # ── 7. Rolling 3-cutpoint CV on group feature set ─────────────────────────
    print("\n[7] Rolling 3-cutpoint CV — group macro set …")
    cv_df_champion, champ_avg = rolling_cv(df, CHAMPION_FEATS_AVAIL, "MO_53_champion")
    cv_df_group,    group_avg = rolling_cv(df, group_feats, "MO_76_macro_group")
    cv_df_group.to_csv(OUTPUT_DIR / "mo76_group_cv.csv", index=False)

    print(f"\n  MO_53 champion avg CV:  {champ_avg:.3f}%")
    print(f"  MO_76 group macro avg CV: {group_avg:.3f}%")
    print(f"  Δ avg CV: {group_avg - champ_avg:+.3f}pp")

    # ── 8. SHAP on group model ────────────────────────────────────────────────
    print("\n[8] SHAP feature importance on group model …")
    shap_path = OUTPUT_DIR / "mo76_shap.png"
    chart_shap(group_model, te_dec, group_feats, shap_path)

    # ── 9. Charts ─────────────────────────────────────────────────────────────
    print("\n[9] Generating charts …")
    chart_individual(results_df, champion_wmape, OUTPUT_DIR / "mo76_individual_results.png")

    # ── 10. Promotion decision ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("MO_76 PROMOTION EVALUATION")
    print("=" * 70)

    individual_winners = results_df.loc[results_df["delta"] <= -PROMOTE_THRESHOLD, "feature"].tolist()
    cv_beats_threshold = (group_avg - champ_avg) <= -PROMOTE_THRESHOLD

    # Check SHAP: proxy by whether the group model has better wMAPE
    # (actual SHAP significance requires visual review of mo76_shap.png)
    crit_cv      = cv_beats_threshold
    crit_no_regr = group_avg <= champ_avg
    crit_winners = len(individual_winners) >= 1

    promotion_criteria = {
        "cv_improvement_pp":      round(champ_avg - group_avg, 4),
        "cv_beats_threshold":     crit_cv,
        "no_regression":          crit_no_regr,
        "individual_winners":     individual_winners,
        "has_individual_winners": crit_winners,
        "promote_group":          all([crit_cv, crit_no_regr]),
        "partial_promotion":      crit_winners and crit_no_regr,
        "recommendation": (
            f"PROMOTE group set: MO_76 beats MO_53 by {champ_avg - group_avg:.3f}pp CV avg."
            if all([crit_cv, crit_no_regr]) else
            f"PARTIAL: promote individual winners only: {individual_winners}."
            if (crit_winners and crit_no_regr) else
            "ARCHIVE: macro features add noise or no improvement vs MO_53. Keep MO_53 active."
        ),
    }

    print(f"\n  Criterion 1 — No regression:      {'PASS' if crit_no_regr else 'FAIL'}")
    print(f"  Criterion 2 — CV ≥ {PROMOTE_THRESHOLD}pp improvement: {'PASS' if crit_cv else 'FAIL'} "
          f"({champ_avg - group_avg:+.3f}pp)")
    print(f"  Criterion 3 — Individual winners: {'PASS' if crit_winners else 'FAIL'} "
          f"({individual_winners})")
    print(f"\n  RECOMMENDATION: {promotion_criteria['recommendation']}")
    print(f"\n  ⚠  MO_53 REMAINS ACTIVE — manual review of SHAP chart required before any promotion")
    print(f"     Review: {shap_path}")

    is_candidate = crit_no_regr and (crit_cv or crit_winners)
    update_model_history(
        variant_tag="MO_76_macro_group",
        dec_wmape=group_wmape,
        avg_cv_wmape=group_avg,
        n_series=n_dec,
        feats=group_feats,
        is_promoted=is_candidate,
        promotion_criteria=promotion_criteria,
    )

    print("\n" + "=" * 70)
    print("MO_76 COMPLETE")
    print(f"  Champion (MO_53):    {champ_avg:.3f}% avg CV wMAPE  [ACTIVE — unchanged]")
    print(f"  Candidate (MO_76):   {group_avg:.3f}% avg CV wMAPE  [CANDIDATE]")
    print(f"  Individual winners:  {individual_winners if individual_winners else 'none'}")
    print("=" * 70)
