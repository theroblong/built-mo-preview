"""MO_59f — Year-over-year seasonality validation view (HTML).

The growth charts in Mo cannot validate seasonality: a series growing 30x over three years
shows its growth curve, and a +20% March effect is invisible against that. This builds the
view that CAN show it — week-of-year on a common x-axis with one panel per year, so a
repeating seasonal shape is visible directly rather than taken on faith from an STL
decomposition.

Covers the three portfolio measures side by side as well, because they disagree and the
disagreement is the point:
  * STL volume-weighted  — what MO_27 multiplies the forecast by (trend REMOVED)
  * raw monthly          — the client-chart number (trend INCLUDED)
  * YoY-overlay median   — each series-YEAR normalised to its own mean, then medianed.
                           ⚠️ NOT an independent seasonality measure: normalising within a year
                           embeds the within-year growth ramp, so a growing series reads below
                           its annual mean in January and above it by autumn regardless of
                           season. Included BECAUSE the contrast is instructive — it is what
                           "seasonality" looks like when trend is left in.

Sampling: random series from RMA retailers only (geography_level == 'RMA'), requiring enough
history to show at least two full years, weighted toward populated retailers so the panels
are not all near-zero.

Output: mockups/mo59f_seasonality_yoy.html  (self-contained, no external data)

Run:  python MO_59f_seasonality_yoy_view.py [--n-series 12] [--seed 7]
"""
from __future__ import annotations
import argparse, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from mo_panel import (drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts, GROUP_COLS)

OUT = Path(__file__).parent.parent / "mockups" / "mo59f_seasonality_yoy.html"
YEAR_COLORS = {"2023": 0, "2024": 1, "2025": 2, "2026": 3}


def load():
    df = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce")
    df = df.dropna(subset=["base_units"])
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_zero_volume_geographies, apply_rma_priority):
        df = fn(df, verbose=False)
    return df[df["geography_level"] == "RMA"].copy()


def main(n_series: int, seed: int):
    df = load()
    df["year"] = df["__time"].dt.year.astype(str)
    df["woy"] = df["__time"].dt.isocalendar().week.astype(int)
    print(f"RMA panel: {len(df):,} rows | {df.groupby(GROUP_COLS).ngroups} series | "
          f"{df.retail_account.nunique()} retailers")

    # eligible: >=2 distinct years with >=30 weeks each, and real volume
    stats = (df.groupby(GROUP_COLS + ["year"])
               .agg(wks=("base_units", "size"), units=("base_units", "sum")).reset_index())
    good = stats[(stats.wks >= 30) & (stats.units > 0)]
    cnt = good.groupby(GROUP_COLS).agg(yrs=("year", "nunique"), tot=("units", "sum")).reset_index()
    elig = cnt[cnt.yrs >= 2].sort_values("tot", ascending=False)
    print(f"eligible series (>=2 yrs x >=30 wks): {len(elig)}")

    # sample across DIFFERENT retailers so one account cannot dominate
    rng = np.random.default_rng(seed)
    picked, used = [], {}
    for _, r in elig.iterrows():
        a = r["retail_account"]
        if used.get(a, 0) >= 2:        # at most 2 per retailer
            continue
        picked.append(tuple(r[c] for c in GROUP_COLS)); used[a] = used.get(a, 0) + 1
        if len(picked) >= n_series * 3: break
    idx = rng.choice(len(picked), size=min(n_series, len(picked)), replace=False)
    picked = [picked[i] for i in sorted(idx)]
    print(f"sampled {len(picked)} series across {len({p[2] for p in picked})} retailers")

    panels = []
    for upc, chan, acct, geo in picked:
        s = df[(df.upc == upc) & (df.channel_outlet == chan) &
               (df.retail_account == acct) & (df.geography_raw == geo)]
        desc = str(s["description"].iloc[0])
        years = {}
        for y, gy in s.groupby("year"):
            if len(gy) < 30: continue
            ser = gy.groupby("woy")["base_units"].sum().reindex(range(1, 54)).astype(float)
            years[y] = {"raw": [None if pd.isna(v) else round(float(v), 1) for v in ser],
                        "mean": float(np.nanmean(ser.values)) or 1.0}
        if len(years) < 2: continue
        for y in years:
            m = years[y]["mean"] or 1.0
            years[y]["norm"] = [None if v is None else round(v / m, 4) for v in years[y]["raw"]]
        panels.append({"upc": upc, "desc": desc, "acct": acct, "geo": geo,
                       "chan": chan, "years": years})
    print(f"panels built: {len(panels)}")

    # ── three portfolio measures ───────────────────────────────────────────────
    stl = pd.read_csv("outputs/mo59_seasonal_index.csv")
    stl_s = pd.Series(stl.seasonal_index.values, index=stl.week_of_year.astype(int).values).reindex(range(1, 53))
    # raw monthly, expanded to weeks for a like-for-like x-axis
    monthly = []
    for k, g in df.groupby(GROUP_COLS):
        if len(g) < 52: continue
        mm = g.groupby(g["__time"].dt.month)["base_units"].mean().reindex(range(1, 13))
        if mm.mean() and mm.mean() > 0: monthly.append(mm / mm.mean() - 1.0)
    raw_m = pd.concat(monthly, axis=1).mean(axis=1) if monthly else pd.Series([0]*12, index=range(1,13))
    raw_m -= raw_m.mean()
    wk_month = {w: (pd.Timestamp("2026-01-01") + pd.Timedelta(days=(w-1)*7)).month for w in range(1, 53)}
    raw_w = pd.Series({w: raw_m[wk_month[w]] for w in range(1, 53)})
    # YoY-overlay median: each series-year normalised to its own mean, medianed
    ov = []
    for (upc, chan, acct, geo), g in df.groupby(GROUP_COLS):
        for y, gy in g.groupby("year"):
            if len(gy) < 40: continue
            ser = gy.groupby("woy")["base_units"].sum().reindex(range(1, 53)).astype(float)
            m = np.nanmean(ser.values)
            if m and m > 0: ov.append(ser / m - 1.0)
    yoy = pd.concat(ov, axis=1).median(axis=1) if ov else pd.Series([0]*52, index=range(1,53))
    yoy -= yoy.mean()
    print(f"portfolio measures: STL, raw monthly ({len(monthly)} series), "
          f"YoY overlay ({len(ov)} series-years)")

    def ser(s): return [None if pd.isna(v) else round(float(v), 4) for v in s.reindex(range(1, 53))]
    payload = {"panels": panels,
               "portfolio": {"stl": ser(stl_s), "raw": ser(raw_w), "yoy": ser(yoy)},
               "meta": {"n_panels": len(panels), "n_raw": len(monthly), "n_yoy": len(ov),
                        "generated": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")}}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(HTML.replace("__DATA__", json.dumps(payload)))
    print(f"\n  → {OUT}")


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Seasonality Check</title>
<style>
:root{--surface-1:#fcfcfb;--surface-2:#f4f4f1;--text-primary:#1a1a19;--text-secondary:#5c5b55;
--text-muted:#8a8980;--grid:#e4e4df;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--surface-1:#1a1a19;
--surface-2:#242423;--text-primary:#fff;--text-secondary:#c3c2b7;--text-muted:#8a8980;
--grid:#35352f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;}}
:root[data-theme="dark"]{--surface-1:#1a1a19;--surface-2:#242423;--text-primary:#fff;
--text-secondary:#c3c2b7;--text-muted:#8a8980;--grid:#35352f;--s1:#3987e5;--s2:#d95926;
--s3:#199e70;--s4:#c98500;}
*{box-sizing:border-box}body{margin:0;background:var(--surface-1);color:var(--text-primary);
font:14px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;padding:0 16px 64px}
.wrap{max-width:1180px;margin:0 auto}h1{font-size:22px;margin:28px 0 6px}
h2{font-size:16px;margin:34px 0 4px;padding-top:18px;border-top:1px solid var(--grid)}
p.sub{color:var(--text-secondary);margin:0 0 18px;max-width:72ch}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 14px;font-size:12px}
.legend span{display:flex;align-items:center;gap:6px;color:var(--text-secondary)}
.sw{width:11px;height:11px;border-radius:2px;flex:none}
.card{background:var(--surface-2);border:1px solid var(--grid);border-radius:10px;
padding:14px 16px 10px;margin:14px 0}
.card h3{font-size:13px;margin:0 0 2px;font-weight:600}
.card .meta{font-size:11.5px;color:var(--text-muted);margin:0 0 10px;font-family:ui-monospace,monospace}
.row{display:grid;gap:10px}
svg{display:block;width:100%;height:auto;overflow:visible}
.gl{stroke:var(--grid);stroke-width:1}
.ax{fill:var(--text-muted);font-size:10px;font-family:ui-monospace,monospace}
.ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dl{font-size:10px;font-family:ui-monospace,monospace;font-weight:600}
.zero{stroke:var(--text-muted);stroke-width:1;stroke-dasharray:3 3;opacity:.55}
table{border-collapse:collapse;width:100%;font-size:12px;margin-top:10px}
th,td{text-align:right;padding:4px 7px;border-bottom:1px solid var(--grid)}
th:first-child,td:first-child{text-align:left}th{color:var(--text-secondary);font-weight:600}
details{margin-top:10px}summary{cursor:pointer;color:var(--text-secondary);font-size:12px}
.note{background:var(--surface-2);border-left:3px solid var(--s4);padding:10px 14px;
border-radius:0 6px 6px 0;margin:14px 0;font-size:13px;color:var(--text-secondary)}
.tt{position:fixed;pointer-events:none;background:var(--surface-1);border:1px solid var(--grid);
border-radius:6px;padding:6px 9px;font-size:11.5px;font-family:ui-monospace,monospace;
box-shadow:0 4px 14px rgba(0,0,0,.18);opacity:0;transition:opacity .08s;z-index:9}
</style></head><body><div class="wrap">
<h1>Seasonality check — year over year</h1>
<p class="sub">Growth charts cannot validate seasonality: a series growing 30&times; over three
years shows its growth curve, and a 20% March effect is invisible against it. Here every year is
plotted on the same week-of-year axis and <strong>normalised to its own annual mean</strong>, so
level is removed and only shape remains. If seasonality is real, the years rise and fall together
regardless of how much bigger each one is.</p>
<div id="app"></div>
<div class="tt" id="tt"></div></div>
<script>
const D=__DATA__;const C=['var(--s1)','var(--s2)','var(--s3)','var(--s4)'];
const YC={'2023':0,'2024':1,'2025':2,'2026':3};
const tt=document.getElementById('tt');
function path(v,x,y){let d='',pen=false;v.forEach((p,i)=>{if(p==null){pen=false;return;}
const X=x(i+1),Y=y(p);d+=(pen?'L':'M')+X.toFixed(1)+' '+Y.toFixed(1);pen=true;});return d;}
function chart(series,{h=150,dom=null,fmt=v=>v.toFixed(2),zero=false,labels=true}={}){
const W=1100,PL=46,PR=58,PT=10,PB=22;
const all=series.flatMap(s=>s.v).filter(v=>v!=null);
if(!all.length)return '';
let lo=dom?dom[0]:Math.min(...all),hi=dom?dom[1]:Math.max(...all);
if(lo===hi){lo-=1;hi+=1;}const pad=(hi-lo)*.08;lo-=pad;hi+=pad;
const x=w=>PL+(w-1)/51*(W-PL-PR), y=v=>PT+(1-(v-lo)/(hi-lo))*(h-PT-PB);
let g='';for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4,Y=y(v);
g+=`<line class="gl" x1="${PL}" y1="${Y.toFixed(1)}" x2="${W-PR}" y2="${Y.toFixed(1)}"/>`
+`<text class="ax" x="${PL-7}" y="${(Y+3).toFixed(1)}" text-anchor="end">${fmt(v)}</text>`;}
if(zero&&lo<0&&hi>0)g+=`<line class="zero" x1="${PL}" y1="${y(0).toFixed(1)}" x2="${W-PR}" y2="${y(0).toFixed(1)}"/>`;
[1,10,20,30,40,52].forEach(w=>{const X=x(w);
g+=`<text class="ax" x="${X.toFixed(1)}" y="${h-6}" text-anchor="middle">w${w}</text>`;});
let p='';series.forEach(s=>{p+=`<path class="ln" d="${path(s.v,x,y)}" stroke="${s.c}"/>`;
if(labels){let li=-1;for(let i=s.v.length-1;i>=0;i--)if(s.v[i]!=null){li=i;break;}
if(li>=0)p+=`<text class="dl" x="${(x(li+1)+6).toFixed(1)}" y="${(y(s.v[li])+3).toFixed(1)}" fill="${s.c}">${s.n}</text>`;}});
const hv=`<rect x="${PL}" y="${PT}" width="${W-PL-PR}" height="${h-PT-PB}" fill="transparent"
 onmousemove="hover(event,${W},${PL},${PR},this)" onmouseleave="tt.style.opacity=0"
 data-s='${JSON.stringify(series.map(s=>({n:s.n,v:s.v})))}'/>`;
return `<svg viewBox="0 0 ${W} ${h}">${g}${p}${hv}</svg>`;}
function hover(e,W,PL,PR,el){const r=el.getBoundingClientRect();
const w=Math.max(1,Math.min(52,Math.round((e.clientX-r.left)/r.width*51)+1));
const s=JSON.parse(el.dataset.s);
let html=`<b>week ${w}</b>`;s.forEach(x=>{const v=x.v[w-1];
html+=`<br>${x.n}: ${v==null?'—':(+v).toFixed(2)}`;});
tt.innerHTML=html;tt.style.opacity=1;
tt.style.left=Math.min(window.innerWidth-170,e.clientX+14)+'px';tt.style.top=(e.clientY-10)+'px';}
window.hover=hover;
let H='';
// ── portfolio measures ──
H+=`<h2>Three portfolio measures, same axis</h2><p class="sub">These disagree, and the
disagreement is diagnostic. <strong>STL</strong> removes the growth trend and is what the
forecast multiplies by. <strong>Raw monthly</strong> keeps the trend and is the client-chart
number. These two agree on a March peak and a late-December trough despite differing on trend —
that agreement is the real corroboration. <strong>YoY overlay</strong> is <em>not</em> a third
opinion: normalising each series-year to its own mean embeds the within-year growth ramp, so it
reads low in January and high by autumn for any growing series. It peaks in June and is
anti-correlated with STL. It is shown because it demonstrates what &ldquo;seasonality&rdquo; looks
like when trend is left in — which is also why a summer bump feels real in raw sales.</p>`;
H+=`<div class="legend"><span><i class="sw" style="background:var(--s1)"></i>STL (trend removed)</span>
<span><i class="sw" style="background:var(--s2)"></i>Raw monthly (trend included)</span>
<span><i class="sw" style="background:var(--s3)"></i>YoY overlay (trend-contaminated)</span></div>`;
H+=`<div class="card">`+chart([
{n:'STL',v:D.portfolio.stl,c:'var(--s1)'},
{n:'Raw',v:D.portfolio.raw,c:'var(--s2)'},
{n:'YoY',v:D.portfolio.yoy,c:'var(--s3)'}],{h:210,zero:true,fmt:v=>(v>=0?'+':'')+v.toFixed(2)})+`</div>`;
const pk=a=>{let b=-1,bi=0;a.forEach((v,i)=>{if(v!=null&&v>b){b=v;bi=i;}});return bi+1;};
const tr=a=>{let b=1e9,bi=0;a.forEach((v,i)=>{if(v!=null&&v<b){b=v;bi=i;}});return bi+1;};
H+=`<table><thead><tr><th>measure</th><th>peak week</th><th>trough week</th><th>amplitude</th></tr></thead><tbody>`;
[['STL (trend removed)','stl'],['Raw monthly','raw'],['YoY overlay ⚠ trend-contaminated','yoy']].forEach(([n,k])=>{
const a=D.portfolio[k].filter(v=>v!=null);
H+=`<tr><td>${n}</td><td>${pk(D.portfolio[k])}</td><td>${tr(D.portfolio[k])}</td><td>${(Math.max(...a)-Math.min(...a)).toFixed(3)}</td></tr>`;});
H+=`</tbody></table>`;
// ── per-series panels ──
H+=`<h2>${D.meta.n_panels} sampled series — RMA retailers</h2><p class="sub">Each card shows one
SKU at one retailer. The first chart overlays every year <em>normalised to its own annual mean</em>
(1.0 = that year's average week), which is the view that makes a repeating shape visible. Below it
the same years are shown unnormalised, so the growth that hides the seasonality is also visible.</p>`;
D.panels.forEach(p=>{
const ys=Object.keys(p.years).sort();
const norm=ys.map(y=>({n:y,v:p.years[y].norm,c:C[YC[y]??0]}));
const raw=ys.map(y=>({n:y,v:p.years[y].raw,c:C[YC[y]??0]}));
H+=`<div class="card"><h3>${p.desc}</h3>
<p class="meta">${p.upc} · ${p.acct} · ${p.chan} · ${p.geo}</p>
<div class="legend">${ys.map(y=>`<span><i class="sw" style="background:${C[YC[y]??0]}"></i>${y}</span>`).join('')}</div>
${chart(norm,{h:150,zero:false,fmt:v=>v.toFixed(1)})}
<details><summary>show unnormalised units (growth visible, seasonality hidden)</summary>
${chart(raw,{h:140,fmt:v=>v>=1000?(v/1000).toFixed(1)+'k':v.toFixed(0)})}</details></div>`;});
H+=`<div class="note"><strong>How to read this.</strong> In the normalised charts, 1.0 is that
year's own average week. If the lines for different years rise and fall together at the same
week numbers, the seasonality is real and repeating. If they wander independently, what looks
like seasonality in the portfolio index is mostly noise or trend, and applying a seasonal
multiplier to an individual series is not justified.</div>`;
H+=`<p class="sub" style="margin-top:20px;font-size:12px;color:var(--text-muted)">
Generated ${D.meta.generated} · raw monthly from ${D.meta.n_raw} series · YoY overlay from
${D.meta.n_yoy} series-years · RMA channel only</p>`;
document.getElementById('app').innerHTML=H;
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-series", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(); main(a.n_series, a.seed)
