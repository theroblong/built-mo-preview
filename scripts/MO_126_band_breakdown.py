#!/usr/bin/env python
"""MO_126 - is conn_L4W's advantage uniform, or concentrated in short-history series?

RECOVERED 2026-10-07. This experiment was never saved as a file: an earlier Claude
session on Jason's machine ran it inline (python heredoc, 2026-10-07T13:01Z) and wrote
outputs/mo126_band_breakdown.json, the numbers behind README update 227. The code below
is copied VERBATIM from that session's record so the result is reproducible.

What it actually scored (settles the 2026-10-07 skeptic question):
  - model = MO_80 run_production in ANCHOR seasonal mode (not the shipped step mode)
  - the full-panel MO_59 seasonal index, which has look-ahead at historical cutoffs (MO_127)
  - the pre-2026-10-07 harness: 800-tree cap, in-sample early stopping, Q3 2026 Monday cutoff

Re-running it today will NOT reproduce README 227. MO_80 now trains like production
(train_like_production) and uses Sunday cutoffs, so this script picks up those fixes and
warns that 800 trees is below the production cap. Results are superseded by MO_127
(honest index) -- see docs/SETTLED_FINDINGS.md, "Proposed changes, PENDING review".
"""
import os, importlib, pickle, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
os.environ["MO_SEASONAL_MODE"]="anchor"
import MO_80_quarterly_honest_backtest as M; importlib.reload(M)
GC=M.GROUP_COLS
feats=list(pickle.load(open("outputs/model_retailer_sales_q50_v10_full.pkl","rb")).feature_name_)
df=M.load_panel(feats); df["tdp"]=pd.to_numeric(df["tdp"],errors="coerce")
seasonal=M.load_seasonal_index()
weeks=pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])),utc=True))
BANDS=[(0,13,"<13 wks"),(13,26,"13-25 wks"),(26,52,"26-51 wks"),(52,10**4,"52+ wks")]
def band(n):
    for lo,hi,l in BANDS:
        if lo<=n<hi: return l
    return BANDS[-1][2]
def vel(bu,td,w=4):
    b=np.asarray(bu[-w:],float); t=np.asarray(td[-w:],float)
    ok=np.isfinite(b)&np.isfinite(t)
    if not ok.any(): return np.nan
    s=t[ok].sum(); return float(b[ok].sum()/s) if s>0.05 else np.nan
recs=[]
for ql,qc,q1,q2 in [q for q in M.QUARTERS if q[0]!="Q4 2026"]:
    cut=pd.Timestamp(qc,tz="UTC"); qs=pd.Timestamp(q1,tz="UTC"); qe=pd.Timestamp(q2,tz="UTC")+pd.Timedelta(days=6)
    act=df[(df["__time"]>=qs)&(df["__time"]<=qe)]
    if act.empty: continue
    truth={(k[:-1],k[-1]):float(v) for k,v in act.groupby(GC+["__time"],observed=True)["base_units"].sum().items()}
    ek={k[0] for k in truth}; fw=M.future_weeks(weeks,cut,M.HORIZON); tr=df[df["__time"]<=cut]
    model=M.run_production(df,feats,cut,qs,qe,ek,800,fw,seasonal)
    for key,g in tr.groupby(GC,observed=True):
        if key not in ek: continue
        g=g.sort_values("__time")
        bu=list(pd.to_numeric(g["base_units"],errors="coerce").fillna(0))
        td=list(pd.to_numeric(g["tdp"],errors="coerce").ffill().fillna(0))
        if len(bu)<4: continue
        v=vel(bu,td); doors=float(td[-1]) if td else 0.0; last=float(bu[-1])
        seas=M._resolve_seasonal(seasonal,key); n=len(bu)
        for step,fd in enumerate(fw[:M.HORIZON],start=1):
            if not(qs<=fd<=qe) or (key,fd) not in truth: continue
            mv=model.get((key,fd))
            if mv is None: continue
            mult=M._seasonal_mult(seas,fd,cut)
            recs.append({"band":band(n),"hist":n,"account":key[GC.index("retail_account")],
                "month":pd.Timestamp(fd).to_period("M").strftime("%Y-%m"),
                "actual":truth[(key,fd)],"model":mv,"flat":last,
                "conn_L4W":max(0.0,(v*doors*mult) if np.isfinite(v) else last)})
r=pd.DataFrame(recs)
def wm(g,a):
    d=np.abs(g["actual"]).sum(); return float(np.abs(g["actual"]-g[a]).sum()/d*100) if d>0 else np.nan
print("MO_126 - is conn_L4W's advantage UNIFORM, or concentrated in short-history series?\n")
print(f"  scored {len(r):,} cell-weeks\n")
print("CELL x WEEK by history band\n")
print(f"  {'band':<12s} {'n':>8s} {'flat':>8s} {'model':>8s} {'conn_L4W':>9s} {'conn-model':>11s}")
out={}
for _,_,l in BANDS:
    g=r[r.band==l]
    if len(g)<100: continue
    t={a:wm(g,a) for a in ["flat","model","conn_L4W"]}
    out[l]={**t,"n":len(g)}
    print(f"  {l:<12s} {len(g):>8,} {t['flat']:>8.1f} {t['model']:>8.1f} {t['conn_L4W']:>9.1f} {t['conn_L4W']-t['model']:>+11.2f}")
print("\nPORTFOLIO x MONTH by history band (same series, aggregated)\n")
print(f"  {'band':<12s} {'n':>8s} {'flat':>8s} {'model':>8s} {'conn_L4W':>9s} {'conn-model':>11s}")
for _,_,l in BANDS:
    g=r[r.band==l]
    if len(g)<100: continue
    gg=g.groupby("month",as_index=False)[["actual","flat","model","conn_L4W"]].sum()
    t={a:wm(gg,a) for a in ["flat","model","conn_L4W"]}
    out[l+"_pm"]={**t,"n":len(gg)}
    print(f"  {l:<12s} {len(gg):>8,} {t['flat']:>8.1f} {t['model']:>8.1f} {t['conn_L4W']:>9.1f} {t['conn_L4W']-t['model']:>+11.2f}")
json.dump(out,open("outputs/mo126_band_breakdown.json","w"),indent=2,default=str)
print("\nwrote outputs/mo126_band_breakdown.json")
