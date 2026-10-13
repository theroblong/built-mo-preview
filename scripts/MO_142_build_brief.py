#!/usr/bin/env python
"""MO_142 step 2 - build the Meijer assortment brief, version 2, in three formats from one content list.

PLAIN WORDS: takes the numbers MO_142 produced (scripts/outputs/meijer_v2/) and writes the brief Brian asked for:
  - Word (.docx): the main editable copy (Brian edits in Word; HTML was hard for him to work with)
  - PDF: exported by Microsoft Word from that .docx, so it matches the Word copy page for page
  - HTML: the same content, every text block and table cell editable in the browser, with
          'Save edited copy' and 'Print / Save as PDF' buttons (works when opened as a file in a normal browser)
Charts are drawn once (matplotlib PNG) and used in all three. Section order follows Brian's Oct 2026 comments.
Output: docs/briefs/meijer_v2/
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (document builder; no model is fit here)
import argparse
import base64
import html
import json
import subprocess
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_ORIENT  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

SRC = Path("outputs/meijer_v2")
VERSION, ISSUED = "v2", "October 13, 2026"
STEM = "Meijer_BUILT_Assortment_Brief_v2_2026-10-13"
OUT = Path("../docs/briefs/meijer_v2")
L13_START, END = pd.Timestamp("2026-06-14"), pd.Timestamp("2026-09-06")
PERIOD = "13 weeks ending Sept 6, 2026 (June 14 – Sept 6)"
STORES = 280
# BUILT color theme (docs/BUILTcolortheme.yaml)
RED, NAVY, BLUE, DEEP, LIGHT, MUTED, BORDER, SUCC, WARN = ("#EB2134", "#0D1733", "#2D7FF9", "#214E9D", "#6BA8FF",
                                                           "#7D879C", "#D5DBE8", "#1FA971", "#F5A524")
CORE = {"08-40229-30380": "Brownie Batter 4pk", "08-40229-30381": "Coconut 4pk", "08-40229-30558": "Cookie Dough 4pk",
        "08-40229-30646": "Peanut Butter Cup 4pk", "08-40229-30581": "Cookies N Cream 4pk"}
NEW2 = ["08-40229-30646", "08-40229-30581"]
OLD3 = ["08-40229-30380", "08-40229-30381", "08-40229-30558"]
AUG = {"08-40229-30696": "Rocky Road 4pk", "08-40229-30697": "Orange Cream Pop 4pk", "08-40229-30571": "Mint Chip 4pk"}
SINGLES = {"08-40229-30037": "Coconut 1pk", "08-40229-30362": "Brownie Batter 1pk"}


def fmt(x, d=0, pct=False, money=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    if money:
        return f"${x:,.2f}"
    s = f"{x:,.{d}f}"
    return s + "%" if pct else s


def sg(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace("-", "−")


def times(r: float) -> str:
    return {1: "about as strongly as", 2: "about twice as strongly as", 3: "about three times as strongly as"}.get(
        int(round(r)), f"about {r:.1f} times as strongly as")


def rate_words(r: float) -> str:
    return f"about {round(r * 100):d} of every 100"


# ---------------------------------------------------------------- data
class D:
    pass


def load() -> D:
    d = D()
    d.own = pd.read_csv(SRC / "own_weekly.csv", parse_dates=["week"])
    d.ev = pd.read_csv(SRC / "launch_events.csv", parse_dates=["anchor"])
    d.items = pd.read_csv(SRC / "launch_per_item.csv", parse_dates=["anchor"])
    d.pooled = pd.read_csv(SRC / "launch_pooled.csv")
    d.placebo = pd.read_csv(SRC / "placebo.csv", parse_dates=["anchor"])
    d.new2 = pd.read_csv(SRC / "newest_two_weekly.csv", parse_dates=["__time"])
    d.price = pd.read_csv(SRC / "price_meijer_brands.csv")
    d.packs = pd.read_csv(SRC / "price_4ct_vs_1ct_peer_food.csv")
    d.pos = pd.read_csv(SRC / "price_position_meijer.csv")
    d.summary = json.loads((SRC / "summary.json").read_text())
    d.m = pd.read_parquet(SRC / "_cache_meijer_all.parquet")
    d.m["__time"] = pd.to_datetime(d.m["__time"])
    for c in ("base_units", "units", "stores_selling", "dollars", "base_dollars", "source_pack_count"):
        d.m[c] = pd.to_numeric(d.m[c], errors="coerce")
    return d


def geo_names(geos: list[str]) -> list[str]:
    g = pd.read_parquet(SRC / "_cache_geos.parquet").set_index("geography_raw").retail_account
    return [g.get(x, x).title() for x in geos]


def item_table(m: pd.DataFrame, upcs: dict, since=L13_START) -> list[list[str]]:
    rows = []
    for u, name in upcs.items():
        g = m[m.upc == u].sort_values("__time")
        sold = g[g.base_units > 0]
        first = sold.__time.min()
        l = g[(g.__time >= max(since, first)) & (g.__time <= END)]
        wk = l.__time.nunique()
        st = l.stores_selling.mean()
        bu = l.base_units.sum() / wk if wk else np.nan
        per = l.base_units.sum() / l.stores_selling.sum() if l.stores_selling.sum() else np.nan
        ppb = l.dollars.sum() / l.units.sum() / 4 if l.units.sum() else np.nan
        bppb = l.base_dollars.sum() / l.base_units.sum() / 4 if l.base_units.sum() else np.nan
        rows.append([name, u, first.strftime("%b %d, %Y"), fmt(st), fmt(100 * st / STORES, 0, pct=True), fmt(bu),
                     fmt(per, 1), fmt(ppb, money=True), fmt(bppb, money=True), str(wk)])
    return rows


# ---------------------------------------------------------------- charts
def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BORDER)
    ax.tick_params(colors=NAVY, labelsize=8.5)
    ax.yaxis.label.set_color(NAVY)
    ax.grid(axis="y", color=BORDER, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def save(fig, name: str) -> Path:
    p = OUT / "charts" / f"{name}.png"
    fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


def end_label(ax, x, y, text, color):
    ax.annotate(text, (x, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5, color=color,
                fontweight="bold")


def items10(d: D) -> pd.Series:
    b = d.m[d.m.source_brand.str.startswith("BUILT") & (d.m.base_units > 0) & (d.m.stores_selling >= 10)]
    return b.groupby("__time").upc.nunique()


def chart_own(d: D) -> Path:
    a = d.own[d.own.pack == 0].set_index("week").sort_index()
    a["items_selling"] = items10(d).reindex(a.index).fillna(0)
    a = a[a.index >= "2023-10-08"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 4.2), sharex=True, gridspec_kw={"height_ratios": [2.4, 1]})
    s = a.base_units_per_store_week
    ax1.plot(s.index, s, color=BORDER, lw=0.8)
    r = s.rolling(4, min_periods=2).mean()
    ax1.plot(r.index, r, color=RED, lw=2)
    end_label(ax1, r.index[-1], r.iloc[-1], f"{r.iloc[-1]:.1f}", RED)
    ax1.set_ylabel("Base units per store\nper week (all BUILT)", fontsize=8.5)
    for t, lab, ha, dy in (("2025-04-20", "Cookie Dough", "right", 0.97), ("2026-04-19", "PB Cup +\nCookies N Cream", "right", 0.97),
                           ("2026-08-16", "3 Aug\nlaunches", "right", 0.12)):
        for ax in (ax1, ax2):
            ax.axvline(pd.Timestamp(t), color=MUTED, lw=0.8, ls=":")
        ax1.annotate(lab, (pd.Timestamp(t), ax1.get_ylim()[1] * dy), xytext=(-3, 0), textcoords="offset points",
                     ha=ha, va="top" if dy > 0.5 else "bottom", fontsize=7.5, color=MUTED)
    it = a.items_selling
    ax2.step(it.index, it, where="post", color=DEEP, lw=1.6)
    ax2.set_ylabel("BUILT items in\n10+ stores", fontsize=8.5)
    ax2.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 7]))
    ax2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%Y"))
    ax2.set_ylim(0, it.max() + 1.5)
    for ax in (ax1, ax2):
        style(ax)
    ax1.set_title("BUILT at Meijer stores: weekly base units per store (red = 4-week average)", fontsize=9.5,
                  color=NAVY, loc="left")
    return save(fig, "1_own_performance")


def chart_newest(d: D) -> Path:
    n = d.new2[(d.new2.__time >= "2026-01-04") & (d.new2.__time <= END)].copy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.1))
    tot = n.pivot_table(index="__time", columns="group", values="base_units", aggfunc="sum").fillna(0)
    ax1.stackplot(tot.index, tot["other three"], tot["newest two"], colors=[DEEP, RED], alpha=0.9,
                  labels=["Other three 4-packs", "Newest two 4-packs"])
    ev = d.ev[(d.ev.geography_raw == "MEIJER CORP - RMA") & (d.ev.anchor == "2026-04-19")].iloc[0]
    exp_old = ev.existing_pre_all * ev.category_factor
    post = pd.date_range("2026-05-03", "2026-07-26", freq="7D")
    ax1.plot(post, [exp_old] * len(post), color=NAVY, ls="--", lw=1.4)
    ax1.annotate("Other three: expected\nwithout the launch", (post[0], exp_old), xytext=(-6, -40), textcoords="offset points",
                 ha="right", fontsize=7.5, color=NAVY, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BORDER, lw=0.6),
                 arrowprops=dict(arrowstyle="-", color=NAVY, lw=0.6))
    ax1.set_ylabel("Weekly base units", fontsize=8.5)
    ax1.legend(loc="upper left", fontsize=7.5, frameon=False)
    ax1.set_title("Total weekly base units", fontsize=9, color=NAVY, loc="left")
    vel = n.groupby(["__time", "group"]).apply(lambda g: g.base_units.sum() / g.stores_selling.sum()
                                               if g.stores_selling.sum() > 0 else np.nan).unstack()
    vel = vel.rolling(4, min_periods=2).mean()
    for grp, col, ls in (("other three", DEEP, "-"), ("newest two", RED, "--")):
        s = vel[grp].dropna()
        ax2.plot(s.index, s, color=col, lw=2, ls=ls)
        end_label(ax2, s.index[-1], s.iloc[-1], f"{grp.capitalize()} {s.iloc[-1]:.1f}", col)
    ax2.set_ylabel("Base units per store selling,\nper item per week (4-wk avg)", fontsize=8.5)
    ax2.set_ylim(0, None)
    ax2.set_title("Sales per store, per item", fontsize=9, color=NAVY, loc="left")
    ax2.set_xlim(None, pd.Timestamp("2026-11-15"))
    for ax in (ax1, ax2):
        style(ax)
        ax.axvline(pd.Timestamp("2026-04-19"), color=MUTED, lw=0.8, ls=":")
        ax.tick_params(axis="x", rotation=0)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    fig.tight_layout()
    return save(fig, "3_newest_two")


def chart_channels(d: D) -> Path:
    ok = d.ev[(d.ev.status == "ok") & d.ev.measurable.astype(bool) & (d.ev.channel == "Food")].copy()
    oth = ok[ok.retail_account != "MEIJER"]
    q1, q3 = oth.rate_v_all.quantile([0.25, 0.75])
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    ax.axhspan(q1, q3, color=LIGHT, alpha=0.18, lw=0)
    ax.axhline(oth.rate_v_all.median(), color=DEEP, lw=1.2, ls="--")
    end_label(ax, pd.Timestamp("2026-09-20"), oth.rate_v_all.median(), "middle launch", DEEP)
    v = oth.rate_v_all.clip(-1.5, 3)
    ax.scatter(oth.anchor, v, s=22, color=DEEP, alpha=0.75, zorder=3)
    mj = ok[ok.retail_account == "MEIJER"]
    ax.scatter(mj.anchor, mj.rate_v_all, s=70, color=RED, marker="D", zorder=4)
    for _, r in mj.iterrows():
        ax.annotate(f"Meijer {r.rate_v_all:.2f}", (r.anchor, r.rate_v_all), xytext=(0, -14), textcoords="offset points",
                    ha="center", fontsize=8, color=RED, fontweight="bold")
    ax.axhline(0, color=MUTED, lw=0.8)
    n_clip = int(((oth.rate_v_all > 3) | (oth.rate_v_all < -1.5)).sum())
    ax.text(0.01, 0.97, f"{n_clip} launches beyond the scale are drawn at the edge", transform=ax.transAxes,
            fontsize=7, color=MUTED, va="top")
    ax.set_ylabel("Share of new items' sales\ntaken from existing BUILT items", fontsize=8.5)
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%Y"))
    ax.set_xlim(None, pd.Timestamp("2027-01-15"))
    ax.set_title("BUILT launches at Food-channel retailers (shaded = middle half of launches)", fontsize=9,
                 color=NAVY, loc="left")
    style(ax)
    return save(fig, "6_channel_trend")


def chart_price(d: D) -> Path:
    p = d.price[d.price.group != "OTHER BARS"].sort_values("estimate")
    fig, ax = plt.subplots(figsize=(6.4, 0.32 * len(p) + 0.9))
    for i, (_, r) in enumerate(p.iterrows()):
        c = RED if r.group == "BUILT" else DEEP
        ax.plot([r.p05, r.p95], [i, i], color=c, lw=1.6, alpha=0.6)
        ax.scatter([r.estimate], [i], color=c, s=36 if r.group == "BUILT" else 22, zorder=3)
    ax.set_yticks(range(len(p)), [g.title() if g != "BUILT" else "BUILT" for g in p.group], fontsize=8)
    for t in ax.get_yticklabels():
        if t.get_text() == "BUILT":
            t.set_color(RED)
            t.set_fontweight("bold")
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("% change in units per store for a 1% lower price (more negative = more price-responsive)", fontsize=8)
    ax.set_title("Price sensitivity at Meijer stores, last 104 weeks (dot = estimate, line = likely range)",
                 fontsize=9, color=NAVY, loc="left")
    style(ax)
    ax.grid(axis="x", color=BORDER, lw=0.6)
    ax.grid(axis="y", visible=False)
    return save(fig, "8_price")


# ---------------------------------------------------------------- content
def fade(d: D) -> list[tuple[str, float]]:
    """Cookie Dough 4pk launch at Meijer (2025-04-20): the older two 4-packs' gap vs the category-adjusted
    expectation in launch weeks 2-14, 15-27 and 28-40 (same 13-week pre window). Reproduces the skeptic's fade check."""
    b = pd.read_parquet(SRC / "_cache_built.parquet")
    b = b[b.geography_raw == "MEIJER CORP - RMA"].copy()
    b["__time"] = pd.to_datetime(b["__time"])
    c = pd.read_parquet(SRC / "_cache_category.parquet")
    c = c[c.geography_raw == "MEIJER CORP - RMA"].copy()
    c["__time"] = pd.to_datetime(c["__time"])
    cat = c.set_index("__time").cat_bu
    a = pd.Timestamp("2025-04-20")
    pre = pd.date_range(a - 13 * pd.Timedelta(weeks=1), a - pd.Timedelta(weeks=1), freq="7D")
    piv = b.pivot_table(index="__time", columns="upc", values="base_units", aggfunc="sum").fillna(0)
    old, new = ["08-40229-30380", "08-40229-30381"], "08-40229-30558"
    out = []
    for lo, hi in ((2, 14), (15, 27), (28, 40)):
        post = pd.date_range(a + lo * pd.Timedelta(weeks=1), a + hi * pd.Timedelta(weeks=1), freq="7D")
        f = cat.reindex(post).mean() / cat.reindex(pre).mean()
        e_pre = piv.reindex(pre)[old].sum(axis=1).mean()
        e_post = piv.reindex(post)[old].sum(axis=1).mean()
        out.append((f"weeks {lo}–{hi}", (e_pre * f - e_post) / piv.reindex(post)[new].mean()))
    return out


def build_blocks(d: D, charts: dict) -> list[tuple]:
    B: list[tuple] = []
    ev = d.ev
    mj = ev[(ev.geography_raw == "MEIJER CORP - RMA") & (ev.status == "ok")].set_index("anchor")
    apr = mj.loc[pd.Timestamp("2026-04-19")]
    cd = mj.loc[pd.Timestamp("2025-04-20")]
    ok = ev[(ev.status == "ok") & ev.measurable.astype(bool)]
    food_x = ok[(ok.channel == "Food") & (ok.retail_account != "MEIJER")].rate_v_all
    f_med, f_q1, f_q3 = food_x.median(), food_x.quantile(0.25), food_x.quantile(0.75)
    fd = fade(d)
    a = d.own[d.own.pack == 0].copy()
    a["items_selling"] = a.week.map(items10(d)).fillna(0)
    a["q"] = a.week.dt.to_period("Q")
    qt = a.groupby("q").agg(per_store=("base_units_per_store_week", "mean"), per_item=("base_units_per_item_store_week", "mean"),
                            items=("items_selling", "mean"), share=("built_share_of_bars_pct", "mean"),
                            bu=("base_units", "mean"), weeks=("week", "nunique"))
    q_last, q_peak = qt.iloc[-1], qt.loc[pd.Period("2025Q2")]
    price = d.price.set_index("group")
    built_e = price.loc["BUILT"]
    comp = price.drop(index=[i for i in ("BUILT", "OTHER BARS") if i in price.index])
    ratio = built_e.estimate / comp.estimate.median()
    packs = d.packs.set_index("group")
    pos = d.pos.set_index("grp")
    it = d.items[(d.items.geography_raw == "MEIJER CORP - RMA") & (d.items.anchor == "2026-04-19")]
    gaps = (100 * it.lost_weekly / it.expected_weekly)

    B.append(("title", "Meijer Account Brief"))
    B.append(("subtitle", "BUILT performance, 2026 launches, cannibalization and pricing at Meijer"))
    B.append(("meta", f"Account: Meijer (Meijer's own {STORES} stores)  ·  Channel: Food  ·  Period: {PERIOD}, "
                      f"unless a table says otherwise  ·  Data: SPINS weekly through Sept 6, 2026"))
    B.append(("meta", f"Version 2 · issued {ISSUED} · prepared by Aevah (Mo) for BUILT · replaces the Sept 25, 2026 version"))
    B.append(("h1", "Summary"))
    B.append(("bullets", [
        f"BUILT keeps growing at Meijer. BUILT sold {qt.iloc[0].per_store:.1f} packages (base units) per Meijer store per "
        f"week in late 2023 and {q_last.per_store:.1f} this quarter; its share of bar units went from "
        f"{qt.iloc[0].share:.1f}% to {q_last.share:.1f}%.",
        f"As the line widened, each item sells less per store: {q_peak.per_item:.1f} packages per store per week at the "
        f"Q2 2025 peak, with 3 main 4-packs, vs {q_last.per_item:.1f} now, with 5 main 4-packs plus 3 new flavors added in "
        f"August.",
        f"The newest two 4-packs (Peanut Butter Cup and Cookies N Cream, April 2026) were mostly new business. In their "
        f"first three months, for every 100 packages they sold, the older three 4-packs sold roughly 10–40 fewer than "
        f"expected, so roughly 60–90% of the pair's sales were new to BUILT. Each older 4-pack gave up about "
        f"{gaps.min():.0f}–{gaps.max():.0f}% of its expected sales.",
        "After the Cookie Dough launch in April 2025, the same pattern appeared and the older items' dip shrank after "
        "the first three months, so this first read may overstate the lasting effect.",
        f"Meijer's result is within the normal range for BUILT launches at other grocery (Food-channel) retailers. "
        f"Target and Walmart (Mass) could not be measured, because their launches came during store expansions.",
        "4-count vs 1-count cannibalization cannot be measured yet. Meijer sells almost no singles, and too few "
        "launches elsewhere had both pack sizes on the shelf. A planned singles test at Meijer would answer it.",
        f"During promotions, BUILT's sales at Meijer respond {times(ratio)} the typical "
        f"protein-bar competitor's. BUILT's regular price, {fmt(pos.loc['BUILT'].base_price_per_bar, money=True)} a "
        f"bar, sits at the premium end with Barebells and Quest.",
    ]))

    # 1 own performance
    B.append(("h1", "1 — How BUILT is performing at Meijer"))
    B.append(("meta", "Meijer stores, every week Oct 2023 – Sept 6, 2026 · base units = packages sold at regular price "
                      "(promotional lift removed); most BUILT packages at Meijer are 4-packs · per store = divided by "
                      "all Meijer stores"))
    B.append(("img", charts["own"], "Weekly BUILT base units per Meijer store (gray = weekly, red = 4-week average) and "
                                    "the number of BUILT items selling in 10 or more stores. Dotted lines mark launches."))
    rows = []
    for q, r in qt.iterrows():
        lab = f"Q{q.quarter} {q.year}" + (f" ({int(r.weeks)} weeks, to Sept 6)" if q == qt.index[-1] else "")
        rows.append([lab, fmt(r.bu), fmt(r.per_store, 1), fmt(r.per_item, 1), fmt(r["items"], 1), fmt(r.share, 1, pct=True)])
    B.append(("table", ["Quarter", "Weekly base units (all BUILT)", "Per Meijer store per week",
                        "Per item, per store selling, per week", "Items in 10+ stores (avg)", "BUILT share of bar units"],
              rows, "Quarterly averages of weekly values. Items counts BUILT items selling in at least 10 Meijer "
                    "stores that week. The latest quarter is partial and includes the three August flavors; leaving "
                    "them out, sales per item per store would be about the same (3.8)."))

    # 2 established 4-packs
    B.append(("h1", "2 — Established 4-pack set: current distribution"))
    B.append(("meta", f"Meijer stores · {PERIOD} · five main 4-packs"))
    B.append(("table", ["Item", "UPC", "First sold at Meijer", "Stores selling (avg)", "% of Meijer stores",
                        "Base units per week", "Per store selling per week", "Avg price paid per bar",
                        "Regular price per bar", "Weeks"], item_table(d.m, CORE),
              "Price paid includes promotions; regular price is the non-promoted price. Salted Caramel 4pk, listed in "
              "the Sept version, has no sales in Meijer's own stores."))

    # 3 per-SKU cannibalization profile (Brian: toward the top)
    B.append(("h1", "3 — Cannibalization: the newest two 4-packs vs the other three"))
    B.append(("meta", "Meijer stores · before = 13 weeks Jan 18 – Apr 12, 2026 · after = first three months, May 3 – "
                      "Jul 26, 2026 (the two ramp-up weeks and the August launches are left out)"))
    B.append(("p", "How we measure it: we compare each older item's sales after the launch with what it would have sold "
                   "if it had moved in line with the rest of Meijer's bar category. The gap, divided by the new items' "
                   "sales, is the share of the new items' sales that came out of BUILT's existing items. The rest is new "
                   "business for BUILT: shoppers switching from other brands or buying more bars."))
    B.append(("img", charts["newest"], "Left: total weekly base units of the newest two and the other three 4-packs; "
                                       "dashed line = what the other three would have sold without the launch. Right: "
                                       "base units per store selling, per item."))
    rows = []
    for _, r in it.iterrows():
        rows.append([CORE.get(r.upc, r.item), fmt(r.pre_weekly), fmt(r.expected_weekly), fmt(r.post_weekly),
                     sg(-r.lost_weekly, 0), sg(-100 * r.lost_weekly / r.expected_weekly, 0) + "%",
                     fmt(r.stores_pre), fmt(r.stores_post)])
    exp_tot = apr.existing_pre_all * apr.category_factor
    rows.append(["Other three, total", fmt(apr.existing_pre_all), fmt(exp_tot), fmt(apr.existing_post_all),
                 sg(-apr.lost_all, 0), sg(-100 * apr.lost_all / exp_tot, 0) + "%", "", ""])
    rows.append(["Newest two (PB Cup + Cookies N Cream)", "—", "—", fmt(apr.new_weekly), "", "", "", ""])
    B.append(("table", ["Item", "Before: base units per week", "After: expected", "After: actual", "Gap (per week)",
                        "Gap vs expected", "Stores selling before", "Stores selling after"], rows,
              f"Central estimate: the older three gave up about {apr.rate_all * 100:.0f} packages for every 100 the "
              f"newest two sold ({apr.rate_v_all * 100:.0f} counting sales per store only). With launches this size the "
              f"measure is uncertain by about ±30, hence 'roughly 10–40'. The two launched one week apart, so their "
              f"effects cannot be separated flavor by flavor."))
    B.append(("table", ["Cookie Dough 4pk launch (April 2025)", "Older items' gap per 100 Cookie Dough packages"],
              [[w, f"{r * 100:.0f}"] for w, r in fd],
              "Same measure for the previous Meijer launch: Brownie Batter and Coconut gave up sales in the first three "
              "months, and much less afterward. Both Meijer launches were in April, after BUILT's strongest season "
              "(Jan–Mar, with more promotions), which the method cannot fully separate from the launch."))
    B.append(("h2", "Competitor items flagged by Mo's pair model (from the Sept version, provisional)"))
    B.append(("table", ["BUILT item", "Same-flavor competitor items checked", "Flagged as losing sales"], [
        ["Peanut Butter Cup 4pk", "48", "6"], ["Coconut 4pk", "13", "11"], ["Cookie Dough 4pk", "4", "2"],
        ["Cookies N Cream 4pk", "0", "—"], ["Brownie Batter 4pk", "1", "1"]],
        "A model signal for each pair of items, low confidence and still being re-checked on Meijer's own stores. It "
        "answers 'which competitor items moved', not 'how many packages'. Read it next to the table above, not "
        "instead of it."))

    # 4 2026 launches
    B.append(("h1", "4 — 2026 launches at Meijer"))
    B.append(("meta", "Meijer stores · since each item's first week through Sept 6, 2026"))
    B.append(("table", ["Item", "UPC", "First sold at Meijer", "Stores selling (avg)", "% of Meijer stores",
                        "Base units per week", "Per store selling per week", "Avg price paid per bar",
                        "Regular price per bar", "Weeks"], item_table(d.m, AUG, since=pd.Timestamp("2026-08-16")),
              "Three to four weeks of sales; still ramping into stores. Too early to measure cannibalization; the "
              "first full read needs about 15 weeks after launch (SPINS data through early December 2026)."))

    # 5 singles
    B.append(("h1", "5 — Singles (1-count) at Meijer"))
    B.append(("meta", "Meijer stores · Oct 2023 – Sept 6, 2026"))
    srows = []
    for u, nm in SINGLES.items():
        g = d.m[(d.m.upc == u) & (d.m.base_units > 0)].sort_values("__time")
        mo = g.set_index("__time").resample("MS").stores_selling.mean()
        l13 = g[g.__time >= L13_START]
        srows.append([nm, u, g.__time.min().strftime("%b %Y"), f"{mo.max():.0f} ({mo.idxmax().strftime('%b %Y')})",
                      g.__time.max().strftime("%b %d, %Y"), fmt(l13.base_units.sum()),
                      fmt(l13.stores_selling.mean() if len(l13) else 0, 0)])
    B.append(("table", ["Item", "UPC", "First sold", "Peak stores selling (month)", "Last week with sales",
                        "Base units, last 13 weeks", "Stores selling, last 13 weeks"], srows,
              "Meijer carried two singles in about 15–20 of its stores from Oct 2023 to Apr 2024, and in one or two "
              "stores since. The Sept version showed six singles at 21–31% distribution; that came from the wider "
              "Meijer trading area (all stores near Meijer), not Meijer's own stores."))
    B.append(("h2", "4-count vs 1-count cannibalization"))
    B.append(("p", "Not measurable yet. Meijer has no singles to compare against, and across all other retailers too "
                   "few launches had both pack sizes on the shelf to give a reliable answer. The one clean case "
                   "(a 4-pack launch at Publix in July 2024) drew a little from both pack sizes."))
    B.append(("callout", "Check lane: a singles test in a defined set of Meijer stores, with a matched set of stores "
                         "without it, would measure directly whether singles add to BUILT's sales at Meijer or draw "
                         "from the 4-pack set."))

    # 6 Meijer vs other retailers
    B.append(("h1", "6 — Meijer vs other retailers"))
    B.append(("meta", "Each retailer's own stores · BUILT launches since Apr 2023 with 13 weeks before and at least "
                      "8 weeks after · per-store measure (store expansions are not counted)"))
    B.append(("img", charts["channels"], "BUILT launches at Food-channel retailers over time. Each dot is one launch; "
                                         "the shaded band is the middle half of launches; red diamonds are Meijer."))
    n_food = int(food_x.size)
    B.append(("table", ["Retailer / channel", "Launches measured", "Share of new items' sales taken from existing BUILT items",
                        "Reading"], [
        ["Meijer (Food)", "2", f"{mj.rate_v_all.min():.2f}–{mj.rate_v_all.max():.2f}", "Within the normal Food range"],
        ["Other Food-channel retailers", str(n_food), f"middle launch {f_med:.2f}; middle half {f_q1:.2f}–{f_q3:.2f}",
         "Single launches vary widely; a launch is only measurable when it is big enough to stand out"],
        ["Mass (Target, Walmart)", "—", "Not measurable",
         "Launches came in large sets during store expansions"],
        ["Drug, Convenience, Club", "—", "Not shown", "Too few clean launches, or singles-only shelves"]],
        "Target and Walmart are Mass, not Food. Every measured launch is listed in the appendix."))

    # 7 competitive position
    B.append(("h1", "7 — Competitive position at Meijer"))
    B.append(("meta", f"Meijer stores · {PERIOD} · all nutrition and protein bars"))
    l = d.m[(d.m.__time >= L13_START) & (d.m.__time <= END)].copy()
    l["brand"] = np.where(l.source_brand.str.startswith("BUILT"), "BUILT", l.source_brand)
    l["bars"] = l.units * l.source_pack_count
    br = l.groupby("brand").agg(u=("units", "sum"), dol=("dollars", "sum"), bars=("bars", "sum"))
    br["items"] = l[l.units > 0].groupby("brand").upc.nunique()
    br["share"] = 100 * br.u / br.u.sum()
    br["ppb"] = br.dol / br.bars
    br = br.sort_values("u", ascending=False)
    br["rank"] = range(1, len(br) + 1)
    top = br.head(15)
    if "BUILT" not in top.index:
        top = pd.concat([top, br.loc[["BUILT"]]])
    rows = [[str(int(r["rank"])), b.title() if b != "BUILT" else "BUILT", fmt(r.u), fmt(r.share, 1, pct=True),
             fmt(r.ppb, money=True), fmt(r["items"])] for b, r in top.iterrows()]
    B.append(("table", ["Rank", "Brand", "Units (13 weeks)", "Unit share", "Avg price paid per bar", "Items selling"], rows,
              f"BUILT ranks #{int(br.loc['BUILT', 'rank'])} of {len(br)} brands by units at Meijer stores. Units are "
              f"packages of any size; price per bar = dollars ÷ bars. Brand names as SPINS reports them."))

    # 8 price
    B.append(("h1", "8 — Price sensitivity"))
    B.append(("meta", "Meijer stores and other Food retailers · weekly price paid vs units per store, Sept 2024 – Sept 2026 · "
                      "each item compared with itself over time, with week-to-week category swings removed"))
    B.append(("p", "How to read it: the number shows how strongly units per store move when the price paid moves. "
                   "Most price changes here are promotions, which often come with displays and ads, so these numbers "
                   "describe the response to a deal, not to a permanent shelf-price change. The method makes every "
                   "brand look somewhat more responsive than it is, the same way for each, so compare brands with "
                   "each other rather than reading any one number as exact."))
    B.append(("img", charts["price"], "Protein-bar brands at Meijer (at least 15 g protein per bar and 20,000 units a "
                                      "year). BUILT in red; BUILT's range is narrower than it should be because "
                                      "three items carry most of its data."))
    B.append(("table", ["Pack size (BUILT, other Food retailers)", "Response to price", "Range when any one retailer is left out"], [
        ["4-packs", sg(packs.loc['4-count'].estimate), "−2.1 to −2.9"],
        ["Singles", sg(packs.loc['1-count'].estimate), "−0.8 to −1.2"]],
        "Singles barely sell at Meijer, so this compares pack sizes at Food retailers that sell both "
        f"({', '.join(sorted(geo_names(d.summary['peer_food_retailers_both_packs'])))}). "
        "4-packs respond to deals much more than singles, which are bought on impulse."))
    prow = []
    for g, r in pos.sort_values("base_price_per_bar", ascending=False).iterrows():
        prow.append([g.title() if g != "BUILT" else "BUILT", fmt(r.base_price_per_bar, money=True), f"{r.index_vs_built:.0f}",
                     sg(price.loc[g].estimate) if g in price.index else "—"])
    B.append(("table", ["Brand", "Regular price per bar", "Price index (BUILT = 100)", "Response to price"], prow,
              f"Regular (non-promoted) price per bar, {PERIOD}, sales-weighted. The Sept version's −0.49 came from the "
              f"Meijer trading area and a different method, so the two numbers are not comparable."))

    # 9 recommendations
    B.append(("h1", "9 — Assortment recommendations (draft for discussion)"))
    B.append(("bullets", [
        "Keep all five main 4-packs. The newest two added mostly new sales; the older three each gave up about "
        f"{gaps.min():.0f}–{gaps.max():.0f}% of their expected sales in the first three months, and BUILT's total at "
        "Meijer still grew.",
        "Give Rocky Road, Orange Cream Pop and Mint Chip time before judging them, and re-run this read when SPINS covers "
        "early December 2026. With eight 4-packs on shelf, expect sales per item to keep easing while the BUILT total "
        "grows; the question is whether the total grows faster than the overlap.",
        "Singles: propose a check-lane test in a defined set of Meijer stores, with a matched set of stores without "
        "it, so the effect on the 4-pack set can be measured rather than assumed.",
        "Promotions: BUILT's response to deals at Meijer is strong compared with the protein-bar set, so promotions "
        "are an effective volume lever. Regular price sits at the top of the set with Barebells and Quest.",
    ]))

    # appendix + sources
    B.append(("h1", "Appendix — every measured launch"))
    oks = ok.sort_values(["channel", "anchor"])
    oks = oks[oks.channel == "Food"]
    rows = [[r.retail_account.title(), r.anchor.strftime("%b %Y"), str(int(r.n_new)), r.launch_type,
             fmt(r.new_weekly), sg(r.rate_v_all, 2)] for _, r in oks.iterrows()]
    B.append(("table", ["Retailer (Food channel)", "Launch", "New items", "Pack sizes", "New items' base units per week",
                        "Share taken from existing BUILT items"], rows,
              "Launches within three weeks of each other at a retailer are counted as one. A launch is measurable when "
              "the new items sold at least 10% as much as the existing items. Values below 0 or above 1 are "
              "possible and mostly reflect noise in single launches (existing items moving for other reasons)."))
    B.append(("h1", "Sources, method and what changed from the September version"))
    B.append(("bullets", [
        "Data: SPINS weekly, Meijer's own stores (SPINS 'Meijer Corp – RMA') and each retailer's own stores for the "
        "comparisons, through Sept 6, 2026. Prepared by Aevah with Mo.",
        "This describes what happened around each launch; it is not proof of cause. Store resets, displays, "
        "promotions and competitor changes can move at the same time. Results are ranges, not exact points.",
        "Corrected from the Sept version: it mixed Meijer's own stores with the wider Meijer trading area (every "
        "store near Meijer). All numbers here use Meijer's own stores. This changes the singles section (Meijer has "
        "almost no singles), the price sensitivity (the earlier −0.49 came from the trading area and a different "
        "method) and the cannibalization rate (the earlier 46.9% was the share of item pairs a model flagged, not a "
        "share of sales). The Sept version's check-lane 'go' and 'fully incremental' singles readings are withdrawn "
        "until a test measures them.",
        "Cannibalization is measured from sales before and after each launch, against the rest of the bar category at "
        "the same retailer. Checked against made-up launch dates with no real launch: at Food retailers those move "
        "existing sales by about 12% by chance, which is why only launches big enough to stand out are counted.",
        "Price sensitivity is estimated from weekly price and unit changes over two years, item by item; most price "
        "changes are promotions. Price and cannibalization are separate analyses and are not combined.",
        "Internal to BUILT and Aevah. Not for distribution outside BUILT.",
    ]))
    return B


# ---------------------------------------------------------------- Word
def shade(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hex_color.lstrip("#"))
    tcPr.append(sh)


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h.lstrip("#"))


def render_docx(B: list[tuple], path: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.6))
    sec.top_margin = sec.bottom_margin = Inches(0.6)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for name, size, color in (("Heading 1", 14, NAVY), ("Heading 2", 11.5, DEEP), ("Title", 24, NAVY)):
        s = doc.styles[name]
        s.font.name, s.font.size, s.font.color.rgb, s.font.bold = "Calibri", Pt(size), rgb(color), True
    foot = sec.footer.paragraphs[0]
    foot.text = f"Meijer Account Brief · {VERSION} · {ISSUED} · Internal to BUILT and Aevah"
    foot.runs[0].font.size, foot.runs[0].font.color.rgb = Pt(8), rgb(MUTED)
    width = sec.page_width - sec.left_margin - sec.right_margin
    first_h1 = True
    for b in B:
        k = b[0]
        if k == "title":
            p = doc.add_paragraph(b[1], style="Title")
        elif k == "subtitle":
            p = doc.add_paragraph()
            r = p.add_run(b[1])
            r.font.size, r.font.color.rgb, r.bold = Pt(12), rgb(RED), True
        elif k == "meta":
            p = doc.add_paragraph()
            r = p.add_run(b[1])
            r.font.size, r.font.color.rgb, r.italic = Pt(8.5), rgb(MUTED), True
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
        elif k == "h1":
            if not first_h1 and b[1].startswith(("Appendix",)):
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            first_h1 = False
            doc.add_heading(b[1], level=1).paragraph_format.keep_with_next = True
        elif k == "h2":
            doc.add_heading(b[1], level=2).paragraph_format.keep_with_next = True
        elif k == "p":
            doc.add_paragraph(b[1]).paragraph_format.keep_with_next = True
        elif k == "bullets":
            for t in b[1]:
                doc.add_paragraph(t, style="List Bullet")
        elif k == "callout":
            t = doc.add_table(rows=1, cols=1)
            c = t.cell(0, 0)
            shade(c, "#FDECEE")
            c.paragraphs[0].add_run(b[1]).font.size = Pt(9.5)
            doc.add_paragraph()
        elif k == "img":
            doc.add_picture(str(b[1]), width=width)
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.paragraphs[-1].paragraph_format.keep_with_next = True
            p = doc.add_paragraph()
            r = p.add_run(b[2])
            r.font.size, r.font.color.rgb, r.italic = Pt(8.5), rgb(MUTED), True
        elif k == "table":
            head, rows, note = b[1], b[2], b[3]
            t = doc.add_table(rows=1 + len(rows), cols=len(head))
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            fs = Pt(8) if len(head) >= 7 else Pt(9)
            for j, h in enumerate(head):
                c = t.cell(0, j)
                c.text = ""
                r = c.paragraphs[0].add_run(h)
                r.bold, r.font.size, r.font.color.rgb = True, fs, rgb("#FFFFFF")
                shade(c, NAVY)
            for row_ in t.rows:
                trPr = row_._tr.get_or_add_trPr()
                cs = OxmlElement("w:cantSplit")
                trPr.append(cs)
            hdr = t.rows[0]._tr.get_or_add_trPr()
            th = OxmlElement("w:tblHeader")
            hdr.append(th)
            for i, row in enumerate(rows, start=1):
                is_built = any(str(v).startswith("BUILT") or str(v).startswith("Meijer") for v in row[:2])
                for j, v in enumerate(row):
                    c = t.cell(i, j)
                    c.text = ""
                    r = c.paragraphs[0].add_run(str(v))
                    r.font.size = fs
                    if is_built:
                        r.bold = True
                        shade(c, "#FDECEE")
                    elif i % 2 == 0:
                        shade(c, "#F5F9FF")
            if note:
                p = doc.add_paragraph()
                r = p.add_run(note)
                r.font.size, r.font.color.rgb, r.italic = Pt(8), rgb(MUTED), True
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
    doc.core_properties.title = "Meijer Account Brief v2"
    doc.core_properties.author = "Aevah"
    doc.save(path)


def pdf_text(pdf_path: Path) -> str:
    """Text of a PDF via macOS PDFKit (tools/pdf_text.swift); used to verify an export."""
    r = subprocess.run(["swift", str(Path(__file__).resolve().parent / "tools" / "pdf_text.swift"), str(pdf_path)],
                       capture_output=True, text=True, timeout=180)
    return r.stdout


def to_pdf(docx_path: Path, pdf_path: Path) -> bool:
    """Microsoft Word exports the PDF. Word is sandboxed, so the file goes through Word's own Documents folder
    (no file-access prompt) under a UNIQUE name: Word reuses an already-open document with the same name, which
    once exported a stale earlier draft (2026-10-13). The PDF is accepted only if its text contains the .docx's
    first and last paragraphs."""
    import shutil
    import time
    from docx import Document
    paras = [p.text.strip() for p in Document(docx_path).paragraphs if p.text.strip()]
    box = Path.home() / "Library/Containers/com.microsoft.Word/Data/Documents"
    tag = f"aevah_{docx_path.stem[:40]}_{int(time.time())}"
    src, dst = box / f"{tag}.docx", box / f"{tag}.pdf"
    shutil.copy(docx_path, src)
    script = f"""with timeout of 170 seconds
    tell application "Microsoft Word"
        set theDoc to open file name (POSIX file "{src}" as string)
        delay 2
        save as theDoc file name (POSIX file "{dst}" as string) file format format PDF
    end tell
    end timeout"""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=200)
    if r.returncode != 0:
        print("Word PDF export:", r.stderr.strip())
    ok = False
    if dst.exists():
        txt = " ".join(pdf_text(dst).split())
        ok = all(" ".join(x.split())[:60] in txt for x in (paras[0], paras[-1]))
        if ok:
            shutil.copy(dst, pdf_path)
        else:
            print("PDF REJECTED: its text does not match", docx_path.name)
    src.unlink(missing_ok=True)
    dst.unlink(missing_ok=True)
    return ok


# ---------------------------------------------------------------- HTML
CSS = f"""
:root {{ --red:{RED}; --navy:{NAVY}; --blue:{BLUE}; --deep:{DEEP}; --muted:{MUTED}; --border:{BORDER};
  --bg:#F5F9FF; --surface:#FFFFFF; --tint:#FDECEE; --zebra:#F5F9FF; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--navy); font:15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system,
  "Segoe UI", Arial, sans-serif; }}
.bar {{ position:sticky; top:0; z-index:5; background:var(--navy); color:#fff; display:flex; flex-wrap:wrap; gap:10px;
  align-items:center; padding:10px 16px; }}
.bar b {{ margin-right:auto; font-weight:600; }}
.bar button {{ background:#fff; color:var(--navy); border:0; border-radius:8px; padding:7px 12px; font:600 13px Inter, Arial,
  sans-serif; cursor:pointer; }}
.bar button.primary {{ background:var(--red); color:#fff; }}
.bar .hint {{ font-size:12px; opacity:.8; width:100%; }}
main {{ max-width:980px; margin:0 auto; padding:24px 16px 64px; background:var(--surface); }}
main[contenteditable=true] {{ outline:none; }}
main[contenteditable=true] :is(p,li,td,th,h1,h2,figcaption,.meta):hover {{ background:#FFF8E1; }}
h1.title {{ font-size:32px; margin:0 0 4px; letter-spacing:-.01em; }}
.subtitle {{ color:var(--red); font-weight:700; font-size:17px; margin:0 0 10px; }}
h1 {{ font-size:21px; margin:34px 0 6px; padding-top:10px; border-top:3px solid var(--red); text-wrap:balance; }}
h2 {{ font-size:16px; color:var(--deep); margin:22px 0 6px; }}
.meta {{ color:var(--muted); font-size:12.5px; font-style:italic; margin:2px 0 10px; }}
p, li {{ max-width:72ch; }}
li {{ margin:4px 0; }}
figure {{ margin:12px 0 16px; }}
figure img {{ width:100%; height:auto; border:1px solid var(--border); border-radius:8px; }}
figcaption {{ color:var(--muted); font-size:12.5px; font-style:italic; margin-top:4px; }}
.tw {{ overflow-x:auto; margin:8px 0 4px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums; }}
th {{ background:var(--navy); color:#fff; text-align:left; font-weight:600; padding:6px 8px; vertical-align:bottom; }}
td {{ border-bottom:1px solid var(--border); padding:5px 8px; vertical-align:top; }}
tr:nth-child(even) td {{ background:var(--zebra); }}
tr.hl td {{ background:var(--tint); font-weight:700; }}
.note {{ color:var(--muted); font-size:12px; font-style:italic; margin:4px 0 14px; }}
.callout {{ background:var(--tint); border-left:4px solid var(--red); padding:10px 14px; border-radius:6px; margin:12px 0; }}
@media (max-width:600px) {{ body {{ font-size:14px; }} h1.title {{ font-size:26px; }} }}
@media print {{
  @page {{ size: letter; margin: 0.55in; }}
  body {{ background:#fff; font-size:10.5pt; }}
  .bar {{ display:none; }}
  main {{ max-width:none; padding:0; }}
  h1 {{ break-after:avoid; }} h2 {{ break-after:avoid; }}
  figure, table, .callout {{ break-inside:avoid; }}
  tr {{ break-inside:avoid; }}
  h1.appendix {{ break-before:page; }}
  main :hover {{ background:none !important; }}
}}
"""

JS = """
const main = document.querySelector('main');
const toggle = document.getElementById('edit');
function setEdit(on){ main.contentEditable = on ? 'true' : 'false';
  toggle.textContent = on ? 'Editing: ON' : 'Editing: OFF'; }
toggle.onclick = () => setEdit(main.contentEditable !== 'true');
document.getElementById('save').onclick = () => {
  const wasOn = main.contentEditable === 'true'; setEdit(false);
  const src = '<!doctype html>\\n' + document.documentElement.outerHTML; setEdit(wasOn);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([src], {type:'text/html'}));
  a.download = 'Meijer_BUILT_Assortment_Brief_v2_edited.html'; document.body.appendChild(a); a.click(); a.remove();
};
document.getElementById('print').onclick = () => { setEdit(false); window.print(); };
document.getElementById('addrow').onclick = () => {
  const sel = window.getSelection(); if (!sel.rangeCount) return;
  let n = sel.anchorNode; while (n && n.nodeName !== 'TR') n = n.parentNode; if (!n) return;
  const c = n.cloneNode(true); c.querySelectorAll('td').forEach(td => td.textContent = ''); n.after(c);
};
setEdit(true);
"""


def render_html(B: list[tuple], path: Path) -> None:
    e = html.escape
    out = []
    for b in B:
        k = b[0]
        if k == "title":
            out.append(f'<h1 class="title">{e(b[1])}</h1>')
        elif k == "subtitle":
            out.append(f'<p class="subtitle">{e(b[1])}</p>')
        elif k == "meta":
            out.append(f'<p class="meta">{e(b[1])}</p>')
        elif k == "h1":
            cls = ' class="appendix"' if b[1].startswith("Appendix") else ""
            out.append(f"<h1{cls}>{e(b[1])}</h1>")
        elif k == "h2":
            out.append(f"<h2>{e(b[1])}</h2>")
        elif k == "p":
            out.append(f"<p>{e(b[1])}</p>")
        elif k == "bullets":
            out.append("<ul>" + "".join(f"<li>{e(t)}</li>" for t in b[1]) + "</ul>")
        elif k == "callout":
            out.append(f'<div class="callout">{e(b[1])}</div>')
        elif k == "img":
            data = base64.b64encode(Path(b[1]).read_bytes()).decode()
            out.append(f'<figure><img alt="{e(b[2])}" src="data:image/png;base64,{data}">'
                       f"<figcaption>{e(b[2])}</figcaption></figure>")
        elif k == "table":
            head, rows, note = b[1], b[2], b[3]
            h = "".join(f"<th>{e(x)}</th>" for x in head)
            body = []
            for r in rows:
                hl = ' class="hl"' if any(str(v).startswith(("BUILT", "Meijer")) for v in r[:2]) else ""
                body.append(f"<tr{hl}>" + "".join(f"<td>{e(str(v))}</td>" for v in r) + "</tr>")
            out.append(f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
            if note:
                out.append(f'<p class="note">{e(note)}</p>')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meijer Account Brief v2</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet"
 href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<style>{CSS}</style></head><body>
<div class="bar"><b>Meijer Account Brief · v2</b>
<button id="edit">Editing: ON</button><button id="addrow">Add table row below cursor</button>
<button id="save">Save edited copy</button><button id="print" class="primary">Print / Save as PDF</button>
<span class="hint">Click any text or table cell to change it. 'Save edited copy' downloads your version as a new file;
'Print / Save as PDF' opens your browser's print window (choose 'Save as PDF').</span></div>
<main>{"".join(out)}</main><script>{JS}</script></body></html>"""
    path.write_text(page, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    (OUT / "charts").mkdir(parents=True, exist_ok=True)
    d = load()
    charts = {"own": chart_own(d), "newest": chart_newest(d), "channels": chart_channels(d), "price": chart_price(d)}
    B = build_blocks(d, charts)
    docx_p, pdf_p, html_p = OUT / f"{STEM}.docx", OUT / f"{STEM}.pdf", OUT / f"{STEM}.html"
    render_docx(B, docx_p)
    render_html(B, html_p)
    print("wrote", docx_p, html_p)
    if not a.no_pdf:
        print("pdf", "ok" if to_pdf(docx_p, pdf_p) else "FAILED", pdf_p)


if __name__ == "__main__":
    main()
