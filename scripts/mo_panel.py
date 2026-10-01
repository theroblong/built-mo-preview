"""Shared panel definitions for the retailer-sales forecast pipeline (MO_25–MO_28).

Single source of truth for things that MUST agree across training, forecasting and
backtesting. Four divergent copies of the categorical set shipped a silent bug in
v8 (source_brand + spins_flavor_canonical were coerced to NaN at inference and fed
to the model as the literal string "nan"), so anything that has to match across
scripts belongs here rather than being retyped.

Import from the repo root or from scripts/:
    try:
        from mo_panel import CAT_COLS, drop_zero_volume_geographies
    except ImportError:
        sys.path.insert(0, "scripts")
        from mo_panel import CAT_COLS, drop_zero_volume_geographies
"""

from __future__ import annotations

import pandas as pd

# Series key. geography_raw is part of the key but NOT a model feature — see below.
GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# Categorical columns, by name. Anything listed here is exempt from
# pd.to_numeric(errors="coerce") and must be supplied as a string at inference.
#
# geography_raw is deliberately included even though it is NOT in FEATURE_COLS: it
# is a GROUP_COL, and coercing it to numeric NaNs the column, after which
# groupby(GROUP_COLS) silently drops every row (pandas dropna=True) and the
# pipeline produces an empty result with exit code 0.
CAT_COLS = {
    "channel_outlet",
    "retail_account",
    "pack_count",
    "spins_flavor_canonical",
    "source_brand",
    "geography_raw",          # GROUP_COL, not a feature — keep exempt from coercion
    "spins_flavor_raw",       # audit only — un-normalised family, duplicate levels
    "specific_flavor_normalized",  # 76 specific flavours (typo-corrected); ablation candidate
    "specific_flavor_raw",         # audit only — retains source typos
    # Listed but NOT a model feature: nfp_protein_range is a constant (95.3% of rows are
    # "15 TO < 20G PROTEIN" — every BUILT SKU is in the same band). It stays in CAT_COLS so
    # that if anyone re-adds it to FEATURE_COLS it is never run through pd.to_numeric.
    "nfp_protein_range",
}

# Default fill per categorical. "UNKNOWN" over a plausible real value: filling
# source_brand with "BUILT BAR" asserts a brand the data does not support and
# teaches the model that unlabelled rows behave like that brand.
CAT_FILLS = {
    "spins_flavor_canonical":     "UNKNOWN",
    "source_brand":               "UNKNOWN",
    "geography_raw":              "UNKNOWN",
    "spins_flavor_raw":           "UNKNOWN",
    "specific_flavor_normalized": "UNKNOWN",
    "specific_flavor_raw":        "UNKNOWN",
    "nfp_protein_range":          "UNKNOWN",
}

# Flavour field guide (verified against SPINS 2026-10-01, built_enriched_weekly,
# parent_brand = 'BUILT' — NOT source_brand, which holds the sub-brand):
#   spins_flavor_canonical     35 families, OVERRIDE-CORRECTED. The model feature.
#                              Fixes UPC 08-40229-30034 (Salted Caramel), which
#                              spins_flavor_mapped and spins_flavor_raw misfile as CHOCOLATE.
#   specific_flavor_normalized 76 specific flavours, typo-corrected ("Satled" -> "Salted").
#                              Needed to compare pack sizes within ONE true flavour —
#                              family BROWNIE lumps Brownie Batter with Candy Cane Brownie.
#   specific_flavor_raw        84 values, keeps typos. Audit only.
#   spins_flavor_raw           un-normalised family with duplicate levels. Audit only.


# Military exchanges / commissaries. Excluded explicitly rather than relying on the
# zero-volume filter to catch them: as of 2026-10-01 all three report exactly 0 BUILT
# units, but if any ever reported a nonzero week the filter would stop dropping them and
# they would silently rejoin the panel. They are a separate, non-retail trade class
# (AAFES = Army & Air Force Exchange, NEXCOM = Navy Exchange, CGX = Coast Guard
# Exchange) and are MULO CRMA aggregates only — no account-level feed exists.
MILITARY_ACCOUNTS = {"AAFES", "COAST GUARD", "NEXCOM"}

PROMO_MECHANIC_COLS = ["units_lift_tpr", "units_lift_any_display", "units_lift_any_feature"]


def drop_military_accounts(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Drop military exchange / commissary accounts.

    Measured 2026-10-01: AAFES (5,395 rows), COAST GUARD (4,536), NEXCOM (4,519) —
    14,450 rows carrying exactly ZERO BUILT units, all MULO CRMA only.
    """
    if "retail_account" not in df.columns:
        return df
    mask = df["retail_account"].isin(MILITARY_ACCOUNTS)
    if not mask.any():
        if verbose:
            print("  Military/commissary filter: none present")
        return df
    kept = df[~mask].copy()
    if verbose:
        found = sorted(df.loc[mask, "retail_account"].unique())
        print(f"  Military/commissary filter: dropped {int(mask.sum()):,} rows {found}")
        print(f"  Rows: {len(df):,} → {len(kept):,}")
    return kept


def fill_promo_mechanic_nulls(
    df: pd.DataFrame,
    verbose: bool = True,
) -> pd.DataFrame:
    """Fill promo-mechanic nulls with 0 ONLY where no promo ran that week.

    A null in units_lift_tpr / units_lift_any_display / units_lift_any_feature means
    two different things depending on context, and treating both as "missing" conflates
    them. Measured on the 2026-10-01 panel:

        feature                   null | is_promo_week=0   null | is_promo_week=1
        units_lift_tpr                      79.8%                  41.6%
        units_lift_any_display              88.0%                  48.8%
        units_lift_any_feature              99.3%                  86.6%

    * **No promo that week** -> no TPR/display/feature could have run, so the lift is
      genuinely **zero**, not unknown. Leaving it NaN makes the model unable to
      distinguish "no promotion" from "promotion whose mechanic SPINS did not attribute".
    * **Promo ran but the mechanic is null** -> genuinely unknown. Preserved as NaN so
      LightGBM routes it as missing.

    This is the same defect class as the MO_50 rolling_cannibal_pressure bug, where 73%
    nulls came from treating "no active cannibalisation" as missing instead of 0.

    Rows are never dropped — only values are filled, and only where the semantics
    justify it.
    """
    if "is_promo_week" not in df.columns:
        if verbose:
            print("  Promo-mechanic fill: is_promo_week absent — skipped")
        return df

    out = df.copy()
    no_promo = pd.to_numeric(out["is_promo_week"], errors="coerce").fillna(0) == 0
    for col in PROMO_MECHANIC_COLS:
        if col not in out.columns:
            continue
        vals = pd.to_numeric(out[col], errors="coerce")
        target = no_promo & vals.isna()
        n = int(target.sum())
        out[col] = vals.where(~target, 0.0)
        if verbose and n:
            remaining = pd.to_numeric(out[col], errors="coerce").isna().mean() * 100
            print(f"  {col:24s} filled {n:>7,} nulls with 0 (no promo that week) "
                  f"| still null: {remaining:5.1f}% (promo ran, mechanic unknown)")
    return out


def apply_rma_priority(
    df: pd.DataFrame,
    verbose: bool = True,
) -> pd.DataFrame:
    """Keep one measurement basis per retailer, per Brian's guidance.

    Rule (stated by Jason 2026-10-01):
      1. Retailer has RMA            -> use RMA only, drop its CRMA rows
      2. Retailer has CRMA only      -> keep CRMA (e.g. no account-level feed exists)
      3. Retailer has neither        -> keep as-is (KEY ACCOUNT and other store-level feeds)

    Why CRMA must go when RMA exists — two measurements, both verified on the
    2026-10-01 panel:

    * **CRMA is not retailer-specific.** Mean pairwise Jaccard overlap of the UPC
      sets across CRMA geographies is **0.796** (CVS vs KROGER 0.901, AHOLD vs BJS
      0.975). Different retailers share almost the same UPC list, which is the
      signature of a shared MULO aggregate rather than an assortment. Summing CRMA
      across retailers therefore double-counts the same underlying demand.

    * **RMA matches each retailer's real-world model.** Pack mix lines up exactly:
      KROGER CONVENTIONAL|FOOD 42 UPCs 78% singles; WALMART / TARGET
      CONVENTIONAL|MASS MERCH ~30 UPCs ~80% 4-packs; SAMS / BJS CONVENTIONAL|CLUB
      2-4 UPCs **99-100% 13-packs**. Sam's four UPCs are the true club assortment
      (wholesale, few SKUs, multipacks), not a coverage gap — so the 92 extra UPCs
      its CRMA rows carry are aggregate contamination.

    Do NOT "preserve UPC coverage" by applying this per (retailer x UPC). That was
    considered and rejected: it keeps exactly the aggregate rows this rule exists to
    remove, because a UPC absent from a retailer's RMA is generally a UPC that
    retailer does not carry.

    IMPACT — large, and deliberate. On the 2026-10-01 panel, after the zero-volume
    filter: 160,240 -> 96,153 rows (-40%), 2,740 -> 1,716 series, 122 -> 120 UPCs,
    and base_units 426.6M -> 61.1M (**14.3% retained**). The 85.7% drop is the
    double-counted aggregate being removed, not lost sales — but it restates every
    volume total, so client-facing figures move with it.
    """
    if "geography_level" not in df.columns or "retail_account" not in df.columns:
        if verbose:
            print("  RMA priority: geography_level/retail_account absent — skipped")
        return df

    levels = df.groupby("retail_account", observed=True)["geography_level"].agg(set)
    has_rma = {a for a, s in levels.items() if "RMA" in s}

    mask = (df["geography_level"] == "CRMA") & df["retail_account"].isin(has_rma)
    kept = df[~mask].copy()

    if verbose:
        crma_only = {a for a, s in levels.items() if "CRMA" in s} - has_rma
        print(f"  RMA priority: {len(has_rma)} retailers have RMA -> CRMA dropped for those")
        print(f"                {len(crma_only)} retailer(s) are CRMA-only -> CRMA kept"
              f"{' ' + str(sorted(crma_only)) if crma_only else ''}")
        print(f"                dropped {int(mask.sum()):,} CRMA rows "
              f"({mask.sum() / len(df) * 100:.1f}%)")
        print(f"  Rows: {len(df):,} → {len(kept):,}")
    return kept


def cat_str(val, default: str) -> str:
    """Categorical value as a string, with a fallback that survives NaN.

    `str(val or default)` is wrong: float('nan') is truthy, so the fallback never
    fires and the literal string "nan" reaches pd.Categorical, where it is absent
    from the trained category universe and silently becomes missing. This shipped
    in v8 for spins_flavor_canonical and source_brand.
    """
    import math
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    s = str(val).strip()
    return default if s in ("", "nan", "None", "NaN", "<NA>") else s


def drop_zero_volume_geographies(
    df: pd.DataFrame,
    target: str = "base_units",
    verbose: bool = True,
) -> pd.DataFrame:
    """Drop geographies whose entire history carries zero volume.

    Measured 2026-10-01: 20 of 154 geography variants, 26,308 of 187,127 rows
    (14.1%), with SUM(base_units) == 0 across the whole panel. Two classes:

    1. **Phantom AK/HI markets** — SPINS emits a "with Alaska/Hawaii" market
       definition alongside the real one. All six carry exactly zero units and each
       has a row-count-matched twin at the same account+channel holding the real
       volume (e.g. KROGER CORP W/ AK... = 2,816 rows / 0 units vs its twin's
       4,173,782 units). They are duplicate market definitions, not real demand.
    2. **No-distribution accounts** — military exchanges AAFES/CGX/NEXCOM (14,529
       rows, 7.8%) plus c-store chains where BUILT has never sold a unit.

    Why this is a filter and not a feature: once these rows are gone, geography_raw
    is 1:1 with retail_account x channel_outlet for 99.1% of the panel (1 remaining
    multi-variant combo, Circle K, 1,392 rows). The apparent "geography signal" was
    entirely the phantom rows, so the correct fix is to delete them rather than add
    a 154-level categorical whose only job is to separate junk from real data.

    Why it matters:
    - MO_26 drops null targets but not zeros, so these rows carried 14.1% of
      training weight — and Optuna / RECENCY_LAMBDA were tuned on that mix.
    - wMAPE = SUM|err| / SUM(actual), so a zero-actual series adds to the numerator
      and nothing to the denominator. Albertsons' CONVENTIONAL|FOOD backtest slice
      was half phantom rows, which is a live suspect for its 50.3% outlier.

    Note this filters whole *geographies*, not individual zero rows: a real market
    that is genuinely zero for some weeks (out of stock, pre-launch) keeps those
    weeks, because they are real observations the model should learn from.
    """
    if "geography_raw" not in df.columns or target not in df.columns:
        return df

    # observed=True: geography_raw is often already a categorical dtype by this point,
    # and the pandas default (observed=False) would include levels with no rows at all,
    # reporting them as "zero volume". Harmless for the row mask — a level with no rows
    # matches nothing — but it inflates the dropped-geography count in the log, and the
    # default is changing in a future pandas anyway.
    vol = (pd.to_numeric(df[target], errors="coerce").fillna(0)
             .groupby(df["geography_raw"], observed=True).sum())
    dead = set(vol[vol <= 0].index)
    if not dead:
        if verbose:
            print("  Zero-volume geography filter: none found")
        return df

    mask = df["geography_raw"].isin(dead)
    kept = df[~mask].copy()
    if verbose:
        print(f"  Zero-volume geography filter: dropped {len(dead)} geographies, "
              f"{int(mask.sum()):,} rows ({mask.sum() / len(df) * 100:.1f}%)")
        for geo in sorted(dead)[:8]:
            print(f"      - {geo}")
        if len(dead) > 8:
            print(f"      … and {len(dead) - 8} more")
        print(f"  Rows: {len(df):,} → {len(kept):,}")
    return kept
