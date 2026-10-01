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

import re

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

# Minimum series length for the LightGBM autoregressive models. Was MO_25.MIN_WEEKS,
# i.e. applied at EXTRACT — which silently kept BUILT's newest launches out of the
# parquet entirely and therefore out of reach of every downstream consumer, not just
# training. Moved here so it is a training/serving decision, not a data decision.
MIN_SERIES_WEEKS = 13


def drop_short_series(
    df: pd.DataFrame,
    min_weeks: int = MIN_SERIES_WEEKS,
    target: str = "base_units",
    verbose: bool = True,
) -> pd.DataFrame:
    """Drop series with fewer than `min_weeks` observations of the target.

    Legitimate for the LightGBM models: the feature set needs lag13 / roll13 / lag52,
    so an 8-week series contributes rows whose most important features are all NaN.

    NOT legitimate at extract time, which is where this used to live. On the
    2026-10-01 panel MO_25's MIN_WEEKS=13 removed 7,291 series (23.9% of all series,
    though only 0.27% of volume) AND 17 UPCs entirely — including BUILT's newest and
    fastest-ramping launches:

        08-40229-30766  first week 2026-06-28  150,141 units  17 accounts  (11 wks)
        08-40229-30687  first week 2026-07-19  145,626 units  17 accounts  ( 8 wks)
        08-40229-30771  first week 2026-07-19   23,162 units   3 accounts  ( 8 wks)
        08-40229-30772  first week 2026-07-12      758 units   1 account   ( 9 wks)

    Those are real, broadly distributed new SKUs (a new PB S'mores flavour in both
    1-pack and 12-pack, plus a new variety pack). Dropping them in MO_25 made them
    invisible to MO_27, to the ETS work, and to any analysis reading the parquet.

    ⚠️ MO_27 must apply this too. It has NO minimum-history gate of its own and NO ETS
    fallback — ETS lives only in the MO_30–MO_37 analysis scripts and the chart builder,
    and MO_34's data-maturity router ("new/expanding -> ETS, mature -> LightGBM") is
    analysis, not production code. So without an explicit gate MO_27 would forecast an
    8-week series from NaN lags and serve the result as if it were sound. Skipping with
    a logged count is the honest behaviour until a real ETS route is wired in.
    """
    if target not in df.columns:
        return df
    lengths = df.groupby(GROUP_COLS, observed=True)[target].transform("count")
    mask = lengths < min_weeks
    if not mask.any():
        if verbose:
            print(f"  Short-series filter (<{min_weeks} wks): none found")
        return df
    kept = df[~mask].copy()
    if verbose:
        n_series = df.loc[mask].groupby(GROUP_COLS, observed=True).ngroups
        lost_upcs = sorted(set(df.loc[mask, "upc"]) - set(kept["upc"])) if "upc" in df else []
        print(f"  Short-series filter (<{min_weeks} wks): dropped {int(mask.sum()):,} rows "
              f"across {n_series:,} series")
        if lost_upcs:
            print(f"      {len(lost_upcs)} UPC(s) excluded entirely (too new to model): "
                  f"{lost_upcs[:6]}{' …' if len(lost_upcs) > 6 else ''}")
        print(f"  Rows: {len(df):,} → {len(kept):,}")
    return kept


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


AK_HI_MARKET_PATTERN = re.compile(
    r"W/\s*(AK|HI|PR|ALASKA|HAWAII|PUERTO\s+RICO)\b", re.I)


def drop_ak_hi_market_variants(
    df: pd.DataFrame,
    verbose: bool = True,
) -> pd.DataFrame:
    """Exclude SPINS "with Alaska / Hawaii / Puerto Rico" market variants BY DEFINITION.

    SPINS ships a supplementary market for some retailers covering the same chain plus the
    AK/HI/PR stores. Where both the base market and the supplement are present, counting both
    double-counts the retailer.

    DECIDED BY JASON 2026-10-01 (to be confirmed with Brian):
      * **Circle K — ignore the W/ ALASKA variant.** Keep `CIRCLE K CORP - RMA`, drop
        `CK - CIRCLE K CORP TOTAL W/ ALASKA - RMA`. Note this is the NARROWER market, which a
        value-based "keep the superset" heuristic would have got backwards. Which market is
        canonical is a business decision about BUILT's book of business, not something a
        nesting test can infer.
      * **Ignore the six zero-unit AK/HI markets** (Albertsons, CVS, Kroger, Sam's, Target,
        Walgreens). They were already being removed by `drop_zero_volume_geographies`, but only
        because they happen to carry no units — a coincidence, not a safeguard. Excluding them
        by definition means a future SPINS refresh that populates one cannot silently double a
        top-5 retailer.
      * **Giant Eagle and Hy-Vee both count** — GETGO/FAST & FRESH are convenience banners and
        the CORP markets are supermarkets, i.e. genuinely different store sets. They do not
        match this pattern, so they are untouched. Verified: 25 and 34 item-weeks respectively
        where the banner exceeds the parent, which is impossible under nesting.
      * **Murphy USA — `MURPHY CORP TOTAL - RMA` is all we receive; use it.** It contains
        "CORP TOTAL" but no AK/HI supplement, so it is correctly not matched.

    The pattern deliberately requires AK/HI/PR immediately after "W/", so legitimate markets
    whose names contain "W/" or "TOTAL" survive. Verified against all 159 geographies in the
    extract — 7 matched, and these all correctly did NOT match:
        MURPHY CORP TOTAL - RMA
        KROGER CORP W/ HARRIS TEETER, ROUNDYS AND RULER - RMA   (the real Kroger market)
        K-VA-T FOODS W/ CHATTANOOGA, TN - RMA
        WAKEFERN CORP W/O PRICE RITE - RMA · WEGMANS CORP W/O METRO NY - RMA
        SPROUTS FARMERS MARKET - TOTAL US W/O PL   + 92 other "- TOTAL US" markets
    """
    if "geography_raw" not in df.columns:
        return df
    geos = [g for g in df["geography_raw"].dropna().unique()
            if AK_HI_MARKET_PATTERN.search(str(g))]
    if not geos:
        if verbose:
            print("  AK/HI market-variant filter: none present")
        return df
    mask = df["geography_raw"].isin(geos)
    kept = df[~mask].copy()
    if verbose:
        print(f"  AK/HI market-variant filter: dropped {len(geos)} supplementary "
              f"market{'' if len(geos) == 1 else 's'}, {int(mask.sum()):,} rows")
        for g in sorted(geos):
            u = pd.to_numeric(df.loc[df["geography_raw"] == g, "base_units"],
                              errors="coerce").sum() if "base_units" in df.columns else float("nan")
            print(f"      - {g}  ({u:,.0f} units)")
        print(f"  Rows: {len(df):,} → {len(kept):,}")
    return kept


def warn_nested_rma_duplicates(
    df: pd.DataFrame,
    target: str = "base_units",
    min_cells: int = 30,
    min_jaccard: float = 0.75,
    min_nesting: float = 0.98,
    min_equal: float = 0.25,
    verbose: bool = True,
) -> pd.DataFrame:
    """SAFETY NET — detect, report, and DO NOT drop nested duplicate markets.

    Returns `df` unchanged. This exists because the Circle K duplicate was found by accident
    while answering an unrelated question, and nothing in the pipeline would have caught it.

    It is WARN-ONLY on purpose. The detector can prove two markets describe the same stores,
    but it cannot decide which one is canonical — that is a business call. On Circle K the
    "keep the superset" heuristic would have kept the with-Alaska market; the actual decision
    was the opposite. So a new nested pair is surfaced loudly for a human, never auto-dropped.

    Run AFTER `drop_ak_hi_market_variants`, `apply_rma_priority` and
    `drop_zero_volume_geographies`. With those applied, this should report NOTHING; anything it
    prints is a new SPINS market structure that needs review with Brian before the next retrain.

    Tests (all four must hold): >= `min_cells` shared (upc, week) cells, cell-set Jaccard >=
    `min_jaccard`, one side >= the other in >= `min_nesting` of shared cells, and >= `min_equal`
    exactly equal. The exact-equality floor and the reversal count are what separate a true
    nested duplicate from sibling banners.
    """
    need = {"geography_raw", "retail_account", "upc", "__time", target}
    if not need.issubset(df.columns):
        return df

    d = df[["retail_account", "geography_raw", "upc", "__time", target]].copy()
    d[target] = pd.to_numeric(d[target], errors="coerce")
    d = d.dropna(subset=[target])

    hits = []
    for acct, sub in d.groupby("retail_account", observed=True):
        geos = sorted(sub["geography_raw"].dropna().unique())
        if len(geos) < 2:
            continue
        agg = {g: s.groupby(["upc", "__time"])[target].sum()
               for g, s in sub.groupby("geography_raw", observed=True)}
        for i in range(len(geos)):
            for k in range(i + 1, len(geos)):
                g1, g2 = geos[i], geos[k]
                a, b = agg.get(g1), agg.get(g2)
                if a is None or b is None:
                    continue
                s1, s2 = set(a.index), set(b.index)
                inter, union = s1 & s2, s1 | s2
                if len(inter) < min_cells or not union:
                    continue
                if len(inter) / len(union) < min_jaccard:
                    continue
                j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
                if not len(j):
                    continue
                eq = float((abs(j["a"] - j["b"]) < 1e-6).mean())
                nest = max(float((j["a"] >= j["b"] - 1e-6).mean()),
                           float((j["b"] >= j["a"] - 1e-6).mean()))
                if eq >= min_equal and nest >= min_nesting:
                    hits.append((acct, g1, g2, len(inter), len(inter) / len(union), eq, nest,
                                 float(a.sum()), float(b.sum())))

    if verbose:
        if not hits:
            print("  Nested-market safety net: clean (no undeclared duplicates)")
        else:
            print("\n  " + "!" * 66)
            print(f"  NESTED MARKET DUPLICATE DETECTED — {len(hits)} pair(s). NOT dropped.")
            print("  Review with Brian and add an explicit rule before the next retrain;")
            print("  which market is canonical is a business decision, not a heuristic.")
            for acct, g1, g2, n, jac, eq, nest, u1, u2 in hits:
                print(f"    {acct}:")
                print(f"      {g1}  ({u1:,.0f} units)")
                print(f"      {g2}  ({u2:,.0f} units)")
                print(f"      {n:,} shared cells | Jaccard {jac:.3f} | "
                      f"{eq*100:.1f}% exactly equal | {nest*100:.1f}% nested")
            print(f"  {'!' * 66}\n")
    return df
