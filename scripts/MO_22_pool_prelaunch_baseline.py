"""MO_22 — Build comparison_pool_prelaunch_baseline.

WHY THIS EXISTS
---------------
comparison_pool_weekly is built by self-joining built_enriched_weekly on __time.
Pre-launch, the focal UPC has no rows in built_enriched_weekly, so no pair rows
exist for those weeks even though competitors were actively selling.
This script separately captures each candidate's average base_units for the
13 weeks before the focal's first sale — the baseline the Pool Health win/loss
matrix needs to show "above/below pre-launch average" for competitor SKUs.

WHAT IT DOES
------------
1. Loads all (focal, candidate, dims) pool pairs from scored_cannibalization
   (relationship_distance 1/3/4 — same filter as the Pool Health API endpoint).
2. Gets first_week_selling per (focal_upc, channel_outlet, retail_account,
   geography_raw) from event_detection_weekly.
3. Loads candidate weekly base_units from built_enriched_weekly (no focal join —
   this is the fix; we don't need the focal to be present pre-launch).
4. For each pair, takes up to 13 weeks immediately before first_week_selling
   and averages the base_units.  Pairs with fewer than 4 pre-launch weeks are
   skipped (API falls back to WoW for those).
5. Writes output to comparison_pool_prelaunch_baseline via the standard
   MinIO → Druid native batch pipeline (human review required before ingestion).

OUTPUT SCHEMA
-------------
__time                    ISO — set to focal's first_week_selling (Druid timestamp)
focal_upc                 str
candidate_upc             str
channel_outlet            str
retail_account            str
geography_raw             str
pre_launch_avg_base_units float — AVG(candidate base_units) over pre-launch window
pre_launch_week_count     int   — number of weeks that went into the average
first_week_selling        str   — ISO, same as __time; kept as a readable column
scored_at                 str   — ISO UTC run timestamp

API USAGE
---------
In get_pool_health(), after this table is populated, add a lookup:

    SELECT candidate_upc, pre_launch_avg_base_units
    FROM "comparison_pool_prelaunch_baseline"
    WHERE focal_upc = '...' AND <dims>

Then use pre_launch_avg_base_units as the baseline instead of computing it
from comparison_pool_weekly's pre-launch rows (which don't exist).
"""

import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

PRE_LAUNCH_WEEKS = 13   # look back up to this many weeks before first sale
MIN_WEEKS        = 4    # must match the threshold in get_pool_health()
SCORED_AT        = datetime.now(timezone.utc).isoformat()


def _upc_list(upcs: list[str]) -> str:
    return ", ".join(f"'{u.replace(chr(39), chr(39)*2)}'" for u in upcs)


if __name__ == "__main__":

    # ── 1. Pool pairs ─────────────────────────────────────────────────────────
    print("Loading pool pairs from scored_cannibalization...")
    pairs = query_druid("""
        SELECT DISTINCT
            focal_upc,
            donor_upc       AS candidate_upc,
            channel_outlet,
            retail_account,
            geography_raw
        FROM "scored_cannibalization"
        WHERE relationship_distance IN (1, 3, 4)
    """)
    print(f"  Pairs: {len(pairs):,}")
    if pairs.empty:
        raise SystemExit("No pairs found — check scored_cannibalization.")

    focal_upcs     = pairs["focal_upc"].unique().tolist()
    candidate_upcs = pairs["candidate_upc"].unique().tolist()
    print(f"  Focal UPCs:     {len(focal_upcs)}")
    print(f"  Candidate UPCs: {len(candidate_upcs)}")

    # ── 2. First week selling per focal × dims ────────────────────────────────
    print("\nLoading first_week_selling from event_detection_weekly...")
    focal_first = query_druid(f"""
        SELECT
            upc              AS focal_upc,
            channel_outlet,
            retail_account,
            geography_raw,
            MIN(__time)      AS first_week_selling
        FROM "event_detection_weekly"
        WHERE upc IN ({_upc_list(focal_upcs)})
        GROUP BY upc, channel_outlet, retail_account, geography_raw
    """)
    print(f"  Focal first-week rows: {len(focal_first):,}")
    focal_first["first_week_selling"] = pd.to_datetime(
        focal_first["first_week_selling"], utc=True
    )

    # ── 3. Candidate weekly history (no focal join needed) ───────────────────
    print("\nLoading candidate weekly data from built_enriched_weekly...")
    cand_weekly = query_druid(f"""
        SELECT
            __time,
            upc              AS candidate_upc,
            channel_outlet,
            retail_account,
            geography_raw,
            base_units
        FROM "built_enriched_weekly"
        WHERE upc IN ({_upc_list(candidate_upcs)})
    """)
    print(f"  Candidate weekly rows: {len(cand_weekly):,}")
    cand_weekly["__time"]     = pd.to_datetime(cand_weekly["__time"], utc=True)
    cand_weekly["base_units"] = pd.to_numeric(cand_weekly["base_units"], errors="coerce")

    # ── 4. Attach first_week_selling to pairs ─────────────────────────────────
    pairs = pairs.merge(
        focal_first,
        on=["focal_upc", "channel_outlet", "retail_account", "geography_raw"],
        how="left",
    )
    before = len(pairs)
    pairs = pairs.dropna(subset=["first_week_selling"])
    print(f"\nPairs with launch date: {len(pairs):,} (dropped {before - len(pairs):,} with no event_detection_weekly rows)")

    # ── 5. Join pairs to candidate weekly; filter to pre-launch rows ──────────
    print("Joining pairs to candidate history...")
    joined = cand_weekly.merge(
        pairs[["focal_upc", "candidate_upc", "channel_outlet",
               "retail_account", "geography_raw", "first_week_selling"]],
        on=["candidate_upc", "channel_outlet", "retail_account", "geography_raw"],
        how="inner",
    )

    # Keep only weeks strictly before focal's first sale
    joined = joined[joined["__time"] < joined["first_week_selling"]]
    print(f"  Pre-launch candidate rows: {len(joined):,}")

    if joined.empty:
        print("No pre-launch rows found — built_enriched_weekly may not go back far enough.")
        raise SystemExit(1)

    # Keep only the most recent PRE_LAUNCH_WEEKS rows per (focal, candidate, dims)
    group_cols = ["focal_upc", "candidate_upc", "channel_outlet", "retail_account", "geography_raw"]
    joined = (
        joined
        .sort_values("__time")
        .groupby(group_cols, group_keys=False)
        .tail(PRE_LAUNCH_WEEKS)
    )

    # ── 6. Aggregate ──────────────────────────────────────────────────────────
    agg = (
        joined
        .groupby(group_cols + ["first_week_selling"])
        .agg(
            pre_launch_avg_base_units=("base_units", "mean"),
            pre_launch_week_count=("base_units", "count"),
        )
        .reset_index()
    )

    # Drop pairs below minimum week threshold (API uses WoW fallback for these)
    before = len(agg)
    agg = agg[agg["pre_launch_week_count"] >= MIN_WEEKS]
    print(f"\nBaseline records: {len(agg):,} ({before - len(agg):,} dropped — fewer than {MIN_WEEKS} pre-launch weeks)")

    if agg.empty:
        print("No records meet the minimum-weeks threshold.")
        raise SystemExit(1)

    agg["pre_launch_avg_base_units"] = agg["pre_launch_avg_base_units"].round(4)
    agg["pre_launch_week_count"]     = agg["pre_launch_week_count"].astype(int)
    agg["first_week_selling"]        = agg["first_week_selling"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    agg["scored_at"]                 = SCORED_AT

    # Druid timestamp column
    agg["__time"] = agg["first_week_selling"]

    print("\nSample output:")
    print(agg.head(5).to_string(index=False))

    # ── 7. Write back (human review required) ────────────────────────────────
    write_back(
        agg,
        datasource="comparison_pool_prelaunch_baseline",
        timestamp_col="__time",
    )
