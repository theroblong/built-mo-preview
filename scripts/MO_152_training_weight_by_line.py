"""MO_152 - How much does each product line (BAR, PUFF, SOUR PUFF) weigh in TRAINING the served forecast model?

# protocol: not-a-forecast-arm

WHERE THIS CAME FROM: MO_151 explained the served v11d model's forecasts for the 1,604 active series (46 BAR, 1,282 PUFF,
276 SOUR PUFF). Jason (2026-10-14): how do those counts affect the model's weights; does PUFF have more influence because
of data recency and quantity? MO_151's counts are the series being FORECAST, not the data the model LEARNED from; this
script measures the latter. Descriptive only: no model is trained or scored.

METHOD: rebuild MO_26D's training rows for horizons 1, 4 and 13 (same panel rules via MO_27D.build_panel, target =
base_units h weeks ahead by row shift, train rows = target week <= the v11d validation cutoff) and MO_26D's recency weight
exp(-0.02 x weeks before the newest training row). The loss is the 0.5 quantile (pinball) on log1p(units): every row's
pull on the fit has the same size (0.5 x its weight) regardless of the item's volume, so a line's influence on the
trees is its share of WEIGHTED ROWS. Each row is assigned to a line by its own source_brand (the label the model saw
for that week). The panel file predates v11d's training (same 96,369 rows and 2,117 series as its metrics record), so
these are the rows v11d learned from. Skeptic 2026-10-14: SURVIVES WITH CAVEATS -- the weighted-row share measures the
parts of the model the lines share; product line is also an input, so BAR's own branches are set by BAR's rows alone.
The units share sums origin-week units. Early-stopping (validation) rows, which choose the number of trees, are
unweighted and 12-15% SOUR PUFF, 1-2% BAR.
Output: outputs/mo152_training_weight_by_line.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import MO_27D_direct_forecast as F

HORIZONS = (1, 4, 13)
LAMBDA = 0.02                      # MO_26D_direct_multihorizon_train.py:70
BAR = ("BUILT BAR", "BUILT")


def line_of(b: pd.Series) -> np.ndarray:
    b = b.astype(str)
    return np.select([b.isin(BAR), b.eq("BUILT SOUR PUFF")], ["BAR", "SOUR PUFF"], "PUFF")


def main() -> None:
    meta = json.loads(Path("outputs/direct_multihorizon_metrics_v11d.json").read_text())
    feats = meta["features_used"]
    cut = pd.Timestamp(meta["val_cutoff"], tz="UTC")
    df = F.build_panel(feats)
    print(f"panel now {len(df):,} rows (v11d trained on {meta['panel_rows']:,}); val cutoff {cut.date()}; "
          f"trained_at {meta['trained_at'][:10]}")
    df["line"] = line_of(df["source_brand"])
    g = df.groupby(F.GROUP_COLS, observed=True)
    out = {"val_cutoff": str(cut.date()), "panel_rows_now": int(len(df)), "panel_rows_v11d": meta["panel_rows"],
           "horizons": {}}
    for h in HORIZONS:
        d = df[["__time", "line", "base_units"]].copy()
        d["y"] = g["base_units"].shift(-h)
        d = d.dropna(subset=["y"])
        tr = d[d["__time"] + pd.Timedelta(weeks=h) <= cut].copy()
        wk = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        tr["w"] = np.exp(-LAMBDA * wk)
        tr["year"] = tr["__time"].dt.year
        by = tr.groupby("line").agg(rows=("w", "size"), weighted=("w", "sum"), units=("base_units", "sum"))
        for c in ("rows", "weighted", "units"):
            by[c + "_pct"] = 100 * by[c] / by[c].sum()
        yr = (tr.pivot_table(index="year", columns="line", values="w", aggfunc="sum", fill_value=0)
              .pipe(lambda t: 100 * t / t.values.sum()))
        recent = tr[tr["__time"] > tr["__time"].max() - pd.Timedelta(weeks=26)]
        r26 = recent.groupby("line")["w"].sum()
        out["horizons"][h] = {
            "train_rows": int(len(tr)), "newest_train_week": str(tr["__time"].max().date()),
            "by_line": {ln: {k: round(float(v), 1) for k, v in row.items()} for ln, row in by.iterrows()},
            "weighted_share_by_year_pct": {int(y): {ln: round(float(v), 1) for ln, v in row.items()}
                                           for y, row in yr.iterrows()},
            "weighted_share_last26w_pct": {ln: round(float(100 * v / r26.sum()), 1) for ln, v in r26.items()},
            "weight_of_row_1y_old": round(float(np.exp(-LAMBDA * 52)), 3),
            "weight_of_row_2y_old": round(float(np.exp(-LAMBDA * 104)), 3)}
        print(f"\nh{h}: {len(tr):,} training rows, newest week {tr['__time'].max().date()}")
        print(by[["rows", "rows_pct", "weighted_pct", "units_pct"]].round(1).to_string())
        print("weighted share by year (% of all weight):\n" + yr.round(1).to_string())
        print("last 26 weeks, weighted share:", out["horizons"][h]["weighted_share_last26w_pct"])
    Path("../outputs/mo152_training_weight_by_line.json").write_text(json.dumps(out, indent=2))
    print("\nwrote ../outputs/mo152_training_weight_by_line.json")


if __name__ == "__main__":
    main()
