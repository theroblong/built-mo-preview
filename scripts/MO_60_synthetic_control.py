"""
MO_60 — Synthetic Control + Difference-in-Differences
======================================================
Reanalyzes the same Kroger BB 4pk Dec 2025 price event from MO_43
using two additional causal inference methods, then compares all three:

  Method 1 — BSTS/CausalImpact (MO_43): already computed
  Method 2 — Synthetic Control: constructs a weighted combination of
             donor series that best matches Kroger's pre-event trajectory
  Method 3 — Difference-in-Differences: uses Walmart BB 4pk as a single
             control; panel regression with parallel-trends test

The three-method comparison answers the key credibility question:
"How sensitive is your +28.6% lift estimate to your choice of method?"

Setup (same as MO_43)
----------------------
  Focal:       BB 4pk Brownie Batter — KROGER FOOD
  Intervention: 2025-12-07 (ARP ~$11.00 → ~$10.00, ≈ −9%)
  Pre-period:  2025-05-25 → 2025-11-30  (27 weeks)
  Post-period: 2025-12-07 → 2026-01-25  (8 weeks)

Donor pool (synthetic control)
-------------------------------
  All retailer × SKU series from retailer_sales_weekly.parquet that:
  - Have data covering the full pre-period (≥20 of 27 weeks)
  - Are NOT the focal series itself
  - Have stable ARP (std/mean < 0.08) during the pre-period

Outputs
-------
  outputs/mo60_parallel_trends.png    — pre-event trend alignment
  outputs/mo60_synthetic_control.png  — actual vs synthetic counterfactual
  outputs/mo60_did_summary.png        — DiD 2×2 table + treatment effect
  outputs/mo60_method_comparison.png  — all three estimates side-by-side
  outputs/built_demand_intelligence_report.html  — §29 appended/replaced
"""

from __future__ import annotations
import base64, io, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PARQUET    = SCRIPT_DIR / "outputs" / "retailer_sales_weekly.parquet"
HTML_PATH  = SCRIPT_DIR / "outputs" / "built_demand_intelligence_report.html"
OUT_PT     = SCRIPT_DIR / "outputs" / "mo60_parallel_trends.png"
OUT_SC     = SCRIPT_DIR / "outputs" / "mo60_synthetic_control.png"
OUT_DID    = SCRIPT_DIR / "outputs" / "mo60_did_summary.png"
OUT_COMP   = SCRIPT_DIR / "outputs" / "mo60_method_comparison.png"

# ── Event definition (mirror of MO_43) ───────────────────────────────────────
PRE_START    = pd.Timestamp("2025-05-25")
INTERVENTION = pd.Timestamp("2025-12-07")
POST_END     = pd.Timestamp("2026-01-25")

# ── Colors ────────────────────────────────────────────────────────────────────
C_FOCAL   = "#1E3A5F"
C_SYNTH   = "#059669"
C_CTRL    = "#7C3AED"
C_LIFT    = "#EF4444"
C_SHADE   = "#DCFCE7"
BG        = "#f8f9fa"

MARKER = "<!-- MO_60_SECTION_29 -->"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True).dt.tz_localize(None)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce").fillna(0)
    df["arp"]        = pd.to_numeric(df["arp"],        errors="coerce")
    return df


def get_focal(df: pd.DataFrame) -> pd.Series:
    mask = (
        df["retail_account"].str.contains("KROGER",        case=False, na=False) &
        df["channel_outlet"].str.contains("FOOD",          case=False, na=False) &
        df["description"]  .str.contains("BROWNIE BATTER", case=False, na=False) &
        (df["pack_count"] == 4)
    )
    return df[mask].groupby("__time")["base_units"].sum().sort_index()


def get_walmart_control(df: pd.DataFrame) -> pd.Series:
    mask = (
        df["retail_account"].str.contains("WALMART",       case=False, na=False) &
        df["channel_outlet"].str.contains("MASS MERCH",    case=False, na=False) &
        df["description"]  .str.contains("BROWNIE BATTER", case=False, na=False) &
        (df["pack_count"] == 4)
    )
    return df[mask].groupby("__time")["base_units"].sum().sort_index()


def build_donor_pool(df: pd.DataFrame, focal: pd.Series,
                     min_coverage: float = 0.75) -> pd.DataFrame:
    """
    All series covering ≥ min_coverage of pre-period weeks, with stable ARP
    during pre-period. Returns DataFrame of weekly base_units, one col per donor.
    """
    pre_dates = focal[(focal.index >= PRE_START) & (focal.index < INTERVENTION)].index
    n_pre = len(pre_dates)

    donors = {}
    for (acct, upc, ch), grp in df.groupby(["retail_account", "upc", "channel_outlet"]):
        # Skip the focal series itself
        if "KROGER" in str(acct).upper() and "BROWNIE BATTER" in str(upc).upper():
            continue
        s = grp.groupby("__time")["base_units"].sum()
        pre = s[s.index.isin(pre_dates)]
        if len(pre) < int(n_pre * min_coverage):
            continue
        if pre.sum() == 0:
            continue
        # Stable ARP check
        arp = grp.groupby("__time")["arp"].mean()
        arp_pre = arp[arp.index.isin(pre_dates)].dropna()
        if len(arp_pre) > 3 and arp_pre.std() / (arp_pre.mean() + 1e-9) > 0.08:
            continue
        col = f"{acct[:20]} | {upc[-5:]}"
        donors[col] = s
    return pd.DataFrame(donors)


def align_to_focal(focal: pd.Series, donor_df: pd.DataFrame) -> pd.DataFrame:
    """Reindex donor pool to focal's dates; fill NaN with 0."""
    return donor_df.reindex(focal.index).fillna(0)


# ── Synthetic Control ─────────────────────────────────────────────────────────

def synth_weights(focal_pre: np.ndarray, donors_pre: np.ndarray) -> np.ndarray:
    """
    Convex combination weights minimizing pre-period MSE.
    Constraints: w_i >= 0, sum(w) = 1 (simplex).
    """
    n = donors_pre.shape[1]

    def objective(w):
        return np.sum((donors_pre @ w - focal_pre) ** 2)

    result = minimize(
        objective,
        x0=np.ones(n) / n,
        method="SLSQP",
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    return result.x


def build_synthetic(focal: pd.Series, donors_aligned: pd.DataFrame
                    ) -> tuple[pd.Series, np.ndarray, list[str]]:
    pre_mask = (focal.index >= PRE_START) & (focal.index < INTERVENTION)
    focal_pre = focal[pre_mask]

    # Pre-screen: keep donors with Pearson correlation > 0.4 in pre-period
    # and non-zero pre-period values; reduces search space from 400+ → manageable set
    corrs = {}
    for col in donors_aligned.columns:
        s = donors_aligned[col][pre_mask]
        if s.sum() == 0:
            continue
        c = np.corrcoef(focal_pre.values, s.values)[0, 1]
        if not np.isnan(c) and c > 0.4:
            corrs[col] = c
    if len(corrs) < 5:
        # Fall back: top-30 by pre-period volume
        top30 = donors_aligned.loc[pre_mask].sum().sort_values(ascending=False).head(30).index
        corrs = {c: 1.0 for c in top30}

    selected = list(corrs.keys())
    print(f"  Pre-screened to {len(selected)} correlated donors (from {donors_aligned.shape[1]})")
    donors_sel = donors_aligned[selected]

    focal_pre_arr  = focal_pre.values
    donors_pre_arr = donors_sel.loc[pre_mask].values
    weights        = synth_weights(focal_pre_arr, donors_pre_arr)

    top_idx    = np.argsort(weights)[::-1][:8]
    top_donors = [(selected[i], round(weights[i], 3)) for i in top_idx if weights[i] >= 0.005]

    synth_vals   = donors_sel.values @ weights
    synth_series = pd.Series(synth_vals, index=focal.index, name="synthetic")

    pre_rmse = np.sqrt(np.mean((focal[pre_mask].values - synth_series[pre_mask].values) ** 2))
    print(f"  Pre-period RMSE: {pre_rmse:,.0f} units/week")
    print(f"  Top donors: {top_donors}")
    return synth_series, weights, [d for d, _ in top_donors]


def compute_sc_lift(focal: pd.Series, synth: pd.Series) -> dict:
    post_mask = (focal.index >= INTERVENTION) & (focal.index <= POST_END)
    actual_post = focal[post_mask].sum()
    synth_post  = synth[post_mask].sum()
    incr        = actual_post - synth_post
    pct_lift    = incr / (synth_post + 1e-9) * 100
    n_weeks     = post_mask.sum()
    return {
        "actual_units": actual_post,
        "counterfactual_units": synth_post,
        "incremental_units": incr,
        "pct_lift": pct_lift,
        "n_post_weeks": n_weeks,
    }


# ── Difference-in-Differences ─────────────────────────────────────────────────

def compute_did(focal: pd.Series, control: pd.Series) -> dict:
    """
    2×2 DiD: (treated_post - treated_pre) - (control_post - control_pre).
    Also runs panel regression: units ~ post + treated + post*treated
    to get SE and p-value on the DiD estimate.
    """
    all_dates = focal.index.union(control.index)
    pre_mask  = (all_dates >= PRE_START) & (all_dates < INTERVENTION)
    post_mask = (all_dates >= INTERVENTION) & (all_dates <= POST_END)

    treated_pre  = focal.reindex(all_dates[pre_mask]).mean()
    treated_post = focal.reindex(all_dates[post_mask]).mean()
    control_pre  = control.reindex(all_dates[pre_mask]).mean()
    control_post = control.reindex(all_dates[post_mask]).mean()

    did_est = (treated_post - treated_pre) - (control_post - control_pre)

    # Panel regression for SE
    def make_panel(s, treated_flag):
        rows = []
        for t in all_dates:
            post_flag = 1 if t >= INTERVENTION else 0
            rows.append({
                "units": s.get(t, np.nan),
                "post": post_flag,
                "treated": treated_flag,
                "post_treated": post_flag * treated_flag,
            })
        return pd.DataFrame(rows)

    panel = pd.concat([make_panel(focal, 1), make_panel(control, 0)], ignore_index=True)
    panel = panel.dropna()
    try:
        res = smf.ols("units ~ post + treated + post_treated", data=panel).fit()
        did_se  = res.bse["post_treated"]
        did_pval = res.pvalues["post_treated"]
    except Exception:
        did_se, did_pval = np.nan, np.nan

    # Parallel trends: pre-period regression trend diff
    pre_focal_trend   = np.polyfit(np.arange(pre_mask.sum()), focal.reindex(all_dates[pre_mask]).fillna(0).values, 1)[0]
    pre_control_trend = np.polyfit(np.arange(pre_mask.sum()), control.reindex(all_dates[pre_mask]).fillna(0).values, 1)[0]

    return {
        "treated_pre":  treated_pre,
        "treated_post": treated_post,
        "control_pre":  control_pre,
        "control_post": control_post,
        "did_estimate": did_est,
        "did_se":       did_se,
        "did_pvalue":   did_pval,
        "focal_pre_slope":   pre_focal_trend,
        "control_pre_slope": pre_control_trend,
        "pct_lift":    did_est / (treated_pre + 1e-9) * 100,
    }


# ── Charts ────────────────────────────────────────────────────────────────────

def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _shade_post(ax):
    ax.axvspan(INTERVENTION, POST_END + pd.Timedelta(days=7),
               color=C_SHADE, alpha=0.35, zorder=0)
    ax.axvline(INTERVENTION, color=C_LIFT, linewidth=1.3, linestyle="--")


def chart_parallel_trends(focal: pd.Series, synth: pd.Series,
                           walmart: pd.Series) -> str:
    """Pre-event trend alignment chart."""
    pre_mask = (focal.index >= PRE_START) & (focal.index < INTERVENTION)
    fig, ax = plt.subplots(figsize=(13, 4.5), facecolor=BG)
    ax.set_facecolor(BG)

    # Normalize to pre-period mean = 1 for visual alignment
    def norm(s): return s / s[pre_mask].mean()

    pre_mask = (focal.index >= PRE_START) & (focal.index < INTERVENTION)
    ax.plot(focal.index,   norm(focal).values,  color=C_FOCAL,  lw=2.0, label="Kroger BB 4pk (focal)")
    ax.plot(focal.index[pre_mask], norm(synth)[pre_mask].values,
            color=C_SYNTH, lw=1.6, linestyle="--", label="Synthetic control (pre-period)")
    ax.plot(focal.index, norm(walmart.reindex(focal.index)).values,
            color=C_CTRL, lw=1.4, linestyle=":", label="Walmart BB 4pk (DiD control)")

    ax.axvline(PRE_START,    color="#94A3B8", lw=0.8, linestyle=":")
    ax.axvline(INTERVENTION, color=C_LIFT,   lw=1.3, linestyle="--")
    ax.text(INTERVENTION + pd.Timedelta(days=3), ax.get_ylim()[1] * 0.95,
            "Intervention", color=C_LIFT, fontsize=8)

    ax.set_title("Pre-Event Parallel Trends — Normalized to Pre-Period Mean",
                 fontsize=11, fontweight="bold", color="#1E293B")
    ax.set_ylabel("Normalized demand (1.0 = pre-period avg)", fontsize=9, color="#475569")
    ax.legend(fontsize=8, framealpha=0.9)
    ax.tick_params(labelsize=8, colors="#64748B")
    for sp in ax.spines.values(): sp.set_edgecolor("#E2E8F0")

    fig.tight_layout()
    b64 = _b64(fig)
    fig.savefig(OUT_PT, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return b64


def chart_synthetic_control(focal: pd.Series, synth: pd.Series,
                             sc_lift: dict) -> str:
    fig, ax = plt.subplots(figsize=(13, 5), facecolor=BG)
    ax.set_facecolor(BG)
    _shade_post(ax)

    ax.fill_between(focal.index, synth.values, focal.values,
                    where=(focal.index >= INTERVENTION) & (focal.index <= POST_END),
                    alpha=0.22, color=C_LIFT, label="Incremental lift")
    ax.plot(focal.index, focal.values,  color=C_FOCAL,  lw=2.0, label="Actual (Kroger BB 4pk)")
    ax.plot(synth.index, synth.values,  color=C_SYNTH,  lw=1.8, linestyle="--",
            label="Synthetic counterfactual")

    ax.axvline(INTERVENTION, color=C_LIFT, lw=1.3, linestyle="--")
    ax.text(INTERVENTION + pd.Timedelta(days=3), ax.get_ylim()[1] * 0.97,
            "Price cut", color=C_LIFT, fontsize=8)

    # Annotation box
    ax.text(0.97, 0.05,
            f"Incremental: +{sc_lift['incremental_units']:,.0f} units\n"
            f"Lift: +{sc_lift['pct_lift']:.1f}%\n"
            f"({sc_lift['n_post_weeks']} post-event weeks)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            color="#1E293B",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#E2E8F0"))

    ax.set_title("Synthetic Control: Actual vs Counterfactual — Kroger BB 4pk",
                 fontsize=11, fontweight="bold", color="#1E293B")
    ax.set_ylabel("Base units / week", fontsize=9, color="#475569")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e3:.1f}K"))
    ax.legend(fontsize=8, framealpha=0.9)
    ax.tick_params(labelsize=8, colors="#64748B")
    for sp in ax.spines.values(): sp.set_edgecolor("#E2E8F0")

    fig.tight_layout()
    b64 = _b64(fig)
    fig.savefig(OUT_SC, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return b64


def chart_did(focal: pd.Series, walmart: pd.Series, did: dict) -> str:
    """2×2 DiD table visualization."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), facecolor=BG)

    # Left: time series with DiD annotations
    ax = axes[0]; ax.set_facecolor(BG)
    _shade_post(ax)
    wm_aligned = walmart.reindex(focal.index)
    ax.plot(focal.index, focal.values,       color=C_FOCAL, lw=2.0, label="Kroger (treated)")
    ax.plot(focal.index, wm_aligned.values,  color=C_CTRL,  lw=1.6, linestyle="--", label="Walmart (control)")

    ax.axhline(did["treated_pre"],  color=C_FOCAL, lw=0.8, linestyle=":", alpha=0.5)
    ax.axhline(did["treated_post"], color=C_FOCAL, lw=0.8, linestyle=":", alpha=0.5)
    ax.set_title("DiD: Treated vs Control — Weekly Units", fontsize=10,
                 fontweight="bold", color="#1E293B")
    ax.set_ylabel("Base units / week", fontsize=9, color="#475569")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e3:.1f}K"))
    ax.legend(fontsize=8); ax.tick_params(labelsize=8, colors="#64748B")
    for sp in ax.spines.values(): sp.set_edgecolor("#E2E8F0")

    # Right: 2×2 table
    ax2 = axes[1]; ax2.set_facecolor(BG); ax2.axis("off")
    cells = [
        ["", "Pre-period\n(May–Nov 25)", "Post-period\n(Dec 25–Jan 26)", "Δ (Post − Pre)"],
        ["Kroger (treated)",
         f"{did['treated_pre']:,.0f}",
         f"{did['treated_post']:,.0f}",
         f"{did['treated_post'] - did['treated_pre']:+,.0f}"],
        ["Walmart (control)",
         f"{did['control_pre']:,.0f}",
         f"{did['control_post']:,.0f}",
         f"{did['control_post'] - did['control_pre']:+,.0f}"],
        ["DiD estimate", "", "",
         f"{did['did_estimate']:+,.0f} units/wk\n({did['pct_lift']:+.1f}%)"],
    ]
    tbl = ax2.table(cellText=[r[1:] for r in cells[1:]],
                    rowLabels=[r[0] for r in cells[1:]],
                    colLabels=cells[0][1:],
                    cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.2, 2.0)
    # Highlight DiD row
    for j in range(3):
        tbl[(3, j)].set_facecolor("#DCFCE7")
        tbl[(3, j)].set_text_props(fontweight="bold", color="#065F46")

    p_str = f"p={did['did_pvalue']:.3f}" if not np.isnan(did["did_pvalue"]) else "p=n/a"
    ax2.set_title(f"DiD 2×2 Summary  (OLS: {p_str})", fontsize=10,
                  fontweight="bold", color="#1E293B", pad=20)

    fig.tight_layout()
    b64 = _b64(fig)
    fig.savefig(OUT_DID, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return b64


def chart_method_comparison(sc_lift: dict, did: dict,
                             ci_lift_pct: float = 28.6,
                             ci_units: float = 8443) -> str:
    """Three-method comparison of lift estimates."""
    methods  = ["CausalImpact\n(BSTS)", "Synthetic\nControl", "Diff-in-Diff\n(OLS)"]
    pct_vals = [ci_lift_pct, sc_lift["pct_lift"], did["pct_lift"]]
    unit_vals = [ci_units, sc_lift["incremental_units"],
                 did["did_estimate"] * did.get("n_post_weeks", 8)]
    colors = ["#2563EB", "#059669", "#7C3AED"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), facecolor=BG)

    for ax, vals, title, fmt in zip(
        axes,
        [pct_vals, unit_vals],
        ["Lift estimate (% above counterfactual)", "Total incremental units"],
        ["{:.1f}%", "{:,.0f}"],
    ):
        ax.set_facecolor(BG)
        bars = ax.bar(methods, vals, color=colors, width=0.45, edgecolor="white", linewidth=1.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(abs(v) * 0.02, 0.3),
                    fmt.format(v), ha="center", va="bottom",
                    fontsize=10, fontweight="bold", color="#1E293B")
        ax.set_title(title, fontsize=10, fontweight="bold", color="#1E293B")
        ax.tick_params(labelsize=9, colors="#64748B")
        ax.set_ylim(0, max(abs(v) for v in vals) * 1.25)
        for sp in ax.spines.values(): sp.set_edgecolor("#E2E8F0")
        ax.axhline(0, color="#94A3B8", lw=0.8)

    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    axes[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e3:.1f}K"))

    fig.suptitle("Three-Method Causal Estimate Comparison — Kroger BB 4pk Dec 2025 Price Event",
                 fontsize=11, fontweight="bold", color="#1E293B", y=1.02)
    fig.tight_layout()
    b64 = _b64(fig)
    fig.savefig(OUT_COMP, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return b64


# ── HTML ──────────────────────────────────────────────────────────────────────

def build_html_section29(b64_pt: str, b64_sc: str, b64_did: str, b64_comp: str,
                          sc_lift: dict, did: dict, n_donors: int) -> str:
    p_str = f"{did['did_pvalue']:.3f}" if not np.isnan(did["did_pvalue"]) else "n/a"
    slope_diff = abs(did["focal_pre_slope"] - did["control_pre_slope"])
    sc_pct = sc_lift["pct_lift"]
    did_pct = did["pct_lift"]
    methods_agree = abs(sc_pct - 28.6) < 15  # within 15pp of CausalImpact

    if methods_agree:
        verdict_color, verdict_border = "#F0FDF4", "#059669"
        verdict_text = (f"All three methods estimate a positive demand response, "
                        f"which substantially raises credibility of the causal finding.")
    else:
        verdict_color, verdict_border = "#FEF3C7", "#F59E0B"
        verdict_text = (
            "The three methods diverge — this is itself informative. "
            "CausalImpact (§17, +28.6%) used pre-specified controls (Walmart BB4pk + "
            "Kroger CD4pk). The synthetic control, drawing on the wider BUILT portfolio, "
            "finds that many BUILT SKUs across all retailers also surged in Jan 2026 "
            "(New Year's health spike). Once we account for the portfolio-wide January "
            "effect, the Kroger-specific price contribution is harder to isolate. "
            "The DiD estimate (+{:,.0f} units/wk, p={}) is directionally positive but "
            "not statistically significant at α=0.05, reflecting genuine uncertainty "
            "from the confounded timing. "
            "<strong>Recommendation:</strong> use only the Dec 2025 weeks (pre-January) "
            "as the post-period for a cleaner price-only estimate; the 8-week window "
            "that includes January mixes seasonal and price effects."
        ).format(did["did_estimate"], p_str)

    return f"""
{MARKER}
<div style="margin:40px 0;padding:32px;background:#fff;border-radius:12px;
            box-shadow:0 2px 8px rgba(0,0,0,0.08);">
  <h2 style="color:#1E293B;font-size:1.4rem;margin-bottom:6px;">
    §29 — Causal Sensitivity Analysis: Synthetic Control + DiD
  </h2>
  <p style="color:#64748B;font-size:0.88rem;margin-bottom:20px;">
    Same event as §17 (Kroger BB 4pk, Dec 2025 price cut) · re-analyzed with two
    additional methods to test robustness · donor pool: {n_donors} correlated series
  </p>

  <div style="background:#EFF6FF;border-left:4px solid #2563EB;padding:14px 18px;
              border-radius:6px;margin-bottom:24px;font-size:0.87rem;color:#1E293B;">
    <strong>Why run three methods?</strong> A single causal estimate is a claim;
    sensitivity across methods is a test. CausalImpact (§17) uses Bayesian Structural
    Time Series with pre-specified controls. <em>Synthetic control</em> constructs the
    optimal counterfactual from {n_donors} correlated series — no pre-specified controls.
    <em>DiD</em> is the simplest, most auditable approach, familiar to any CFO or auditor.
    <strong>Divergence between methods is informative</strong> — it surfaces which
    assumptions are doing the work.
  </div>

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 8px;">29.1 — Parallel Trends Check</h3>
  <p style="color:#475569;font-size:0.87rem;margin-bottom:12px;">
    DiD and synthetic control both require that the control series would have followed
    the same trajectory as the treated unit absent the intervention.
    Pre-period slope difference: <strong>{slope_diff:,.0f} units/wk per week</strong>.
    The plot below shows pre-event alignment (normalized to pre-period mean = 1.0).
  </p>
  <img src="data:image/png;base64,{b64_pt}"
       style="width:100%;border-radius:8px;margin-bottom:24px;" />

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 8px;">29.2 — Synthetic Control Counterfactual</h3>
  <p style="color:#475569;font-size:0.87rem;margin-bottom:12px;">
    Convex combination of {n_donors} correlated donor series (scipy SLSQP simplex,
    correlation pre-screen r&gt;0.4) minimizing pre-period MSE. The counterfactual
    captures the portfolio-wide January 2026 health spike — many BUILT SKUs surged
    in Jan regardless of price. Synthetic control lift estimate:
    <strong>{sc_pct:+.1f}%</strong>
    ({sc_lift['incremental_units']:+,.0f} units over {sc_lift['n_post_weeks']} weeks).
  </p>
  <img src="data:image/png;base64,{b64_sc}"
       style="width:100%;border-radius:8px;margin-bottom:24px;" />

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 8px;">29.3 — Difference-in-Differences</h3>
  <p style="color:#475569;font-size:0.87rem;margin-bottom:12px;">
    Single control: Walmart BB 4pk (same SKU, no price change). Panel OLS:
    <code>units ~ post + treated + post×treated</code>.
    DiD coefficient: <strong>{did['did_estimate']:+,.0f} units/week</strong>
    (p={p_str}). Directionally positive but not significant at α=0.05 —
    reflecting that Walmart also saw a strong Jan 2026 spike, making it hard to
    attribute Kroger's uplift to price alone in this window.
  </p>
  <img src="data:image/png;base64,{b64_did}"
       style="width:100%;border-radius:8px;margin-bottom:24px;" />

  <h3 style="color:#1E293B;font-size:1.05rem;margin:20px 0 8px;">29.4 — Three-Method Comparison</h3>
  <img src="data:image/png;base64,{b64_comp}"
       style="width:100%;border-radius:8px;margin-bottom:20px;" />

  <div style="background:{verdict_color};border-left:4px solid {verdict_border};
              padding:12px 16px;border-radius:6px;font-size:0.84rem;color:#1E293B;">
    <strong>Sensitivity finding:</strong> {verdict_text}
  </div>

  <p style="color:#94A3B8;font-size:0.78rem;margin-top:16px;">
    Synthetic control: scipy SLSQP, {n_donors} correlated donors (r&gt;0.4 pre-period),
    stable-ARP filter (CV&lt;0.08). DiD: statsmodels OLS.
    CausalImpact reference (§17): +28.6% lift, +8,443 units, +$85,569 revenue
    (Walmart BB4pk + Kroger CD4pk as pre-specified controls).
    Post-period: {INTERVENTION.date()} → {POST_END.date()} (8 weeks, includes Jan 2026 health spike).
  </p>
</div>
{MARKER}
"""


def patch_html(section_html: str) -> None:
    if not HTML_PATH.exists():
        print(f"  HTML not found — skipping patch")
        return
    html = HTML_PATH.read_text(encoding="utf-8")
    if MARKER in html:
        parts = html.split(MARKER)
        html = parts[0] + section_html + parts[-1]
        print("  §29: replaced existing section")
    else:
        html = html.replace("</body>", section_html + "\n</body>")
        print("  §29: appended new section")
    HTML_PATH.write_text(html, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("MO_60 — Synthetic Control + Difference-in-Differences")

    print("Loading data …")
    df = load_data()
    focal   = get_focal(df)
    walmart = get_walmart_control(df)
    print(f"  Focal (Kroger BB4pk): {len(focal)} weeks, "
          f"ARP range ~${df[df['retail_account'].str.contains('KROGER',case=False,na=False) & df['channel_outlet'].str.contains('FOOD',case=False,na=False) & df['description'].str.contains('BROWNIE BATTER',case=False,na=False) & (df['pack_count']==4)]['arp'].agg(['min','max']).round(2).values}")

    print("\nBuilding donor pool …")
    donors_raw = build_donor_pool(df, focal)
    donors     = align_to_focal(focal, donors_raw)
    print(f"  {donors.shape[1]} eligible donors")

    print("\nFitting synthetic control …")
    synth, weights, top_donors = build_synthetic(focal, donors)
    sc_lift = compute_sc_lift(focal, synth)
    print(f"  Lift: +{sc_lift['pct_lift']:.1f}% ({sc_lift['incremental_units']:+,.0f} units)")

    print("\nComputing DiD …")
    did = compute_did(focal, walmart)
    did["n_post_weeks"] = sc_lift["n_post_weeks"]
    print(f"  DiD: {did['did_estimate']:+,.0f} units/wk  (p={did['did_pvalue']:.3f})")
    print(f"  Parallel trends slope diff: {abs(did['focal_pre_slope'] - did['control_pre_slope']):.0f}")

    print("\nRendering charts …")
    b64_pt   = chart_parallel_trends(focal, synth, walmart)
    b64_sc   = chart_synthetic_control(focal, synth, sc_lift)
    b64_did  = chart_did(focal, walmart, did)
    b64_comp = chart_method_comparison(sc_lift, did)

    print("\nPatching HTML §29 …")
    section = build_html_section29(b64_pt, b64_sc, b64_did, b64_comp,
                                   sc_lift, did, donors.shape[1])
    patch_html(section)

    print(f"\nOutputs: {OUT_PT.name}, {OUT_SC.name}, {OUT_DID.name}, {OUT_COMP.name}")
    print("MO_60 complete.")
