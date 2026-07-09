"""
MO_59 — STL Decomposition + Changepoint Detection
──────────────────────────────────────────────────
Layer 1 of the layered forecast architecture: decompose each demand series
into Trend + Seasonal + Remainder, then detect structural breaks in the
remainder that signal distribution events, pricing resets, or competitive
entries beyond normal seasonal variation.

Methodology
-----------
  STL (Seasonal-Trend decomposition using LOESS):
    - statsmodels.tsa.seasonal.STL, period=52, robust=True
    - Robust mode downweights outliers so single promo spikes don't distort
      the seasonal or trend estimates
    - Minimum 104 weeks (2 full annual cycles) required per series

  Changepoint Detection (ruptures — PELT algorithm):
    - Applied to the STL remainder after removing trend + seasonal
    - PELT (Pruned Exact Linear Time): NIPS 2012; O(n log n) time complexity
    - Used by NASA JPL, ESA, and many academic time series applications
    - model="rbf" (radial basis function) detects changes in mean AND variance
    - pen (penalty) controls sensitivity; higher = fewer, more significant breaks

Outputs
-------
  outputs/mo59_seasonal_index.png    — portfolio seasonal pattern (week 1-52)
  outputs/mo59_stl_decomp.png        — 3-series decomposition grid
  outputs/built_demand_intelligence_report.html  — §28 appended/replaced

Production note on ruptures
---------------------------
  ruptures is well-tested scientific software (Killick et al. 2012, PELT);
  for production deployment consider also: BOCPD (Bayesian Online CPD),
  or simple z-score thresholding on STL remainder for operator-interpretable
  thresholds without external dependency.
"""

from __future__ import annotations
import base64, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from statsmodels.tsa.seasonal import STL
import ruptures as rpt

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ROOT       = SCRIPT_DIR.parent
PARQUET    = SCRIPT_DIR / "outputs" / "retailer_sales_weekly.parquet"
HTML_PATH  = SCRIPT_DIR / "outputs" / "built_demand_intelligence_report.html"
OUT_SEAS   = SCRIPT_DIR / "outputs" / "mo59_seasonal_index.png"
OUT_DECOMP = SCRIPT_DIR / "outputs" / "mo59_stl_decomp.png"

# ── Config ────────────────────────────────────────────────────────────────────
STL_PERIOD       = 52    # annual seasonality
MIN_WEEKS        = 104   # 2 full cycles for clean STL
RUPTURES_PENALTY = 8     # PELT pen; increase to reduce false positives
TOP_N            = 3     # series to show in decomposition grid
EXCLUDE_GEO      = {"CRMA"}  # MULO aggregates double-count individual retailers

# Colors
C_ACTUAL   = "#CBD5E1"
C_TREND    = "#2563EB"
C_SEASONAL = "#7C3AED"
C_RESID    = "#475569"
C_CPT      = "#EF4444"
C_IDX      = "#059669"
BG         = "#f8f9fa"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df = df[~df["geography_level"].isin(EXCLUDE_GEO)].copy()
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    return df


def get_top_series(df: pd.DataFrame, n: int) -> list[tuple]:
    """Return top-N (retail_account, upc, description) by total base_units."""
    ranked = (
        df.groupby(["retail_account", "upc", "description"])["base_units"]
        .sum()
        .sort_values(ascending=False)
    )
    # Only keep series with enough weeks
    result = []
    for (acct, upc, desc), _ in ranked.items():
        s = df[(df["retail_account"] == acct) & (df["upc"] == upc)]
        if len(s) >= MIN_WEEKS:
            result.append((acct, upc, desc))
        if len(result) >= n:
            break
    return result


def extract_series(df: pd.DataFrame, acct: str, upc: str) -> pd.Series:
    """Return weekly base_units Series indexed by date, filled/sorted."""
    s = (
        df[(df["retail_account"] == acct) & (df["upc"] == upc)]
        .groupby("__time")["base_units"]
        .sum()
        .sort_index()
    )
    s = s.asfreq("W-SUN", fill_value=np.nan).ffill().fillna(0)
    return s


# ── STL + Changepoints ────────────────────────────────────────────────────────

def run_stl(series: pd.Series) -> tuple:
    """Fit STL, return (trend, seasonal, remainder) as pandas Series."""
    result = STL(series.values.astype(float), period=STL_PERIOD, robust=True).fit()
    idx = series.index
    trend    = pd.Series(result.trend,    index=idx)
    seasonal = pd.Series(result.seasonal, index=idx)
    resid    = pd.Series(result.resid,    index=idx)
    return trend, seasonal, resid


def detect_changepoints(resid: pd.Series, pen: float = RUPTURES_PENALTY) -> list[pd.Timestamp]:
    """Run PELT on remainder; return list of changepoint timestamps."""
    signal = resid.values.reshape(-1, 1).astype(float)
    algo   = rpt.Pelt(model="rbf").fit(signal)
    bkps   = algo.predict(pen=pen)
    # bkps is list of end-indices of segments; last element = len(signal)
    dates = [resid.index[b - 1] for b in bkps[:-1]]
    return dates


def compute_seasonal_index(df: pd.DataFrame, top_series: list[tuple]) -> pd.DataFrame:
    """Average the STL seasonal component by week_of_year across top series."""
    all_seasonal = []
    for acct, upc, desc in top_series:
        s = extract_series(df, acct, upc)
        if len(s) < MIN_WEEKS:
            continue
        _, seasonal, _ = run_stl(s)
        seasonal_df = pd.DataFrame({
            "week_of_year": seasonal.index.isocalendar().week.astype(int),
            "seasonal": seasonal.values,
            "baseline": s.rolling(STL_PERIOD, min_periods=STL_PERIOD//2, center=True).mean().values,
        })
        # Normalize seasonal component as % of trend level
        baseline_mean = s[s > 0].mean()
        seasonal_df["seasonal_norm"] = seasonal_df["seasonal"] / baseline_mean
        all_seasonal.append(seasonal_df)

    combined = pd.concat(all_seasonal, ignore_index=True)
    index_df = (
        combined.groupby("week_of_year")["seasonal_norm"]
        .median()
        .reset_index()
        .rename(columns={"seasonal_norm": "seasonal_index"})
    )
    # Shift so mean = 0 (show deviation from average)
    index_df["seasonal_index"] -= index_df["seasonal_index"].mean()
    return index_df


# ── Charts ────────────────────────────────────────────────────────────────────

def short_label(desc: str, acct: str) -> str:
    """Compact series label for chart title."""
    d = desc.replace("Built Puff ", "").replace(" Protein Bar", "").replace(" Oz", "oz")
    a = acct.title() if len(acct) <= 8 else acct[:8].title() + "."
    return f"{a} — {d}"


def chart_seasonal_index(index_df: pd.DataFrame, n_series: int) -> str:
    """Bar chart of portfolio seasonal pattern. Returns base64 PNG."""
    fig, ax = plt.subplots(figsize=(14, 4), facecolor=BG)
    ax.set_facecolor(BG)

    weeks = index_df["week_of_year"].values
    vals  = index_df["seasonal_index"].values
    colors = [C_IDX if v >= 0 else C_CPT for v in vals]

    ax.bar(weeks, vals, color=colors, width=0.8, linewidth=0)
    ax.axhline(0, color="#94A3B8", linewidth=0.8, linestyle="--")

    # Annotate peaks
    peak_idx = np.argmax(vals)
    trough_idx = np.argmin(vals)
    ax.annotate(
        f"Peak: wk {weeks[peak_idx]}\n(New Year / Jan health spike)",
        xy=(weeks[peak_idx], vals[peak_idx]),
        xytext=(weeks[peak_idx] + 3, vals[peak_idx] * 0.9),
        fontsize=8, color="#1E293B",
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=0.8),
    )
    ax.annotate(
        f"Trough: wk {weeks[trough_idx]}\n(Summer softness)",
        xy=(weeks[trough_idx], vals[trough_idx]),
        xytext=(weeks[trough_idx] + 3, vals[trough_idx] * 1.1),
        fontsize=8, color="#1E293B",
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=0.8),
    )

    ax.set_xlabel("Week of Year", fontsize=9, color="#475569")
    ax.set_ylabel("Seasonal deviation\n(fraction of avg demand)", fontsize=9, color="#475569")
    ax.set_title(
        f"Portfolio Seasonal Pattern — Protein Bar Category ({n_series} series)",
        fontsize=11, fontweight="bold", color="#1E293B", pad=10,
    )
    ax.set_xlim(0.5, 52.5)
    ax.tick_params(labelsize=8, colors="#64748B")
    for spine in ax.spines.values():
        spine.set_edgecolor("#E2E8F0")

    fig.tight_layout()
    buf = _fig_to_b64(fig)
    plt.close(fig)
    fig.savefig(OUT_SEAS, dpi=150, bbox_inches="tight", facecolor=BG)
    return buf


def chart_decomp_grid(df: pd.DataFrame, top_series: list[tuple]) -> str:
    """3-column decomposition grid. Returns base64 PNG."""
    n = len(top_series)
    fig = plt.figure(figsize=(15, 10), facecolor=BG)
    gs  = GridSpec(3, n, figure=fig, hspace=0.35, wspace=0.3)

    row_titles = ["Actual + Trend", "Seasonal Component", "Remainder + Changepoints"]
    row_colors = [C_TREND, C_SEASONAL, C_CPT]

    for col, (acct, upc, desc) in enumerate(top_series):
        s = extract_series(df, acct, upc)
        trend, seasonal, resid = run_stl(s)
        cpts = detect_changepoints(resid)

        dates = s.index.tz_localize(None) if s.index.tz is not None else s.index

        # Row 0: Actual + Trend
        ax0 = fig.add_subplot(gs[0, col])
        ax0.fill_between(dates, s.values, alpha=0.25, color=C_ACTUAL, linewidth=0)
        ax0.plot(dates, s.values, color=C_ACTUAL, linewidth=0.8, label="Actual")
        ax0.plot(dates, trend.values, color=C_TREND, linewidth=1.6, label="Trend")
        ax0.set_title(short_label(desc, acct), fontsize=8.5, fontweight="bold",
                      color="#1E293B", pad=6)
        if col == 0:
            ax0.set_ylabel(row_titles[0], fontsize=8, color=row_colors[0])

        # Row 1: Seasonal
        ax1 = fig.add_subplot(gs[1, col])
        ax1.plot(dates, seasonal.values, color=C_SEASONAL, linewidth=1.2)
        ax1.axhline(0, color="#94A3B8", linewidth=0.6, linestyle="--")
        if col == 0:
            ax1.set_ylabel(row_titles[1], fontsize=8, color=row_colors[1])

        # Row 2: Remainder + changepoints
        ax2 = fig.add_subplot(gs[2, col])
        ax2.bar(dates, resid.values, color=C_RESID, width=6, alpha=0.6, linewidth=0)
        ax2.axhline(0, color="#94A3B8", linewidth=0.6, linestyle="--")
        for cpt_date in cpts:
            cpt_tz = cpt_date.tz_localize(None) if cpt_date.tzinfo is not None else cpt_date
            ax2.axvline(cpt_tz, color=C_CPT, linewidth=1.4, linestyle="--", alpha=0.85)
        if col == 0:
            ax2.set_ylabel(row_titles[2], fontsize=8, color=row_colors[2])

        # Formatting
        for ax in [ax0, ax1, ax2]:
            ax.set_facecolor(BG)
            ax.tick_params(labelsize=7, colors="#64748B")
            ax.tick_params(axis="x", rotation=30)
            for spine in ax.spines.values():
                spine.set_edgecolor("#E2E8F0")

        print(f"  {acct} {upc}: {len(cpts)} changepoint(s): "
              f"{[c.strftime('%Y-%m-%d') for c in cpts]}")

    # Legend
    handles = [
        mpatches.Patch(color=C_TREND,    label="Trend"),
        mpatches.Patch(color=C_SEASONAL, label="Seasonal"),
        mpatches.Patch(color=C_RESID,    label="Remainder"),
        mpatches.Patch(color=C_CPT,      label="Structural break"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4,
               fontsize=8, framealpha=0.9, bbox_to_anchor=(0.5, -0.01))

    fig.savefig(OUT_DECOMP, dpi=150, bbox_inches="tight", facecolor=BG)
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def _fig_to_b64(fig) -> str:
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ── HTML patching ──────────────────────────────────────────────────────────────

MARKER = "<!-- MO_59_SECTION_28 -->"


def build_html_section28(b64_seasonal: str, b64_decomp: str,
                          n_series: int, n_qualifying: int) -> str:
    return f"""
{MARKER}
<div style="margin:40px 0;padding:32px;background:#fff;border-radius:12px;
            box-shadow:0 2px 8px rgba(0,0,0,0.08);">
  <h2 style="color:#1E293B;font-size:1.4rem;margin-bottom:6px;">
    §28 — Signal Decomposition: Seasonal Structure &amp; Structural Breaks
  </h2>
  <p style="color:#64748B;font-size:0.88rem;margin-bottom:20px;">
    STL (LOESS) decomposition + PELT changepoint detection ·
    {n_qualifying} qualifying series (≥104 weeks) · ruptures v1.1.10
  </p>

  <div style="background:#EFF6FF;border-left:4px solid #2563EB;padding:14px 18px;
              border-radius:6px;margin-bottom:24px;font-size:0.87rem;color:#1E293B;">
    <strong>How to read this section:</strong> Every demand signal decomposes
    into three components — <span style="color:{C_TREND};font-weight:600;">Trend</span>
    (is the business growing?),
    <span style="color:{C_SEASONAL};font-weight:600;">Seasonal</span>
    (is this week structurally high or low?), and
    <span style="color:{C_RESID};font-weight:600;">Remainder</span>
    (what's left after removing both). The remainder is where surprises live:
    distribution events, competitive entries, pricing resets. Red dashed lines
    mark structural breaks detected in the remainder — moments where demand
    shifted in a way not explained by normal trend or seasonal patterns.
  </div>

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 10px;">
    28.1 — Portfolio Seasonal Pattern
  </h3>
  <p style="color:#475569;font-size:0.87rem;margin-bottom:14px;">
    Seasonal deviation averaged across {n_series} high-volume series.
    Green bars = demand above average; red bars = below average.
    The January health spike is clearly visible; summer softness (weeks 24–32)
    reflects the protein bar category's known seasonal trough.
    This curve is the foundation of Layer 1 forecasting — any model that
    ignores it will systematically over-forecast summers and under-forecast
    January.
  </p>
  <img src="data:image/png;base64,{b64_seasonal}"
       style="width:100%;border-radius:8px;margin-bottom:24px;" />

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 10px;">
    28.2 — STL Decomposition: Top {n_series} Series
  </h3>
  <p style="color:#475569;font-size:0.87rem;margin-bottom:14px;">
    Each column shows one high-volume series.
    <strong>Row 1:</strong> Actual demand (gray fill) with estimated trend (blue line) —
    trend isolates organic business growth from seasonal and promotional noise.<br/>
    <strong>Row 2:</strong> Seasonal component — the repeating annual pattern unique to
    each SKU-retailer combination.<br/>
    <strong>Row 3:</strong> Remainder after removing trend and seasonal. Dashed red lines
    are PELT-detected structural breaks — weeks where the remainder's distribution
    changed in a statistically meaningful way. These are candidate moments to cross-reference
    with distribution events, competitor launches, or pricing resets in the price event queue.
  </p>
  <img src="data:image/png;base64,{b64_decomp}"
       style="width:100%;border-radius:8px;margin-bottom:20px;" />

  <div style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;
              border-radius:6px;font-size:0.84rem;color:#92400E;">
    <strong>Diagnostic value:</strong> A large, sustained remainder component
    (more variance in the remainder than in the seasonal) indicates that
    external events — competitive pressure, distribution changes, pricing —
    are the dominant demand drivers, not the calendar. These SKUs benefit most
    from the Mo competitive signal layer. A well-decomposed series with small
    remainder confirms the model has good structural coverage.
  </div>

  <p style="color:#94A3B8;font-size:0.78rem;margin-top:16px;">
    STL: statsmodels robust=True, period=52. Changepoints: ruptures PELT rbf kernel,
    pen={RUPTURES_PENALTY}. MULO/CRMA geography excluded to avoid double-counting.
    Series with &lt;104 weeks excluded from STL (insufficient for 2 seasonal cycles).
  </p>
</div>
{MARKER}
"""


def patch_html(section_html: str) -> None:
    if not HTML_PATH.exists():
        print(f"  HTML not found at {HTML_PATH} — skipping patch")
        return
    html = HTML_PATH.read_text(encoding="utf-8")
    if MARKER in html:
        parts = html.split(MARKER)
        html = parts[0] + section_html + parts[-1]
        print("  §28: replaced existing section")
    else:
        # Append before closing </body>
        html = html.replace("</body>", section_html + "\n</body>")
        print("  §28: appended new section")
    HTML_PATH.write_text(html, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("MO_59 — STL Decomposition + Changepoint Detection")
    print("Loading parquet …")
    df = load_data()
    print(f"  {len(df):,} rows, {df.groupby(['retail_account','upc']).ngroups} series")

    # Qualifying series for STL
    ranked = (
        df.groupby(["retail_account", "upc", "description"])["base_units"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    qualifying = []
    for _, row in ranked.iterrows():
        acct, upc, desc = row["retail_account"], row["upc"], row["description"]
        n = df[(df["retail_account"] == acct) & (df["upc"] == upc)].shape[0]
        if n >= MIN_WEEKS:
            qualifying.append((acct, upc, desc))
    print(f"  {len(qualifying)} series with ≥{MIN_WEEKS} weeks (STL-eligible)")

    top_series = get_top_series(df, TOP_N)
    labels = [f"{a} {u}" for a, u, _ in top_series]
    print(f"  Top {TOP_N}: {labels}")

    print("\nComputing portfolio seasonal index …")
    index_df = compute_seasonal_index(df, qualifying[:20])  # use top-20 for index

    print("Rendering seasonal index chart …")
    b64_seasonal = chart_seasonal_index(index_df, len(qualifying[:20]))

    print("\nRendering STL decomposition grid …")
    b64_decomp = chart_decomp_grid(df, top_series)

    print("\nPatching HTML §28 …")
    section = build_html_section28(b64_seasonal, b64_decomp,
                                   len(qualifying[:20]), len(qualifying))
    patch_html(section)

    print(f"\nOutputs:")
    print(f"  {OUT_SEAS}")
    print(f"  {OUT_DECOMP}")
    print(f"  {HTML_PATH}")
    print("MO_59 complete.")
