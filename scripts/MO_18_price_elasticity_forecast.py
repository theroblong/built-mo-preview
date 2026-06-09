import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"

# Price change assumptions for each scenario
SCENARIOS = {
    "low":  -0.10,   # -10% price cut
    "base":  0.00,   # status quo
    "high":  0.10,   # +10% price increase
}

# Confidence band half-width by elasticity band
BAND_WIDTH = {
    "Highly Elastic":      0.25,
    "Elastic":             0.20,
    "Moderately Elastic":  0.15,
    "Inelastic":           0.10,
    "Positive":            0.20,
}


def forecast_units(current_velocity, current_price, price_change_pct, elasticity):
    """
    Apply elasticity formula: pct_unit_change = elasticity * pct_price_change.
    Returns forecasted velocity and pct change.
    """
    pct_unit_change = elasticity * price_change_pct
    forecasted = current_velocity * (1 + pct_unit_change)
    return max(forecasted, 0.0), pct_unit_change


if __name__ == "__main__":
    print("Loading scored_price_elasticity from Druid...")
    df = query_druid('SELECT * FROM "scored_price_elasticity"')
    print(f"  Rows: {len(df):,}")

    numeric_cols = [
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
        "pre_13w_velocity_spm", "implied_elasticity",
        "pre_13w_weeks_count", "post_13w_weeks_count",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Use post_13w_avg_price_per_bar as current price; pre_13w_velocity_spm as baseline velocity
    df = df[df["post_13w_avg_price_per_bar"].notna() & df["pre_13w_velocity_spm"].notna()].copy()
    df = df[df["implied_elasticity"].notna() & df["implied_elasticity"].between(-10, 5)].copy()
    print(f"  Rows after filtering: {len(df):,}")

    now = datetime.now(timezone.utc).isoformat()
    rows = []

    for scenario_name, price_change_pct in SCENARIOS.items():
        tmp = df.copy()
        tmp["scenario_name"] = scenario_name
        tmp["price_input"] = tmp["post_13w_avg_price_per_bar"] * (1 + price_change_pct)

        forecasted, pct_chg = zip(*tmp.apply(
            lambda r: forecast_units(
                r["pre_13w_velocity_spm"],
                r["post_13w_avg_price_per_bar"],
                price_change_pct,
                r["implied_elasticity"],
            ),
            axis=1,
        ))
        tmp["forecast_units"] = forecasted
        tmp["forecast_pct_change"] = pct_chg

        band_half = tmp["elasticity_band"].map(BAND_WIDTH).fillna(0.15)
        tmp["confidence_band_low"]  = tmp["forecast_units"] * (1 - band_half)
        tmp["confidence_band_high"] = tmp["forecast_units"] * (1 + band_half)

        tmp["model_version"] = MODEL_VERSION
        tmp["scored_at"] = now
        rows.append(tmp)

    forecasts = pd.concat(rows, ignore_index=True)
    print(f"  Total forecast rows (3 scenarios): {len(forecasts):,}")

    output_cols = [
        "upc", "description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "scenario_name", "price_input",
        "post_13w_avg_price_per_bar", "implied_elasticity", "elasticity_band",
        "forecast_units", "forecast_pct_change",
        "confidence_band_low", "confidence_band_high",
        "pre_13w_weeks_count", "post_13w_weeks_count",
        "model_version", "scored_at",
    ]
    out = forecasts[[c for c in output_cols if c in forecasts.columns]].copy()

    write_back(out, "price_elasticity_forecast", timestamp_col="scored_at")
