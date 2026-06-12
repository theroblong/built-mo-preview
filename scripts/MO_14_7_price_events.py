import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"
SCORED_AT = datetime.now(timezone.utc).isoformat()


def _event_row(
    upc, description, channel, account, geo_display, geo_level,
    event_type, event_label, event_color, confidence,
    trigger_value, trigger_column, source_table,
    scoring_window="13w",
    focal_pack_count=None, partner_pack_count=None, partner_description=None,
):
    return {
        "focal_upc":           upc,
        "focal_description":   description,
        "channel_outlet":      channel,
        "retail_account":      account,
        "geography_display":   geo_display,
        "geography_level":     geo_level,
        "event_type":          event_type,
        "event_label":         event_label,
        "event_color":         event_color,
        "confidence":          confidence,
        "trigger_value":       trigger_value,
        "trigger_column":      trigger_column,
        "source_table":        source_table,
        "scoring_window":      scoring_window,
        "focal_pack_count":    focal_pack_count,
        "partner_pack_count":  partner_pack_count,
        "partner_description": partner_description,
        "cross_tool_flag":     0,
        "cross_tool_event_id": None,
        "scored_at":           SCORED_AT,
    }


def _is_own_brand(description: str | None) -> bool:
    return bool(description and "built" in str(description).lower())


# ── Detector 1: DRASTIC_PRICE_CHANGE ─────────────────────────────────────────
def detect_drastic_price_change(df_scored: pd.DataFrame) -> list[dict]:
    rows = []
    mask = (
        (df_scored["post_price"] - df_scored["pre_price"]).abs() >= 2.00
    ) | (
        df_scored["log_price_change"].abs() >= np.log(1.15)
    )
    for _, r in df_scored[mask].iterrows():
        pct = round(float(r["log_price_change"]) * 100, 1)
        direction = "increase" if pct > 0 else "decrease"
        rows.append(_event_row(
            r["upc"], r["description"], r["channel_outlet"],
            r["retail_account"], r["geography_raw"], r["geography_level"],
            "DRASTIC_PRICE_CHANGE",
            f"ARP {abs(pct):.1f}% {direction} detected (13w window)",
            "amber", r.get("elasticity_band", "Unknown"),
            pct, "log_price_change", "scored_price_elasticity",
        ))
    return rows


# ── Detector 2: PROMO_RESPONSE_BREAKPOINT ────────────────────────────────────
def detect_promo_breakpoint(df_scored: pd.DataFrame) -> list[dict]:
    rows = []
    mask = (
        (df_scored["promo_confounded"].fillna(0).astype(float) == 1) &
        (df_scored["log_price_change"].abs() >= np.log(1.15)) &
        (df_scored["elasticity_band"] != "Positive")
    )
    for _, r in df_scored[mask].iterrows():
        rows.append(_event_row(
            r["upc"], r["description"], r["channel_outlet"],
            r["retail_account"], r["geography_raw"], r["geography_level"],
            "PROMO_RESPONSE_BREAKPOINT",
            "Significant price shift during promo-confounded window",
            "amber", r.get("elasticity_band", "Unknown"),
            round(float(r["log_price_change"]) * 100, 1),
            "promo_confounded+log_price_change", "scored_price_elasticity",
        ))
    return rows


# ── Detector 3: NEW_ITEM_PRICE_BASELINE ──────────────────────────────────────
def detect_new_item_baseline(df_ramp: pd.DataFrame) -> list[dict]:
    rows = []
    for col in ["weeks_since_launch", "arp"]:
        if col in df_ramp.columns:
            df_ramp[col] = pd.to_numeric(df_ramp[col], errors="coerce")
    # One event per UPC × geo × channel — keep most recent week in 8–16 window
    in_window = df_ramp[df_ramp["weeks_since_launch"].between(8, 16)].copy()
    in_window = in_window.sort_values("weeks_since_launch", ascending=False)
    df_ramp = in_window.drop_duplicates(
        subset=["upc", "channel_outlet", "retail_account", "geography_raw"]
    )
    mask = pd.Series([True] * len(df_ramp), index=df_ramp.index)
    for _, r in df_ramp[mask].iterrows():
        rows.append(_event_row(
            r["upc"], r["description"], r["channel_outlet"],
            r["retail_account"], r.get("geography_display", r.get("geography_raw")), r["geography_level"],
            "NEW_ITEM_PRICE_BASELINE",
            f"Week {int(r['weeks_since_launch'])} — price baseline window open",
            "amber", r.get("ramp_confidence", "Medium"),
            float(r.get("arp") or 0),
            "weeks_since_launch", "new_product_ramp_monitor",
            scoring_window="launch",
        ))
    return rows


# ── Detector 4: PACK_NORM_GAP ─────────────────────────────────────────────────
def detect_pack_norm_gap(df_weekly: pd.DataFrame, df_norms: pd.DataFrame) -> list[dict]:
    for col in ["pack_count", "arp", "norm_avg_price_per_bar"]:
        for df in [df_weekly, df_norms]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # Most recent week per UPC × channel × account × geo
    df_weekly = df_weekly.sort_values("__time", ascending=False)
    latest = df_weekly.drop_duplicates(
        subset=["upc", "channel_outlet", "retail_account", "geography_raw"]
    )

    # Most recent norm per pack_count × channel × account × geo
    df_norms = df_norms.sort_values("__time", ascending=False)
    df_norms = df_norms.drop_duplicates(
        subset=["channel_outlet", "retail_account", "geography_raw", "pack_count"]
    )

    merged = latest.merge(
        df_norms[["channel_outlet", "retail_account", "geography_raw",
                  "pack_count", "norm_avg_price_per_bar"]],
        on=["channel_outlet", "retail_account", "geography_raw", "pack_count"],
        how="inner",
    )
    merged["price_index"] = merged["arp"] / merged["norm_avg_price_per_bar"].replace(0, np.nan)

    rows = []
    for _, r in merged[merged["price_index"] >= 1.07].iterrows():
        pct_above = round((float(r["price_index"]) - 1) * 100, 1)
        rows.append(_event_row(
            r["upc"], r["description"], r["channel_outlet"],
            r["retail_account"], r.get("geography_display", r.get("geography_raw")), r["geography_level"],
            "PACK_NORM_GAP",
            f"BUILT {pct_above:.1f}% above MULO {int(r['pack_count'])}-pack norm",
            "amber", "Medium",
            round(float(r["price_index"]), 3),
            "price_index_vs_mulo_norm",
            "price_elasticity_weekly_features + mulo_food_pack_size_norms",
        ))
    return rows


# ── Detector 5: PRICE_DEFENSE_OPPORTUNITY ────────────────────────────────────
def detect_price_defense(df_ladder: pd.DataFrame) -> list[dict]:
    if "price_per_bar_gap_pct" in df_ladder.columns:
        df_ladder["price_per_bar_gap_pct"] = pd.to_numeric(
            df_ladder["price_per_bar_gap_pct"], errors="coerce"
        )
    rows = []
    mask = df_ladder["price_per_bar_gap_pct"].abs() >= 0.09
    for _, r in df_ladder[mask].iterrows():
        partner_desc = r.get("partner_description") or ""
        # Own-brand pack gaps belong in the Pack Ladder screen, not Priority Events
        if _is_own_brand(partner_desc):
            continue
        # Only compare equivalent pack sizes — BUILT 4-ct vs Quest 4-ct, not 1-ct vs 4-ct
        focal_ct_raw   = r.get("focal_pack_count")
        partner_ct_raw = r.get("partner_pack_count")
        try:
            if int(focal_ct_raw or 0) != int(partner_ct_raw or 0):
                continue
        except (TypeError, ValueError):
            pass
        gap_pct        = round(float(r["price_per_bar_gap_pct"]) * 100, 1)
        direction      = "below" if gap_pct < 0 else "above"
        focal_ct       = int(r.get("focal_pack_count") or 0)
        partner_ct     = int(r.get("partner_pack_count") or 0)
        focal_lbl      = f"{focal_ct}-ct" if focal_ct else "pack"
        partner_lbl    = f"{partner_ct}-ct" if partner_ct else "pack"
        competitor     = partner_desc.split()[0] if partner_desc else "competitor"
        rows.append(_event_row(
            r["focal_upc"], r["focal_description"], r["channel_outlet"],
            r["retail_account"], r.get("geography_display"), r["geography_level"],
            "PRICE_DEFENSE_OPPORTUNITY",
            f"BUILT {focal_lbl} priced {abs(gap_pct):.1f}% {direction} {competitor} {partner_lbl} per bar",
            "amber", "Medium",
            gap_pct, "price_per_bar_gap_pct", "price_pack_ladder_weekly",
            focal_pack_count=focal_ct or None,
            partner_pack_count=partner_ct or None,
            partner_description=partner_desc or None,
        ))
    return rows


# ── Detector 6: PRICE_DONOR_OVERLAP ──────────────────────────────────────────
def detect_price_donor_overlap(df_ladder: pd.DataFrame) -> list[dict]:
    rows = []
    if "ladder_compression_flag" not in df_ladder.columns:
        return rows
    df_ladder["_flag"] = df_ladder["ladder_compression_flag"].astype(str).str.strip()
    flagged = df_ladder[df_ladder["_flag"].isin(["1", "Y", "True", "true", "yes"])]
    for _, r in flagged.iterrows():
        partner_desc = r.get("partner_description") or ""
        # Own-brand pack compression belongs in the Pack Ladder screen, not Priority Events
        if _is_own_brand(partner_desc):
            continue
        focal_ct    = int(r.get("focal_pack_count") or 0)
        partner_ct  = int(r.get("partner_pack_count") or 0)
        focal_lbl   = f"{focal_ct}-ct" if focal_ct else "pack"
        partner_lbl = f"{partner_ct}-ct" if partner_ct else "pack"
        gap_val     = float(pd.to_numeric(r.get("price_per_bar_gap_pct"), errors="coerce") or 0)
        rows.append(_event_row(
            r["focal_upc"], r["focal_description"], r["channel_outlet"],
            r["retail_account"], r.get("geography_display"), r["geography_level"],
            "PRICE_DONOR_OVERLAP",
            f"Per-bar price gap with {partner_desc} {partner_lbl} compressed to {abs(gap_val)*100:.1f}%",
            "amber", "Medium",
            gap_val, "ladder_compression_flag", "price_pack_ladder_weekly",
            focal_pack_count=focal_ct or None,
            partner_pack_count=partner_ct or None,
            partner_description=partner_desc or None,
        ))
    return rows


if __name__ == "__main__":
    print("Loading scored_price_elasticity...")
    scored = query_druid("""
        SELECT * FROM "scored_price_elasticity"
        WHERE __time = (SELECT MAX(__time) FROM "scored_price_elasticity")
    """)
    for col in ["pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
                "log_price_change", "implied_elasticity", "promo_confounded"]:
        if col in scored.columns:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")
    scored["pre_price"]  = scored["pre_13w_avg_price_per_bar"]
    scored["post_price"] = scored["post_13w_avg_price_per_bar"]

    print("Loading new_product_ramp_monitor...")
    ramp = query_druid('SELECT * FROM "new_product_ramp_monitor"')

    print("Loading price_elasticity_weekly_features (latest week)...")
    weekly = query_druid("""
        SELECT *
        FROM "price_elasticity_weekly_features"
        WHERE __time = (SELECT MAX(__time) FROM "price_elasticity_weekly_features")
    """)

    print("Loading mulo_food_pack_size_norms...")
    norms = query_druid('SELECT * FROM "mulo_food_pack_size_norms"')

    print("Loading price_pack_ladder_weekly (latest week)...")
    ladder = query_druid("""
        SELECT *
        FROM "price_pack_ladder_weekly"
        WHERE __time = (SELECT MAX(__time) FROM "price_pack_ladder_weekly")
    """)

    print("Running event detectors...")
    all_events = []
    all_events += detect_drastic_price_change(scored)
    print(f"  DRASTIC_PRICE_CHANGE:        {sum(1 for e in all_events if e['event_type']=='DRASTIC_PRICE_CHANGE'):>5,}")
    all_events += detect_promo_breakpoint(scored)
    print(f"  PROMO_RESPONSE_BREAKPOINT:   {sum(1 for e in all_events if e['event_type']=='PROMO_RESPONSE_BREAKPOINT'):>5,}")
    all_events += detect_new_item_baseline(ramp)
    print(f"  NEW_ITEM_PRICE_BASELINE:     {sum(1 for e in all_events if e['event_type']=='NEW_ITEM_PRICE_BASELINE'):>5,}")
    all_events += detect_pack_norm_gap(weekly, norms)
    print(f"  PACK_NORM_GAP:               {sum(1 for e in all_events if e['event_type']=='PACK_NORM_GAP'):>5,}")
    all_events += detect_price_defense(ladder)
    print(f"  PRICE_DEFENSE_OPPORTUNITY:   {sum(1 for e in all_events if e['event_type']=='PRICE_DEFENSE_OPPORTUNITY'):>5,}")
    all_events += detect_price_donor_overlap(ladder)
    print(f"  PRICE_DONOR_OVERLAP:         {sum(1 for e in all_events if e['event_type']=='PRICE_DONOR_OVERLAP'):>5,}")

    out = pd.DataFrame(all_events)
    print(f"\n  Total new price events: {len(out):,}")

    if out.empty:
        print("No events to write.")
    else:
        write_back(out, "price_event_queue", timestamp_col="scored_at")
