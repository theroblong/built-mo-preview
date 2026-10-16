"""MO_158 - The complete Meijer brief (v3): the v2 account brief plus the singles-at-checkout section (formerly a
separate add-on) and Meijer's own 2023-24 singles period (MO_157), as one editable document: HTML with editing,
add-table-row, save-edited-copy and print/save-as-PDF; plus Word and PDF.
# protocol: not-a-forecast-arm  (document build; numbers come from MO_142, MO_143 and MO_157)

WHERE THIS CAME FROM: Jason (2026-10-16): "if that's just an addendum, let's combine it into a more complete, total
Meijer brief that allows editing, PDF export, etc. as Brian had requested", after the double-check of the add-on's
first claim (scoped: DECA excluded as not comparable, Jason's decision; Meijer's own singles period stated).
The Oct 13 brief and add-on stay as they were (their builders are imported, not changed).

Output: docs/briefs/meijer_v3/Meijer_BUILT_Brief_v3_2026-10-16.{html,docx,pdf} (+ charts/)
Usage: python3 MO_158_build_full_brief.py [--no-pdf]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import MO_142_build_brief as BB
import MO_143_build_addendum as AD

STEM = "Meijer_BUILT_Brief_v3_2026-10-16"
OUT = Path("../docs/briefs/meijer_v3")
MO157 = Path("../outputs/mo157_meijer_own_singles.json")
L13 = pd.Timestamp("2026-06-14")

# Add-table-row fix: clicking the button used to move the cursor out of the table, so it never found the row.
# Remember the last table row the cursor was in, and keep the button from taking the cursor.
JS = BB.JS.replace(
    """document.getElementById('addrow').onclick = () => {
  const sel = window.getSelection(); if (!sel.rangeCount) return;
  let n = sel.anchorNode; while (n && n.nodeName !== 'TR') n = n.parentNode; if (!n) return;
  const c = n.cloneNode(true); c.querySelectorAll('td').forEach(td => td.textContent = ''); n.after(c);
};""",
    """let lastRow = null;
document.addEventListener('selectionchange', () => {
  const s = window.getSelection(); if (!s.rangeCount) return;
  let n = s.anchorNode; while (n && n.nodeName !== 'TR') n = n.parentNode;
  if (n && main.contains(n)) lastRow = n;
});
const addBtn = document.getElementById('addrow');
addBtn.onmousedown = e => e.preventDefault();              // keep the cursor where it is
addBtn.onclick = () => {
  if (!lastRow) { addBtn.textContent = 'Click a table cell first'; setTimeout(() => addBtn.textContent = 'Add table row below cursor', 1800); return; }
  const inHead = lastRow.parentNode.nodeName === 'THEAD';
  const src = inHead ? (lastRow.closest('table').querySelector('tbody tr') || lastRow) : lastRow;
  const c = src.cloneNode(true);
  c.querySelectorAll('td,th').forEach(td => td.textContent = '');
  c.classList.remove('hl');
  if (inHead) lastRow.closest('table').querySelector('tbody').prepend(c); else lastRow.after(c);
  const first = c.querySelector('td,th'); if (first) { const r = document.createRange(); r.setStart(first, 0); r.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); }
  lastRow = c;
};""")
assert JS != BB.JS, "add-row script not found in MO_142 JS"


def singles_facts(b: pd.DataFrame) -> dict:
    """Numbers for the corrected first bullet (same cache and definitions as the add-on)."""
    l13 = b[b.__time >= L13]
    food = b[b.channel == "Food"]
    mj = l13[l13.retail_account == "MEIJER"]
    mj1 = b[(b.retail_account == "MEIJER") & (b.source_pack_count == 1) & (b.base_units > 0)]
    w = mj1.groupby("__time").stores_selling.max()
    busy = w[w >= 10]
    return {
        "n_food": int(food.retail_account.nunique()),
        "mj_single_units": float(mj[mj.source_pack_count == 1].base_units.sum()),
        "mj_4pk_units": float(mj[mj.source_pack_count == 4].base_units.sum()),
        "mj_single_stores_l13": int(mj[(mj.source_pack_count == 1) & (mj.base_units > 0)].stores_selling.max() or 0),
        "mj_single_items_l13": int(mj[(mj.source_pack_count == 1) & (mj.base_units > 0)].upc.nunique()),
        "start": busy.index.min(), "end": busy.index.max(), "peak": int(w.max()),
        "typical": int(round(busy.median())),          # stores selling in a typical week of the period
        "stores": int(b[b.retail_account == "MEIJER"].groupby("__time").store_count.max().median()),
    }


def corrected_bullet(f: dict) -> str:
    """Skeptic-verified wording (2026-10-16, SURVIVES WITH CAVEATS); numbers recomputed from the same cache."""
    return ("Of the 16 grocery accounts in BUILT's SPINS data, Meijer is the only one that sells BUILT 4-packs with "
            "almost no singles today: about 8 single units over the last 13 weeks (one item, in one store), against "
            "about 68,500 4-packs. Meijer started selling BUILT in October 2023 with two 4-packs and singles of the "
            "same two flavors; the singles were in about 15–20 of its roughly 270 stores until late April 2024, then "
            "dropped within a few weeks to one to three stores (section 10.1). Every other grocer in the data that "
            "sells 4-packs had singles first (data from January 2023). Among the grocery and mass retailers in the "
            "data (military commissaries aside), the only ones that later expanded singles to 10% or more of their "
            "stores after 4-packs were already on the shelf are Walmart and Target; like Meijer, both sell groceries "
            "alongside general merchandise.")


def own_singles_blocks(f: dict) -> list[tuple]:
    """Meijer's own singles (MO_157), skeptic-verified wording (2026-10-16)."""
    r = json.loads(MO157.read_text())
    rows = [[x["description"].replace("Built Puff ", "").replace(" Protein Bar", ""), x["upc"], f"{x['base_units']:,.0f}",
             str(x["weeks"]), f"{x['per_store_wk']:.1f}"] for x in r["Q2"]]
    return [
        ("h2", "10.1 — Meijer's own singles, 2023–24"),
        ("p", "Meijer has carried BUILT singles before: two items, Brownie Batter and Coconut (1.41 oz), the same "
              "flavors as its 4-packs, from October 2023 to June 2024. They sold about 2.6 units per item per store "
              "selling per week at regular price. In the same months a typical grocer sold about 4.0 and a typical "
              "convenience chain about 1.6; Walmart sold about 2.6, and Target had no singles yet. So Meijer's singles "
              "sold below the typical grocer then."),
        ("table", ["Single", "UPC", "Base units, Oct 2023 – Jun 2024", "Weeks sold", "Per store selling per week"], rows,
         "SPINS, Meijer's own stores (RMA). Per store selling per week = base units / stores selling (regular-price "
         "sales), the same measure as the comparisons in this section."),
        ("p", "At regular price, singles cost about 15% more per bar than Meijer's 4-packs (about 20% for Brownie "
              "Batter, 9% for Coconut); at the prices shoppers actually paid, including promotions, the gap was about 5%."),
        ("p", "Did they take sales from 4-packs? This cannot be measured from SPINS. Singles were about 2% of Meijer's "
              "4-pack sales counted in bars, or about 8% counted in packs (the most possible if every single bought "
              "replaced a whole 4-pack). Each single was in at most 25 stores, and SPINS does not show which stores "
              "carried them. Meijer's 4-pack sales were still building after launch (about 1,500 rising to about 4,000 "
              "bars a week) and moved about 8% in a typical week, so any effect on 4-packs cannot be separated out in "
              "Meijer's account totals. The store test in this section is the way to measure it."),
    ]


FIXES = [  # skeptic 2026-10-16: Target is mostly not supercenters; the add-on is now a section of the brief
    ("and like Meijer they are supercenters", "and like Meijer, they sell groceries alongside general merchandise"),
    ("anywhere in this add-on", "anywhere in this section"),
]


def _fix(x):
    if isinstance(x, str):
        for a, b in FIXES:
            x = x.replace(a, b)
        return x
    if isinstance(x, list):
        return [_fix(v) for v in x]
    return x


def singles_section(E: list[tuple], f: dict) -> list[tuple]:
    """The add-on's blocks as section 10 of the brief: header blocks dropped, corrected first bullet, sub-headings."""
    out: list[tuple] = [("h1", "10 — Singles at checkout: what other retailers show, and how to test it at Meijer")]
    first_bullets = True
    for blk in E:
        blk = tuple(_fix(v) for v in blk)
        k = blk[0]
        if k in ("title", "subtitle", "meta"):
            continue
        if k == "h1":
            name = blk[1].split(" — ", 1)[-1]
            out.append(("h2", "Singles: " + name.lower() if name in ("Summary", "Sources and caveats") else name))
            if name == "Summary":
                pass
            continue
        if k == "bullets" and first_bullets:
            first_bullets = False
            out.append(("bullets", [corrected_bullet(f)] + list(blk[1][1:])))
            out.extend(own_singles_blocks(f))
            continue
        out.append(blk)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    BB.OUT = OUT
    (OUT / "charts").mkdir(parents=True, exist_ok=True)
    BB.VERSION, BB.ISSUED = "v3", "October 16, 2026"
    d = BB.load()
    charts = {"own": BB.chart_own(d), "newest": BB.chart_newest(d), "channels": BB.chart_channels(d),
              "price": BB.chart_price(d)}
    B = BB.build_blocks(d, charts)
    B = [("meta", "Version 3 · issued October 16, 2026 · prepared by Aevah (Mo) for BUILT · combines the Oct 13 brief "
                  "and its singles add-on") if (blk[0] == "meta" and blk[1].startswith("Version 2")) else blk for blk in B]
    b = AD.load()
    E = AD.build(b, AD.chart_programs(pd.read_csv(AD.SRC / "q2_singles_ramp.csv")))
    S = singles_section(E, singles_facts(b))
    i = next(i for i, blk in enumerate(B) if blk[0] == "h1" and blk[1].startswith("Appendix"))
    B = B[:i] + S + B[i:]
    docx_p, pdf_p, html_p = OUT / f"{STEM}.docx", OUT / f"{STEM}.pdf", OUT / f"{STEM}.html"
    BB.render_docx(B, docx_p)
    from docx import Document
    dd = Document(docx_p)
    dd.core_properties.title = "Meijer Account Brief v3"
    dd.save(docx_p)
    BB.JS = JS
    BB.render_html(B, html_p)
    html_p.write_text(html_p.read_text(encoding="utf-8")
                      .replace("Meijer Account Brief v2</title>", "Meijer Account Brief v3</title>")
                      .replace("Meijer Account Brief · v2</b>", "Meijer Account Brief · v3</b>")
                      .replace("Meijer_BUILT_Assortment_Brief_v2_edited.html", "Meijer_BUILT_Brief_v3_edited.html"),
                      encoding="utf-8")
    print("wrote", docx_p, html_p)
    if not a.no_pdf:
        print("pdf", "ok" if BB.to_pdf(docx_p, pdf_p) else "FAILED", pdf_p)


if __name__ == "__main__":
    main()
