import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

SCORED_AT = datetime.now(timezone.utc).isoformat()

# Look-back window for weekly history fed to the P11 training set
LOOKBACK_INTERVAL = "INTERVAL '2' YEAR"


def _upc_sql_list(upcs: list[str]) -> str:
    escaped = [u.replace("'", "''") for u in upcs]
    return ", ".join(f"'{u}'" for u in escaped)


if __name__ == "__main__":
    # ── 1. Load cannibalizing + watch pairs ──────────────────────────────────
    print("Loading scored_cannibalization pairs...")
    pairs = query_druid("""
        SELECT DISTINCT
            focal_upc, focal_description, donor_upc,
            channel_outlet, retail_account, geography_raw,
            cannibal_prob, cannibal_status
        FROM "scored_cannibalization"
        WHERE cannibal_status IN ('Cannibalizing', 'Watch')
    """)
    print(f"  Pairs: {len(pairs):,}")
    pairs["cannibal_prob"] = pd.to_numeric(pairs["cannibal_prob"], errors="coerce").fillna(0)

    focal_upcs = pairs["focal_upc"].unique().tolist()
    donor_upcs = pairs["donor_upc"].unique().tolist()

    # ── 2. Focal weekly data ─────────────────────────────────────────────────
    print("Loading event_detection_weekly for focal UPCs...")
    focal_weekly = query_druid(f"""
        SELECT
            __time, upc, channel_outlet, retail_account,
            geography_raw, geography_display, geography_level,
            base_units, avg_weekly_units_spm, tdp,
            base_units_roll4_avg,
            base_units_roll8_avg, base_units_roll8_std,
            base_units_roll13_avg, base_units_roll13_std,
            base_units_wow_delta,
            velocity_spm_roll8_avg, velocity_spm_roll13_avg,
            base_units_z8, base_units_z13,
            velocity_spm_z8, velocity_spm_z13,
            tdp_z8,
            base_units_outlier_class
        FROM "event_detection_weekly"
        WHERE upc IN ({_upc_sql_list(focal_upcs)})
          AND __time >= CURRENT_TIMESTAMP - {LOOKBACK_INTERVAL}
    """)
    print(f"  Focal weekly rows: {len(focal_weekly):,}")

    focal_num_cols = [
        "base_units", "avg_weekly_units_spm", "tdp",
        "base_units_roll4_avg",
        "base_units_roll8_avg", "base_units_roll8_std",
        "base_units_roll13_avg", "base_units_roll13_std",
        "base_units_wow_delta",
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "base_units_z8", "base_units_z13",
        "velocity_spm_z8", "velocity_spm_z13",
        "tdp_z8",
    ]
    for col in focal_num_cols:
        if col in focal_weekly.columns:
            focal_weekly[col] = pd.to_numeric(focal_weekly[col], errors="coerce")

    # ── 3. Donor weekly data ─────────────────────────────────────────────────
    print("Loading event_detection_weekly for donor UPCs...")
    donor_weekly = query_druid(f"""
        SELECT
            __time, upc, channel_outlet, retail_account, geography_raw,
            base_units, base_units_wow_delta
        FROM "event_detection_weekly"
        WHERE upc IN ({_upc_sql_list(donor_upcs)})
          AND __time >= CURRENT_TIMESTAMP - {LOOKBACK_INTERVAL}
    """)
    print(f"  Donor weekly rows: {len(donor_weekly):,}")
    for col in ["base_units", "base_units_wow_delta"]:
        donor_weekly[col] = pd.to_numeric(donor_weekly[col], errors="coerce")

    # ── 4. Compute weighted donor loss per focal × geo × channel × week ──────
    donor_weekly = donor_weekly.rename(columns={
        "upc": "donor_upc",
        "base_units": "donor_base_units",
        "base_units_wow_delta": "donor_wow_delta",
    })

    # Expand pairs across time: join pairs to donor weekly on spatial dims only,
    # then group by (focal_upc, channel, account, geo, week) to aggregate donor
    # contributions.
    pairs_time = pairs.merge(
        donor_weekly[["__time", "donor_upc", "channel_outlet",
                      "retail_account", "geography_raw",
                      "donor_base_units", "donor_wow_delta"]],
        on=["donor_upc", "channel_outlet", "retail_account", "geography_raw"],
        how="inner",
    )
    # Weighted loss: cannibal_prob × max(0, -donor_wow_delta)
    pairs_time["donor_loss"] = np.maximum(0, -(pairs_time["donor_wow_delta"].fillna(0)))
    pairs_time["weighted_loss"] = pairs_time["cannibal_prob"] * pairs_time["donor_loss"]

    donor_agg = (
        pairs_time
        .groupby(["__time", "focal_upc", "channel_outlet", "retail_account", "geography_raw"])
        .agg(
            cannibal_weighted_donor_loss=("weighted_loss", "sum"),
            donor_count=("donor_upc", "nunique"),
            max_donor_cannibal_prob=("cannibal_prob", "max"),
        )
        .reset_index()
    )

    # ── 5. Merge donor aggregates onto focal weekly rows ─────────────────────
    focal_weekly = focal_weekly.rename(columns={"upc": "focal_upc"})
    focal_weekly = focal_weekly.drop_duplicates(
        subset=["__time", "focal_upc", "channel_outlet", "retail_account", "geography_raw"]
    )

    result = focal_weekly.merge(
        donor_agg,
        on=["__time", "focal_upc", "channel_outlet", "retail_account", "geography_raw"],
        how="left",
    )
    result["cannibal_weighted_donor_loss"] = result["cannibal_weighted_donor_loss"].fillna(0)
    result["donor_count"] = result["donor_count"].fillna(0).astype(int)
    result["max_donor_cannibal_prob"] = result["max_donor_cannibal_prob"].fillna(0)

    result["cannibalization_rate"] = (
        result["cannibal_weighted_donor_loss"]
        / result["base_units"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    # ── 6. Attach description from pairs ────────────────────────────────────
    desc_map = (
        pairs[["focal_upc", "focal_description"]]
        .drop_duplicates("focal_upc")
        .set_index("focal_upc")["focal_description"]
        .to_dict()
    )
    result["focal_description"] = result["focal_upc"].map(desc_map)

    result["scored_at"] = SCORED_AT

    output_cols = [
        "__time",
        "focal_upc", "focal_description",
        "channel_outlet", "retail_account",
        "geography_raw", "geography_display", "geography_level",
        "base_units", "base_units_wow_delta",
        "avg_weekly_units_spm",
        "base_units_roll4_avg",
        "base_units_roll8_avg", "base_units_roll8_std",
        "base_units_roll13_avg", "base_units_roll13_std",
        "base_units_z8", "base_units_z13",
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "velocity_spm_z8", "velocity_spm_z13",
        "tdp", "tdp_z8",
        "base_units_outlier_class",
        "cannibal_weighted_donor_loss",
        "cannibalization_rate",
        "donor_count",
        "max_donor_cannibal_prob",
        "scored_at",
    ]
    out = result[[c for c in output_cols if c in result.columns]].copy()

    print(f"\n  Total cannibalization_rate_weekly rows: {len(out):,}")
    print(f"  Weeks covered: {out['__time'].nunique():,}")
    print(f"  Focal UPCs:    {out['focal_upc'].nunique():,}")
    print(f"  Rate range:    {out['cannibalization_rate'].min():.4f} – {out['cannibalization_rate'].max():.4f}")

    if out.empty:
        print("No rows to write.")
    else:
        write_back(out, "cannibalization_rate_weekly", timestamp_col="__time")
