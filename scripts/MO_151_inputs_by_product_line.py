"""MO_151 - Which inputs drive the production forecast for each product line (BAR, PUFF, SOUR PUFF)?

# protocol: not-a-forecast-arm

WHERE THIS CAME FROM: MO_148 found one pooled model beats separate per-line models; Rob asked (2026-10-14) "I wonder how
it is weighing those forecasts internally". Descriptive only: no accuracy is scored and no model is trained.

METHOD: load the SERVED models (outputs/model_direct_h{01,04,13}_q50_v11d.pkl, the median forecast) and build their
inputs exactly as MO_27D does (its load_models / build_panel; last observed week per series, target-week seasonality).
Lapsed series (no SPINS row for LAPSE_WEEKS+) are excluded: MO_27D forecasts them with a resume rule, not the model.
LightGBM's own per-row contributions (pred_contrib=True, TreeSHAP on the log1p scale) are averaged in absolute value
over each line's series and expressed as shares of that line's total. Line = the series' CURRENT brand label (last row),
per the MO_148 skeptic note. Output: outputs/mo151_inputs_by_line.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import MO_27D_direct_forecast as F

HORIZONS = (1, 4, 13)
BAR = ("BUILT BAR", "BUILT")
FAMILY = {  # plain-language groups for a non-technical reader
    "Recent sales level and trend": ["base_units_roll4_avg", "base_units_roll8_avg", "base_units_roll8_std",
                                     "base_units_roll13_avg", "base_units_roll13_std", "base_units_wow_delta",
                                     "base_units_z8", "base_units_z13", "base_units_lag1", "base_units_lag4",
                                     "base_units_lag13", "base_units_13wk_momentum", "base_units_4wk_momentum"],
    "Sales per store": ["velocity_spm_roll8_avg", "velocity_spm_roll13_avg", "velocity_spm_z8", "velocity_spm_z13",
                        "velocity_per_tdp"],
    "Distribution (store reach)": ["tdp", "tdp_z8", "tdp_wow_delta", "tdp_4w_momentum"],
    "Same week last year": ["base_units_lag52", "velocity_spm_lag52", "tdp_lag52", "promo_52w_lag"],
    "Price": ["arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std", "arp_lag1", "arp_dollar_discount",
              "competitor_price_gap"],
    "Promotion history": ["promo_lift_ratio", "promo_lift_median", "promo_lift_p90", "promo_lift_n_events",
                          "promo_lift_std", "is_promo_week", "promo_intensity", "units_lift_tpr",
                          "units_lift_any_display", "units_lift_any_feature", "promo_rate_woy"],
    "Retailer": ["retail_account", "channel_outlet"],
    "Product (flavor, pack, product line)": ["spins_flavor_canonical", "pack_count", "source_brand"],
    "Item age and nearby launches": ["weeks_since_launch", "donor_count", "top_donor_tdp_sum"],
    "Time of year": ["week_sin", "week_cos", "week_sin26", "week_cos26"],
}


def main() -> None:
    models, meta, feats = F.load_models("v11d")
    fam_of = {f: k for k, v in FAMILY.items() for f in v}
    missing = [f for f in feats if f not in fam_of]
    assert not missing, f"unmapped inputs: {missing}"
    df = F.build_panel(feats)
    anchor = df["__time"].max()
    last_seen = df.groupby(F.GROUP_COLS, observed=True)["__time"].max()
    lapse = ((anchor - last_seen).dt.days / 7).round() >= F.LAPSE_WEEKS
    last = df.groupby(F.GROUP_COLS, observed=True).tail(1).reset_index(drop=True)
    key = pd.MultiIndex.from_frame(last[F.GROUP_COLS].astype(str))
    lapsed_keys = {tuple(map(str, k)) for k in last_seen[lapse].index}
    last = last[[tuple(k) not in lapsed_keys for k in key]].reset_index(drop=True)
    b = last["source_brand"].astype(str)
    last["line"] = np.select([b.isin(BAR), b.eq("BUILT SOUR PUFF")], ["BAR", "SOUR PUFF"], "PUFF")
    recent = df[df["__time"] > anchor - pd.Timedelta(weeks=13)]
    rb = recent["source_brand"].astype(str)
    recent_line = np.select([rb.isin(BAR), rb.eq("BUILT SOUR PUFF")], ["BAR", "SOUR PUFF"], "PUFF")
    units13 = recent.groupby(recent_line)["base_units"].sum().to_dict()
    print(f"anchor {anchor.date()} | modeled series {len(last):,} (lapsed excluded {len(lapsed_keys):,})")
    out = {"anchor": str(anchor.date()), "model_version": meta.get("model_version"), "horizons": {},
           "series_by_line": last["line"].value_counts().to_dict(),
           "base_units_last13w_by_line": {k: float(v) for k, v in units13.items()}}
    for h in HORIZONS:
        X = last.copy()
        tw = float((anchor + pd.Timedelta(weeks=h)).isocalendar().week)
        X["week_sin"], X["week_cos"] = np.sin(2 * np.pi * tw / 52), np.cos(2 * np.pi * tw / 52)
        X["week_sin26"], X["week_cos26"] = np.sin(2 * np.pi * tw / 26), np.cos(2 * np.pi * tw / 26)
        contrib = models[h]["q50"].predict(X[feats], pred_contrib=True)[:, :-1]   # last column = base value
        C = pd.DataFrame(np.abs(contrib), columns=feats)
        C["line"] = X["line"].values
        res = {}
        for ln, g in C.groupby("line"):
            m = g[feats].mean()
            share = m / m.sum()
            fam = share.groupby(share.index.map(fam_of)).sum().sort_values(ascending=False)
            res[ln] = {"n_series": int(len(g)),
                       "families": {k: round(100 * v, 1) for k, v in fam.items()},
                       "top_inputs": {k: round(100 * v, 1) for k, v in share.sort_values(ascending=False).head(6).items()},
                       "product_line_input_share": round(100 * float(share["source_brand"]), 2)}
            print(f"\nh{h} {ln} (n={len(g)}): " + "; ".join(f"{k} {v:.1f}%" for k, v in res[ln]["families"].items()))
            print("   top: " + "; ".join(f"{k} {v}%" for k, v in res[ln]["top_inputs"].items())
                  + f" | product-line input {res[ln]['product_line_input_share']}%")
        out["horizons"][h] = res
    Path("../outputs/mo151_inputs_by_line.json").write_text(json.dumps(out, indent=2))
    print("\nwrote ../outputs/mo151_inputs_by_line.json")


if __name__ == "__main__":
    main()
