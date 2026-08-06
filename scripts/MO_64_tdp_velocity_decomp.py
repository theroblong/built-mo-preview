"""MO_64 — Layer 2: TDP × velocity decomposition.

Decomposes demand change into two independent drivers:
  • Distribution (TDP) — how many doors carry the product
  • Velocity — how much each door sells (base_units per TDP point)

Identity: base_units ≈ TDP × velocity_per_tdp
Change decomposition (Laspeyres mid-point):
  Δunits = Δtdp × v_mid + Δvel × t_mid   (cross-term ignored; small)

INPUTS
------
  outputs/retailer_sales_weekly.parquet  (MO_25)
  outputs/retailer_sales_forecast.parquet  (MO_27)

OUTPUT TABLE: retailer_sales_tdp_velocity (Druid)
--------------------------------------------------
One row per (upc, retail_account, channel_outlet, geography_raw).

Historical attribution (13w vs 52w-ago):
  hist_delta_units      — absolute change in avg weekly units vs year ago
  hist_tdp_contrib      — units change attributed to TDP shift
  hist_vel_contrib      — units change attributed to velocity shift
  hist_tdp_contrib_pct  — % of total |change| from TDP
  hist_vel_contrib_pct  — % of total |change| from velocity

Forward attribution (13w forecast vs anchor):
  fwd_delta_units       — forecast avg units − anchor units
  fwd_tdp_contrib       — forward units change from projected TDP shift
  fwd_vel_contrib       — forward units change from implied velocity shift
  fwd_tdp_contrib_pct   — % of total |forward change| from TDP
  fwd_vel_contrib_pct   — % of total |forward change| from velocity

Summary:
  growth_driver         — TDP_DRIVEN / VELOCITY_DRIVEN / MIXED / STABLE / DECLINING
  growth_driver_detail  — human-readable phrase (e.g. "65% TDP, 35% velocity")
  hist_tdp_last13w_avg  — recent avg TDP (context)
  hist_vel_last13w_avg  — recent avg velocity index
  anchor_units          — launch-anchor units/wk from MO_27
  forecast_units_base   — 13w avg q50 forecast units/wk
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mo_writeback import write_back

SCRIPT_DIR = Path(__file__).parent
MIN_WEEKS_HIST = 26   # need at least 26w to compare recent vs year-ago
MIN_WEEKS_HIST_FULL = 52  # ideal: 52w for true year-ago comparison
MIN_TDP = 0.1         # floor to avoid division by zero in vel_index
CHANGE_FLOOR = 5.0    # units/wk below this → STABLE (noise floor)
DOMINANT_THRESH = 0.60  # one driver must explain 60%+ of change to be named


def _safe_div(a, b, fill=0.0):
    return a / b if b > CHANGE_FLOOR else fill


def decompose_series(rows: pd.DataFrame, fcast_rows: pd.DataFrame) -> dict | None:
    """Compute TDP × velocity decomposition for one (upc, account, channel, geo) series."""
    rows = rows.sort_values("__time")
    if len(rows) < MIN_WEEKS_HIST:
        return None

    # Velocity index: units per TDP point
    tdp_s = rows["tdp"].clip(lower=MIN_TDP)
    vel = rows["base_units"] / tdp_s

    n = len(rows)
    window = min(13, n // 2)

    recent = rows.tail(window)
    t_now = recent["tdp"].clip(lower=MIN_TDP).mean()
    v_now = vel.tail(window).mean()
    u_now = recent["base_units"].mean()

    # Historical comparison: year-ago vs now
    if n >= MIN_WEEKS_HIST_FULL:
        # True 52w-ago window
        ago_rows = rows.iloc[max(0, n - 65): max(0, n - 52)]
    else:
        # Use first-half of available history
        ago_rows = rows.head(window)

    if len(ago_rows) < 4:
        return None

    t_ago = ago_rows["tdp"].clip(lower=MIN_TDP).mean()
    v_ago = (ago_rows["base_units"] / ago_rows["tdp"].clip(lower=MIN_TDP)).mean()
    u_ago = ago_rows["base_units"].mean()

    # Mid-point Laspeyres decomposition
    t_mid = (t_now + t_ago) / 2
    v_mid = (v_now + v_ago) / 2

    delta_t = t_now - t_ago
    delta_v = v_now - v_ago
    delta_u = u_now - u_ago

    hist_tdp_contrib = delta_t * v_mid
    hist_vel_contrib = delta_v * t_mid
    denom_hist = abs(hist_tdp_contrib) + abs(hist_vel_contrib)

    if denom_hist > 0:
        hist_tdp_pct = 100 * hist_tdp_contrib / denom_hist
        hist_vel_pct = 100 * hist_vel_contrib / denom_hist
    else:
        hist_tdp_pct = hist_vel_pct = 0.0

    # Forward attribution: forecast vs anchor
    fwd_tdp_contrib = fwd_vel_contrib = fwd_delta_u = 0.0
    fwd_tdp_pct = fwd_vel_pct = 0.0
    anchor_units = forecast_units_base = float("nan")

    if fcast_rows is not None and len(fcast_rows) > 0:
        fc = fcast_rows.sort_values("forecast_week_number")
        fc_avg = fc["forecast_units_base"].mean()
        anc = fc["anchor_base_units"].iloc[0] if "anchor_base_units" in fc.columns else u_now
        anchor_units = float(anc) if pd.notna(anc) else u_now
        forecast_units_base = float(fc_avg)

        # Projected TDP: extrapolate 4w momentum over 13 weeks
        tdp_mom = rows["tdp_4w_momentum"].iloc[-1] if "tdp_4w_momentum" in rows.columns else 0.0
        if pd.isna(tdp_mom):
            tdp_mom = 0.0
        # Weekly TDP change = 4w momentum / 4
        weekly_tdp_step = tdp_mom / 4.0
        t_fwd_avg = max(MIN_TDP, t_now + weekly_tdp_step * 7)  # mid-forecast projection

        # Implied velocity from forecast
        v_fwd_avg = fc_avg / max(t_fwd_avg, MIN_TDP)

        delta_t_fwd = t_fwd_avg - t_now
        delta_v_fwd = v_fwd_avg - v_now
        t_mid_fwd = (t_now + t_fwd_avg) / 2
        v_mid_fwd = (v_now + v_fwd_avg) / 2

        fwd_tdp_contrib = delta_t_fwd * v_mid_fwd
        fwd_vel_contrib = delta_v_fwd * t_mid_fwd
        fwd_delta_u = forecast_units_base - anchor_units
        denom_fwd = abs(fwd_tdp_contrib) + abs(fwd_vel_contrib)

        if denom_fwd > 0:
            fwd_tdp_pct = 100 * fwd_tdp_contrib / denom_fwd
            fwd_vel_pct = 100 * fwd_vel_contrib / denom_fwd

    # Growth driver label (use forward if available, else historical)
    if abs(fwd_delta_u) > CHANGE_FLOOR:
        sign_tdp = fwd_tdp_contrib > 0
        sign_vel = fwd_vel_contrib > 0
        pct_tdp = abs(fwd_tdp_pct)
        pct_vel = abs(fwd_vel_pct)
    else:
        sign_tdp = hist_tdp_contrib > 0
        sign_vel = hist_vel_contrib > 0
        pct_tdp = abs(hist_tdp_pct)
        pct_vel = abs(hist_vel_pct)

    change_direction = "up" if (fwd_delta_u > CHANGE_FLOOR if abs(fwd_delta_u) > CHANGE_FLOOR else delta_u > CHANGE_FLOOR) else \
                       "down" if (fwd_delta_u < -CHANGE_FLOOR if abs(fwd_delta_u) > CHANGE_FLOOR else delta_u < -CHANGE_FLOOR) else \
                       "flat"

    if change_direction == "flat":
        driver = "STABLE"
        detail = "Stable"
    elif change_direction == "up":
        if pct_tdp >= 100 * DOMINANT_THRESH:
            driver = "TDP_EXPANSION"
            detail = f"Distribution-led growth ({round(pct_tdp)}% TDP)"
        elif pct_vel >= 100 * DOMINANT_THRESH:
            driver = "VELOCITY_GROWTH"
            detail = f"Pull-through growth ({round(pct_vel)}% velocity)"
        else:
            driver = "MIXED_GROWTH"
            detail = f"Mixed growth ({round(pct_tdp)}% TDP, {round(pct_vel)}% velocity)"
    else:  # "down"
        if pct_tdp >= 100 * DOMINANT_THRESH:
            driver = "DISTRIBUTION_LOSS"
            detail = f"Distribution declining ({round(pct_tdp)}% TDP-driven)"
        elif pct_vel >= 100 * DOMINANT_THRESH:
            driver = "VELOCITY_EROSION"
            detail = f"Velocity softening ({round(pct_vel)}% velocity-driven)"
        else:
            driver = "MIXED_DECLINE"
            detail = f"Mixed decline ({round(pct_tdp)}% TDP, {round(pct_vel)}% velocity)"

    return {
        "hist_delta_units":      round(float(delta_u), 1),
        "hist_tdp_contrib":      round(float(hist_tdp_contrib), 1),
        "hist_vel_contrib":      round(float(hist_vel_contrib), 1),
        "hist_tdp_contrib_pct":  round(float(hist_tdp_pct), 1),
        "hist_vel_contrib_pct":  round(float(hist_vel_pct), 1),
        "fwd_delta_units":       round(float(fwd_delta_u), 1),
        "fwd_tdp_contrib":       round(float(fwd_tdp_contrib), 1),
        "fwd_vel_contrib":       round(float(fwd_vel_contrib), 1),
        "fwd_tdp_contrib_pct":   round(float(fwd_tdp_pct), 1),
        "fwd_vel_contrib_pct":   round(float(fwd_vel_pct), 1),
        "growth_driver":         driver,
        "growth_driver_detail":  detail,
        "hist_tdp_last13w_avg":  round(float(t_now), 2),
        "hist_vel_last13w_avg":  round(float(v_now), 4),
        "anchor_units":          round(float(anchor_units), 1) if pd.notna(anchor_units) else None,
        "forecast_units_base":   round(float(forecast_units_base), 1) if pd.notna(forecast_units_base) else None,
    }


def main():
    print("MO_64 — TDP × velocity decomposition")

    actuals = pd.read_parquet(SCRIPT_DIR / "outputs" / "retailer_sales_weekly.parquet")
    forecast = pd.read_parquet(SCRIPT_DIR / "outputs" / "retailer_sales_forecast.parquet")

    # Coerce numeric
    for col in ["base_units", "tdp", "tdp_4w_momentum"]:
        if col in actuals.columns:
            actuals[col] = pd.to_numeric(actuals[col], errors="coerce")
    for col in ["forecast_units_base", "anchor_base_units", "forecast_week_number"]:
        if col in forecast.columns:
            forecast[col] = pd.to_numeric(forecast[col], errors="coerce")

    KEY_COLS = ["upc", "retail_account", "channel_outlet", "geography_raw"]
    ID_COLS  = ["upc", "description", "retail_account", "channel_outlet",
                "geography_raw", "geography_display", "geography_level"]

    # Pre-index forecast by series key for fast lookup
    forecast_idx = forecast.groupby(KEY_COLS)

    rows_out = []
    series_groups = actuals.groupby(KEY_COLS)
    n_series = len(series_groups)
    print(f"  Processing {n_series:,} series...")

    ok = skipped = 0
    for key, grp in series_groups:
        upc, acct, ch, geo = key
        try:
            fc_rows = forecast_idx.get_group(key) if key in forecast_idx.groups else None
        except KeyError:
            fc_rows = None

        result = decompose_series(grp, fc_rows)
        if result is None:
            skipped += 1
            continue

        # Identity columns from the last row
        last = grp.iloc[-1]
        row = {c: last.get(c) for c in ID_COLS if c in grp.columns}
        row.update(result)
        rows_out.append(row)
        ok += 1

    print(f"  Computed: {ok:,}  Skipped (<{MIN_WEEKS_HIST}w): {skipped:,}")

    out = pd.DataFrame(rows_out)
    out["scored_at"] = datetime.now(timezone.utc).isoformat()
    out["model_version"] = "v1"

    # Driver distribution
    print("\nGrowth driver distribution:")
    print(out["growth_driver"].value_counts().to_string())

    # Brief attribution sanity check
    print("\nSample TDP_DRIVEN rows:")
    sample = out[out["growth_driver"] == "TDP_DRIVEN"][
        ["upc", "retail_account", "hist_tdp_contrib_pct", "growth_driver_detail"]
    ].head(5)
    print(sample.to_string(index=False))

    write_back(out, "retailer_sales_tdp_velocity", timestamp_col="scored_at")
    print("\nDone.")


if __name__ == "__main__":
    main()
