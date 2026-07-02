"""MO_49 — Promo gap chart: base units vs. total units, actuals + 13-week forecast.

Reads:
  outputs/retailer_sales_weekly.parquet   (MO_25 — actuals; needs total_units col)
  outputs/retailer_sales_forecast.parquet (MO_27 — needs forecast_total_units_* cols)

For each of the top N series by trailing volume, generates a panel showing:
  • Trailing 52-week actuals:
      – Dark line  = total units (base + promo)
      – Light line = base units (non-promo demand)
      – Shaded gap = historical promo contribution
  • 13-week forecast (right of dashed boundary):
      – Dual q50 lines (dashed) + q10/q90 bands
      – Shaded projected promo gap between the two q50 lines
  • Caveat panel when total_units data is not yet available (re-run MO_25→26→27)

OUTPUT
------
  outputs/mo49_promo_gap_chart.png   — multi-panel PNG (150 dpi)
  outputs/mo49_promo_gap.html        — standalone HTML with embedded chart + framing copy
"""

import base64
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
from pathlib import Path

ACTUALS_PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
FORECAST_PARQUET = Path("outputs/retailer_sales_forecast.parquet")

ACTUALS_WEEKS  = 52
TOP_N          = 6
GROUP_COLS     = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# Color palette
C_TOTAL     = "#1a4f72"   # dark navy — total units line
C_BASE      = "#2e86c1"   # medium blue — base units line
C_PROMO_ACT = "#a9cce3"   # light blue — historical promo gap fill
C_PROMO_FC  = "#f0b27a"   # light orange — projected promo gap fill (forecast region)
C_BAND      = "#85c1e9"   # pale blue — q10/q90 band (base forecast)
C_BAND_T    = "#5d6d7e"   # slate — q10/q90 band (total forecast)
C_BOUND     = "#7f8c8d"   # gray — actuals/forecast boundary line
ALPHA_FILL  = 0.30
ALPHA_BAND  = 0.15


def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _format_k(v, _):
    return f"{v/1000:.0f}K" if v >= 1000 else f"{v:.0f}"


if __name__ == "__main__":
    # ── 1. Load actuals ───────────────────────────────────────────────────────
    print("Loading actuals …")
    df_act = pd.read_parquet(ACTUALS_PARQUET)
    df_act["__time"] = pd.to_datetime(df_act["__time"], utc=True)
    for col in ["base_units", "total_units"]:
        if col in df_act.columns:
            df_act[col] = pd.to_numeric(df_act[col], errors="coerce")
    df_act = df_act.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    has_total_actuals = (
        "total_units" in df_act.columns
        and df_act["total_units"].notna().sum() > 100
    )
    print(f"  Rows: {len(df_act):,} | total_units available: {has_total_actuals}")
    if has_total_actuals:
        cov = df_act["total_units"].notna().mean()
        promo_share = (
            (df_act["total_units"] - df_act["base_units"])
            .clip(lower=0).sum() / df_act["total_units"].fillna(df_act["base_units"]).sum()
        )
        print(f"  total_units coverage: {cov*100:.1f}% | "
              f"portfolio promo share: {promo_share*100:.1f}%")

    # ── 2. Load forecast ──────────────────────────────────────────────────────
    has_forecast       = FORECAST_PARQUET.exists()
    has_total_forecast = False
    df_fc              = None

    if has_forecast:
        print("\nLoading forecast …")
        df_fc = pd.read_parquet(FORECAST_PARQUET)
        df_fc["__time"] = pd.to_datetime(df_fc["__time"], utc=True)
        for col in ["forecast_units_low", "forecast_units_base", "forecast_units_high",
                    "forecast_total_units_low", "forecast_total_units_base", "forecast_total_units_high"]:
            if col in df_fc.columns:
                df_fc[col] = pd.to_numeric(df_fc[col], errors="coerce")
        has_total_forecast = (
            "forecast_total_units_base" in df_fc.columns
            and df_fc["forecast_total_units_base"].notna().any()
        )
        print(f"  Forecast rows: {len(df_fc):,} | total_units forecast: {has_total_forecast}")
    else:
        print(f"\n  {FORECAST_PARQUET} not found — showing actuals only.")

    # ── 3. Select top N series ────────────────────────────────────────────────
    anchor = df_act["__time"].max()
    cutoff = anchor - pd.Timedelta(weeks=ACTUALS_WEEKS)
    trailing_vol = (
        df_act[df_act["__time"] > cutoff]
        .groupby(GROUP_COLS)["base_units"].sum()
        .sort_values(ascending=False)
    )
    top_keys = [dict(zip(GROUP_COLS, k)) for k in trailing_vol.index[:TOP_N]]

    print(f"\nTop {len(top_keys)} series (trailing {ACTUALS_WEEKS}w base units):")
    for i, sk in enumerate(top_keys):
        desc = df_act.loc[
            (df_act["upc"] == sk["upc"]) & (df_act["retail_account"] == sk["retail_account"]),
            "description"
        ]
        label = desc.iloc[0][:38] if len(desc) else sk["upc"][:20]
        print(f"  {i+1}. {label} @ {sk['retail_account']}")

    # ── 4. Chart layout ───────────────────────────────────────────────────────
    ncols = 2
    nrows = (len(top_keys) + 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(17, 5.2 * nrows))
    axes_flat = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx, sk in enumerate(top_keys):
        ax = axes_flat[idx]

        # ── actuals for this series ───────────────────────────────────────────
        act = df_act.copy()
        for col, val in sk.items():
            act = act[act[col] == val]
        act = act[act["__time"] > cutoff].sort_values("__time")

        desc_col = act["description"].iloc[0][:38] if "description" in act.columns and len(act) else sk["upc"][:20]
        panel_title = f"{desc_col} @ {sk['retail_account']}"

        adates = act["__time"].dt.to_pydatetime()
        abase  = act["base_units"].clip(lower=0).fillna(0).values
        atotal = (
            act["total_units"].clip(lower=0).fillna(abase).values
            if has_total_actuals else abase
        )

        # Actuals: total units line (dark) + base units line (lighter)
        ax.plot(adates, atotal, color=C_TOTAL, lw=2.0, label="Total units (actual)")
        ax.plot(adates, abase,  color=C_BASE,  lw=1.4, label="Base units (actual)")
        if has_total_actuals:
            ax.fill_between(adates, abase, atotal,
                            color=C_PROMO_ACT, alpha=ALPHA_FILL + 0.1,
                            label="Promo contribution (actual)")

        # ── boundary ─────────────────────────────────────────────────────────
        ax.axvline(anchor, color=C_BOUND, lw=1.2, linestyle="--", alpha=0.65)
        ax.text(anchor, 0.97, "  Forecast →",
                transform=ax.get_xaxis_transform(),
                fontsize=7.5, color=C_BOUND, va="top", ha="left")

        # ── forecast ─────────────────────────────────────────────────────────
        if has_forecast and df_fc is not None:
            fc = df_fc.copy()
            for col, val in sk.items():
                fc = fc[fc[col] == val]
            fc = fc.sort_values("__time")

            if len(fc) > 0:
                fdates  = fc["__time"].dt.to_pydatetime()
                fb_q50  = fc["forecast_units_base"].clip(lower=0).values
                fb_q10  = fc["forecast_units_low"].clip(lower=0).values  if "forecast_units_low"  in fc.columns else fb_q50
                fb_q90  = fc["forecast_units_high"].clip(lower=0).values if "forecast_units_high" in fc.columns else fb_q50

                # Base units forecast
                ax.plot(fdates, fb_q50, color=C_BASE, lw=1.6, linestyle="--",
                        label="Base units (forecast q50)")
                ax.fill_between(fdates, fb_q10, fb_q90,
                                color=C_BAND, alpha=ALPHA_BAND, label="Base q10–q90")

                if has_total_forecast:
                    ft_q50 = fc["forecast_total_units_base"].clip(lower=0).values
                    ft_q10 = fc["forecast_total_units_low"].clip(lower=0).values  if "forecast_total_units_low"  in fc.columns else ft_q50
                    ft_q90 = fc["forecast_total_units_high"].clip(lower=0).values if "forecast_total_units_high" in fc.columns else ft_q50

                    # Total units forecast
                    ax.plot(fdates, ft_q50, color=C_TOTAL, lw=2.0, linestyle="--",
                            label="Total units (forecast q50)")
                    ax.fill_between(fdates, ft_q10, ft_q90,
                                    color=C_BAND_T, alpha=ALPHA_BAND)

                    # Projected promo gap
                    ax.fill_between(fdates, fb_q50, ft_q50,
                                    color=C_PROMO_FC, alpha=ALPHA_FILL,
                                    label="Projected promo contribution")
                else:
                    ax.text(0.97, 0.50,
                            "Re-run MO_25→26→27\nfor total units forecast",
                            transform=ax.transAxes, ha="right", va="center",
                            fontsize=7, color="#7f8c8d",
                            bbox=dict(boxstyle="round,pad=0.4", fc="white",
                                      ec="#bdc3c7", alpha=0.9))

        # ── axes styling ──────────────────────────────────────────────────────
        ax.set_title(panel_title, fontsize=9, fontweight="bold", pad=5)
        ax.set_ylabel("Units / week", fontsize=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_format_k))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="y", alpha=0.25, lw=0.5)
        ax.set_xlim(left=cutoff)
        ax.legend(fontsize=6.5, loc="upper left", framealpha=0.85)

    # Hide unused panels
    for i in range(len(top_keys), len(axes_flat)):
        axes_flat[i].set_visible(False)

    fig.suptitle(
        "Base Units vs. Total Units — Historical Promo Contribution + 13-Week Forecast",
        fontsize=12, fontweight="bold", y=1.005,
    )
    plt.tight_layout(h_pad=3.0)

    # ── 5. Save PNG ───────────────────────────────────────────────────────────
    out_png = Path("outputs/mo49_promo_gap_chart.png")
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"\n  Saved PNG → {out_png}")

    # ── 6. Build standalone HTML ──────────────────────────────────────────────
    img_b64 = _fig_to_base64(fig)
    plt.close(fig)

    # Status pill to show in header
    if has_total_actuals and has_total_forecast:
        status_color, status_text = "#27ae60", "Full data — actuals + forecast"
    elif has_total_actuals:
        status_color, status_text = "#f39c12", "Actuals only — re-run MO_26/27 for forecast"
    else:
        status_color, status_text = "#e74c3c", "Base units only — re-run MO_25→26→27"

    caveat_block = ""
    if not has_total_actuals:
        caveat_block = """
        <div class="callout warn">
          <strong>Missing data:</strong> <code>total_units</code> column not found in
          <code>outputs/retailer_sales_weekly.parquet</code>.
          Re-run <strong>MO_25</strong> to pull <code>units_promo</code> from
          <code>built_filtered_weekly</code> and compute total units. Then re-run
          MO_26 and MO_27 to train the total-units models and generate the dual forecast.
        </div>"""
    elif not has_total_forecast:
        caveat_block = """
        <div class="callout warn">
          <strong>Partial forecast:</strong> <code>forecast_total_units_*</code> columns
          absent from <code>outputs/retailer_sales_forecast.parquet</code>.
          Re-run <strong>MO_26</strong> (trains <code>model_total_units_*</code>)
          then <strong>MO_27</strong> to add the total-units forecast lines.
          Historical promo gap (left of boundary) is based on actuals and is correct.
        </div>"""

    promo_note = ""
    if has_total_actuals:
        overall_share = (
            (df_act["total_units"] - df_act["base_units"])
            .clip(lower=0).sum()
            / df_act["total_units"].fillna(df_act["base_units"]).sum()
        ) * 100
        promo_note = f"Portfolio-wide historical promo share: <strong>{overall_share:.1f}%</strong> of total scan volume."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MO_49 — Promo Gap Chart</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 1140px; margin: 36px auto; padding: 0 24px; color: #1c1c1e;
    background: #f9f9f9;
  }}
  h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 2px; color: #0d1117; }}
  .meta {{ color: #636366; font-size: 12px; margin-bottom: 20px; }}
  .status {{ display: inline-block; background: {status_color}1a; color: {status_color};
             border: 1px solid {status_color}55; border-radius: 20px;
             padding: 2px 10px; font-size: 11px; font-weight: 600; margin-left: 10px; }}
  .callout {{
    padding: 12px 16px; border-radius: 6px; font-size: 13px; margin-bottom: 18px;
    line-height: 1.6;
  }}
  .callout.info {{ background: #eaf4fb; border-left: 4px solid #2980b9; }}
  .callout.warn {{ background: #fef9e7; border-left: 4px solid #f39c12; }}
  img {{ width: 100%; border-radius: 8px; border: 1px solid #dde1e7;
         box-shadow: 0 2px 12px rgba(0,0,0,0.07); }}
  .caption {{ font-size: 11px; color: #8e8e93; margin-top: 8px; text-align: center; }}
  .legend-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 14px 0; font-size: 12px; }}
  .swatch {{ display: inline-block; width: 28px; height: 10px;
             border-radius: 3px; vertical-align: middle; margin-right: 5px; }}
</style>
</head>
<body>

<h1>Base Units vs. Total Units: Promo Contribution
  <span class="status">{status_text}</span>
</h1>
<p class="meta">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} &nbsp;·&nbsp; MO_49
  &nbsp;·&nbsp; Top {TOP_N} series by trailing {ACTUALS_WEEKS}-week volume
</p>

{caveat_block}

<div class="callout info">
  <p><strong>How to read:</strong>
    The <strong style="color:{C_TOTAL}">dark line</strong> is total scan volume (base + promo units).
    The <strong style="color:{C_BASE}">lighter line</strong> is base units — everyday demand with promotional
    mechanics removed.
    The <span style="background:{C_PROMO_ACT};padding:2px 6px;border-radius:3px">blue shaded gap</span>
    is historical promo contribution: volume that only existed because of
    TPR, display, or feature activity.
    In the forecast region the gap becomes
    <span style="background:{C_PROMO_FC};padding:2px 6px;border-radius:3px">orange-shaded</span>
    and represents projected promo contribution based on historical patterns — not a planned trade calendar.</p>
  {"<p>" + promo_note + "</p>" if promo_note else ""}
  <p><strong>Key question for Chase:</strong>
    How much of our volume depends on being on deal, and where is that ratio changing?
    A widening gap = growing promo dependence. A narrowing gap = everyday demand strengthening.</p>
</div>

<img src="data:image/png;base64,{img_b64}"
     alt="Base vs. Total Units Promo Gap Chart — {TOP_N} top series">

<p class="caption">
  Each panel: 52-week actuals (left of dashed line) + 13-week forecast (right).
  Forecast lines are q50 medians; shaded bands are q10–q90.
  Base units model: <code>model_retailer_sales_q*_v3.pkl</code>.
  Total units model: <code>model_total_units_q*_v3.pkl</code>.
</p>

</body>
</html>"""

    out_html = Path("outputs/mo49_promo_gap.html")
    out_html.write_text(html, encoding="utf-8")
    print(f"  Saved HTML → {out_html}")

    print("\nDone.")
    print(f"  Open in browser: outputs/mo49_promo_gap.html")
    if not has_total_actuals:
        print("\n  Next: re-run MO_25 → MO_26 → MO_27 to populate total_units and dual forecast.")
    elif not has_total_forecast:
        print("\n  Next: re-run MO_26 → MO_27 to train total_units models and add forecast gap.")
