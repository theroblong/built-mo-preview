#!/usr/bin/env python
"""MO_143 step 2 - build the Meijer singles add-on (Word, PDF, editable HTML) from MO_143 / MO_143b results.

PLAIN WORDS: a short companion to the Meijer Account Brief v2 on Brian's question "should Meijer add BUILT singles
at the checkouts?". Uses only skeptic-corrected wording (README/memory 2026-10-13): Target and Walmart are the only
retailers that added singles to an established 4-pack set; they run singles as seasonal programs; at Target's 2025
holiday program most singles bars were additional (between none and just under half came out of 4-packs, not
pinned down); typical singles sales per store by channel; flavors; price per bar. Adds a what-if for Meijer
(scenarios, not a forecast) and a store test design. Reuses the brief's renderers (MO_142_build_brief.py).
Output: docs/briefs/meijer_v2/Meijer_Singles_Addendum_2026-10-13.{docx,pdf,html} + charts/9_singles_programs.png
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (document builder; scenario arithmetic only)
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import MO_142_build_brief as BB

SRC = Path("outputs/mo143")
CACHE = Path("outputs/meijer_v2")
STEM = "Meijer_Singles_Addendum_2026-10-13"
L13 = pd.Timestamp("2026-06-14")
MEIJER_STORES = 280
# scenario sales rates (per store selling, per item, per week) are computed in build(): convenience median, grocery
# median (Meijer excluded), Target's rate applied to every store (an upper reading)
SCEN_SHARE = (0.0, 0.25, 0.45)         # share of singles bars that come out of 4-packs: none .. just under half
ITEMS = 4


def load():
    b = pd.read_parquet(CACHE / "_cache_built.parquet")
    g = pd.read_parquet(CACHE / "_cache_geos.parquet")
    b["__time"] = pd.to_datetime(b["__time"])
    for k in ("base_units", "stores_selling", "base_dollars", "source_pack_count", "store_count"):
        b[k] = pd.to_numeric(b[k], errors="coerce").fillna(0)
    b["bars"] = b.base_units * b.source_pack_count
    return b.merge(g[["geography_raw", "channel", "retail_account"]], on="geography_raw", how="left")


def chart_programs(ramp: pd.DataFrame) -> Path:
    r = ramp.copy()
    r["__time"] = pd.to_datetime(r["__time"])
    m = (r.set_index("__time").groupby("retailer").resample("MS").agg({"bu": "sum", "ss": "sum", "share_of_stores": "max"})
         .reset_index())
    m = m[m.__time >= "2025-06-01"]
    m["per"] = m.bu / m.ss
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 2.9))
    for ret, col, ls in (("Target", BB.RED, "-"), ("Walmart", BB.DEEP, "--")):
        x = m[m.retailer == ret]
        a1.plot(x.__time, 100 * x.share_of_stores, color=col, lw=2, ls=ls)
        BB.end_label(a1, x.__time.iloc[-1], 100 * x.share_of_stores.iloc[-1], ret, col)
        y = x[x.ss >= 1000]
        a2.plot(y.__time, y.per, color=col, lw=2, ls=ls, marker="o", ms=3)
        BB.end_label(a2, y.__time.iloc[-1], y.per.iloc[-1], ret, col)
    a1.set_ylabel("% of stores carrying\nBUILT singles (at least)", fontsize=8.5)
    a1.set_ylim(0, 100)
    a2.set_ylabel("Singles sold per store selling,\nper item, per week", fontsize=8.5)
    a2.set_ylim(0, None)
    a1.set_title("Singles in stores (monthly peak)", fontsize=9, color=BB.NAVY, loc="left")
    a2.set_title("Sales per store (months with 1,000+ store-weeks)", fontsize=9, color=BB.NAVY, loc="left")
    for ax in (a1, a2):
        BB.style(ax)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b\n%y"))
        ax.set_xlim(None, pd.Timestamp("2026-12-15"))
    fig.tight_layout()
    return BB.save(fig, "9_singles_programs")


def retailer_velocity(b: pd.DataFrame) -> pd.DataFrame:
    s = b[(b.__time >= L13) & (b.source_pack_count == 1) & (b.base_units > 0) & (b.stores_selling > 0)
          & (b.retail_account != "MEIJER")]   # Meijer is the subject, not a benchmark (1 single in 1 store)
    r = s.groupby(["channel", "retail_account"]).agg(bu=("base_units", "sum"), ss=("stores_selling", "sum"))
    r["per"] = r.bu / r.ss
    return r.reset_index()


def build(b: pd.DataFrame, chart: Path) -> list[tuple]:
    E: list[tuple] = []
    rv = retailer_velocity(b)
    med = rv.groupby("channel").per.median()
    wawa = rv[rv.retail_account == "WAWA"].per.iloc[0]
    ramp = pd.read_csv(SRC / "q2_singles_ramp.csv", parse_dates=["__time"])
    flav = pd.read_csv(SRC / "q2_flavors_l13.csv")
    cflav = pd.read_csv(SRC / "q3_convenience_flavors.csv")
    l13 = b[b.__time >= L13]
    pr = {}
    for ret in ("TARGET", "WALMART"):
        x = l13[(l13.retail_account == ret)]
        pr[ret] = {pk: x[x.source_pack_count == pk].base_dollars.sum() / max(x[x.source_pack_count == pk].bars.sum(), 1)
                   for pk in (1, 4)}
    mj = l13[(l13.retail_account == "MEIJER") & (l13.source_pack_count == 4)]
    mj_weeks = mj.__time.nunique()
    mj_bars_store_wk = mj.bars.sum() / mj_weeks / MEIJER_STORES
    mj_ppb4 = mj.base_dollars.sum() / mj.bars.sum()
    ppb1 = np.mean([pr["TARGET"][1], pr["WALMART"][1]])

    tgt_rate = rv[rv.retail_account == "TARGET"].per.iloc[0]
    SCEN_VEL = {"Low (typical convenience chain)": med["Convenience"], "Mid (typical grocer)": med["Food"],
                "High (Target's rate, applied to every store)": tgt_rate}
    lo_b, hi_b = min(SCEN_VEL.values()) * ITEMS * MEIJER_STORES, max(SCEN_VEL.values()) * ITEMS * MEIJER_STORES
    allstore = {}
    for ret in ("TARGET", "WALMART"):
        x = l13[(l13.retail_account == ret) & (l13.source_pack_count == 1)]
        st = l13[l13.retail_account == ret].groupby("__time").store_count.max()
        allstore[ret] = (x.bars.sum() / x.__time.nunique() / st.mean(), x[x.base_units > 0].upc.nunique())
    rw = ramp[(ramp.retailer == "Walmart") & (ramp.__time >= L13)].share_of_stores
    wm_share = (100 * rw.mean(), 100 * rw.min(), 100 * rw.max())
    n_food, n_conv = int((rv.channel == "Food").sum()), int((rv.channel == "Convenience").sum())
    E.append(("title", "Meijer Singles at Checkout"))
    E.append(("subtitle", "What other retailers show, what it could mean at Meijer, and how to test it"))
    E.append(("meta", "Add-on to the Meijer Account Brief v2  ·  Data: SPINS weekly, each retailer's own stores, through "
                      "Sept 6, 2026  ·  Period: last 13 weeks (June 14 – Sept 6, 2026) unless a table says otherwise"))
    E.append(("meta", "Issued October 13, 2026 · prepared by Aevah (Mo) for BUILT"))
    E.append(("h1", "Summary"))
    E.append(("bullets", [
        "Meijer is the only grocery account that sells BUILT 4-packs with essentially no singles (one single in one "
        "store in the last two weeks of data). Every other grocer started "
        "with singles. The only retailers that added singles to an established 4-pack set are Target and Walmart, "
        "both supercenters like Meijer.",
        "Both run singles as seasonal programs: in most stores for a few months, then back to a core of stores. "
        "Target put singles in roughly 70% of its stores for the 2025 holidays and in most stores again this summer.",
        "When Target added singles for the 2025 holidays, most of the singles bars were additional sales for BUILT. "
        "Its 4-packs sold somewhat less than expected, but the size cannot be pinned down because Target added four "
        "new 4-pack flavors at the same time. Depending on the comparison, between none and just under half of the "
        "singles bars came out of 4-packs.",
        f"A typical grocer sells about {med['Food']:.1f} singles per item per store per week, a typical convenience "
        f"chain about {med['Convenience']:.1f} (Wawa {wawa:.1f}), and Target about {tgt_rate:.1f} with singles in most stores. "
        f"Singles sell for about 13% more per bar than 4-packs.",
        f"At Meijer, {ITEMS} checkout singles in all stores could sell roughly {round(lo_b, -2):,.0f}–{round(hi_b, -2):,.0f} bars a week "
        f"(scenarios below). "
        "In these scenarios, even if close to half came out of 4-packs, BUILT would gain bars and dollars. This is a "
        "scenario, not a forecast.",
        "Recommended: a 13-week test in a set of Meijer stores, compared with matched stores without singles, outside "
        "the holiday season, using Meijer's store-level sales.",
    ]))
    E.append(("h1", "1 — Who is comparable to Meijer"))
    E.append(("p", "Every grocery account with BUILT singles (Kroger, Publix, Albertsons, Hy-Vee, Giant Eagle, Wegmans "
                   "and others) carried singles before 4-packs, so none shows what happens when singles join an "
                   "established 4-pack set. Target and Walmart did exactly that, and like Meijer they are supercenters."))
    E.append(("h1", "2 — How Target and Walmart run singles"))
    E.append(("img", chart, "Left: share of stores carrying BUILT singles (the most widely stocked single; a floor on "
                            "stores with any single). Right: singles sold per store selling, per item, per week."))
    E.append(("bullets", [
        "Target: singles in about 10% of stores in early October 2025, about 70% on average in November–December "
        "(53–83% week to week, including a holiday flavor), back to about 16% from February to May, then 82–91% "
        "from June to September 2026.",
        "Walmart: about 40% of stores in February–March 2026, fading gradually (26% in April, 9% in July), then "
        "about 37% again in August–September.",
        "The stores that keep singles in the off-season are self-selected strong stores, so their higher sales per "
        "store are not a benchmark for a full rollout.",
    ]))
    E.append(("h1", "3 — Did singles take sales from 4-packs?"))
    E.append(("p", "One season can be measured: Target's 2025 holiday program, compared with the weeks just before and "
                   "after it, with the same 4-pack items at grocery retailers removing BUILT-wide seasonality."))
    E.append(("table", ["What we can say", "Detail"], [
        ["Direction", "4-packs sold somewhat less than expected while singles were in most stores"],
        ["Size", "Not pinned down: between none and just under half of the singles bars came out of 4-packs, "
                 "depending on which weeks are compared"],
        ["Why it is uncertain", "Target added four new 4-pack flavors (late Sept – mid Oct 2025) right before the program"],
        ["In every version", "Most singles bars were additional bars for BUILT"],
        ["Walmart", "Not measurable: its singles fade in and out gradually, with no clean before and after"]],
        "One retailer and one holiday season. This describes what happened there, not what will happen at Meijer's "
        "checkouts; SPINS does not show where in the store the singles were placed."))
    E.append(("h1", "4 — How much singles sell"))
    rows = [[f"Typical grocer (middle of {n_food} grocery accounts)", f"{med['Food']:.1f}"],
            [f"Typical convenience chain (middle of {n_conv})", f"{med['Convenience']:.1f}"],
            ["Wawa", f"{wawa:.1f}"],
            ["Target (singles in most stores)", f"{rv[rv.retail_account == 'TARGET'].per.iloc[0]:.1f}"],
            [f"Walmart (about one store in five on average, {wm_share[1]:.0f}–{wm_share[2]:.0f}%)",
             f"{rv[rv.retail_account == 'WALMART'].per.iloc[0]:.1f}"]]
    E.append(("table", ["Where", "Singles sold per store selling, per item, per week"], rows,
              "Last 13 weeks. Units per store selling per item: the right unit for planning a few checkout items. "
              "Middle = median retailer, so one large chain does not set the figure."))
    E.append(("h2", "Flavors"))
    cf = cflav.head(6)
    rows = [[r.flavor, f"{r.units_per_store_wk:.2f}", str(int(r.retailers))] for _, r in cf.iterrows()]
    E.append(("table", ["Top singles at convenience chains", "Per store selling per week", "Chains selling it"], rows,
              "Convenience stores are the closest SPINS view of impulse buying. Cookie Dough Chunk and Brownie Batter "
              "lead, with Coconut close behind; all three are main Meijer 4-pack flavors. Salted Caramel ranks third but "
              "only 3 chains sell it, and the gaps are small. At Target, Peanut Butter and Brownie Batter rank highest, "
              "but items in fewer stores show higher sales per store, so that ranking is not an apples-to-apples "
              "comparison."))
    E.append(("h2", "Price"))
    E.append(("table", ["Retailer", "Singles, per bar", "4-packs, per bar", "Singles premium"], [
        [r.title(), f"${pr[r][1]:.2f}", f"${pr[r][4]:.2f}", f"{100 * (pr[r][1] / pr[r][4] - 1):.0f}%"] for r in ("TARGET", "WALMART")],
        "Typical non-promoted price, last 13 weeks. Price and cannibalization are separate analyses."))
    E.append(("h1", "5 — What it could mean at Meijer (scenarios, not a forecast)"))
    E.append(("p", f"Assumptions: {ITEMS} singles at checkout in all {MEIJER_STORES} Meijer stores; sales per store from "
                   f"section 4; a single at about ${ppb1:.2f}; Meijer's 4-pack bars at about ${mj_ppb4:.2f} each; "
                   f"Meijer's 4-packs now sell about {mj_bars_store_wk:.0f} bars per store per week. The share taken from "
                   f"4-packs covers the range seen at Target (none to just under half). Sales rates come from stores that "
                   f"sold each item that week, often a retailer's stronger stores; applying them to all {ITEMS} items in "
                   f"all {MEIJER_STORES} stores every week is an upper reading. For comparison, across all its stores "
                   f"Target sells about {allstore['TARGET'][0]:.0f} singles bars per store per week from "
                   f"{allstore['TARGET'][1]} items, and Walmart about {allstore['WALMART'][0]:.0f} from "
                   f"{allstore['WALMART'][1]}."))
    rows = []
    for name, v in SCEN_VEL.items():
        bars = v * ITEMS * MEIJER_STORES
        dol = bars * ppb1
        for sh in SCEN_SHARE:
            lost_bars = bars * sh
            net_bars = bars - lost_bars
            net_dol = dol - lost_bars * mj_ppb4
            rows.append([name, f"{100 * sh:.0f}%", f"{bars:,.0f}", f"${dol:,.0f}", f"{net_bars:,.0f}", f"${net_dol:,.0f}",
                         f"+{100 * net_bars / MEIJER_STORES / mj_bars_store_wk:.0f}%"])
    E.append(("table", ["Sales per store", "Share from 4-packs", "Singles bars per week", "Singles retail $ per week",
                        "Net new BUILT bars per week", "Net new retail $ per week", "Change in BUILT bars at Meijer"], rows,
              "Retail dollars at shelf price, before Meijer's margin; BUILT's revenue is its selling price to Meijer. "
              "Estimates from other retailers' patterns; checkout placement may sell differently from where singles sit "
              "at those retailers. Before checkout placement fees and BUILT's cost per single bar."))
    E.append(("h1", "6 — How to test it at Meijer"))
    E.append(("bullets", [
        "Put 3–4 singles at the checkouts in a set of test stores (the number to be set from Meijer's store-level "
        "sales so the test can detect a 5–10% change in 4-pack sales), and pick matched control stores with similar "
        "BUILT 4-pack sales and region.",
        "Keep the 4-pack lineup and promotions the same in test and control stores; new flavors are why Target's "
        "result is uncertain. Compare with at least 13 weeks before the test.",
        "Run at least 13 weeks, outside November–December, so holiday traffic does not blur the result.",
        "Measure, test vs control: BUILT 4-pack non-promoted units per store per week (did 4-packs lose?), singles sold per "
        "store per week, and total BUILT bars and dollars per store.",
        "This needs Meijer's store-level sales for the test and control stores. SPINS reports Meijer as one total, so "
        "it cannot show the difference between test and control stores.",
        "Decide on total BUILT bars and dollars per store, not on 4-packs alone: some overlap is expected and is fine "
        "as long as the total grows.",
    ]))
    E.append(("h1", "Sources and caveats"))
    E.append(("bullets", [
        "SPINS weekly data, each retailer's own stores (RMA), through Sept 6, 2026. Prepared by Aevah with Mo.",
        "SPINS does not record shelf location, so checkout and aisle placement cannot be separated anywhere in this "
        "add-on.",
        "Target and Walmart are the only analogs, with one measurable season (Target, holidays 2025). Results describe "
        "what happened there; they are not proof of cause and not a forecast for Meijer.",
        "The scenarios in section 5 multiply other retailers' sales per store by Meijer's store count; they are a "
        "sizing aid, and the store test is the way to measure Meijer itself.",
        "Internal to BUILT and Aevah. Not for distribution outside BUILT.",
    ]))
    return E


def main() -> None:
    (BB.OUT / "charts").mkdir(parents=True, exist_ok=True)
    b = load()
    chart = chart_programs(pd.read_csv(SRC / "q2_singles_ramp.csv"))
    E = build(b, chart)
    BB.VERSION, BB.ISSUED = "Singles add-on", "October 13, 2026"
    docx_p, pdf_p, html_p = BB.OUT / f"{STEM}.docx", BB.OUT / f"{STEM}.pdf", BB.OUT / f"{STEM}.html"
    BB.render_docx(E, docx_p)
    from docx import Document
    dd = Document(docx_p)
    dd.core_properties.title = "Meijer Singles at Checkout"
    dd.save(docx_p)
    BB.render_html(E, html_p)
    html_p.write_text(html_p.read_text(encoding="utf-8").replace("Meijer Account Brief v2</title>", "Meijer Singles at Checkout</title>")
                      .replace("Meijer Account Brief · v2</b>", "Meijer Singles at Checkout · add-on</b>")
                      .replace("Meijer_BUILT_Assortment_Brief_v2_edited.html", "Meijer_Singles_Addendum_edited.html"),
                      encoding="utf-8")
    print("wrote", docx_p, html_p)
    print("pdf", "ok" if BB.to_pdf(docx_p, pdf_p) else "FAILED", pdf_p)


if __name__ == "__main__":
    main()
