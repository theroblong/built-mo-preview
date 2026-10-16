"""MO_154 helper: pick the settings that go to the next stage, exactly as the pre-registered rule says.
# protocol: not-a-forecast-arm  (selection and summary of MO_154 trial records; no forecasting)

Rule (docs/PRODUCTION_DECISION_PREREG.md, "Amended 2026-10-15"): Stage 2 re-scores the 10 best DISTINCT Stage 1
settings by objective (COMPLETE trials only), plus the production settings (enqueued by the job itself).
Reads every trials_<name>.jsonl a search wrote across its jobs (first job + resumes), keeps each trial number once
(a resumed job never re-runs a finished trial), drops the production settings and exact duplicates, ranks by
objective, and writes the top N parameter sets to a JSON list for `--enqueue`.

Usage: python3 MO_154_stage_select.py --results DIR [DIR ...] --top 10 --out outputs/mo154_stage2_enqueue.json
       [--split 3]  (also writes ..._part{1..3}.json for parallel re-scoring jobs)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASELINE = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20, feature_fraction=0.8,
                bagging_fraction=0.8, reg_alpha=0.1, reg_lambda=0.2, recency=0.02,
                cal_month=False, cal_holiday=False, cal_jan_reset=False)


def load(dirs: list[str]) -> list[dict]:
    seen, recs = set(), []
    for d in dirs:
        for f in sorted(Path(d).glob("trials_*.jsonl")):
            name = f.stem.removeprefix("trials_")
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                key = (name, r["number"])
                if key not in seen:
                    seen.add(key)
                    recs.append(r | {"search": name})
    return recs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", type=int, default=0)
    a = ap.parse_args()
    recs = load(a.results)
    comp = sorted((r for r in recs if r["state"] == "COMPLETE"), key=lambda r: r["objective"])
    picked, keys = [], set()
    for r in comp:
        k = json.dumps(r["params"], sort_keys=True)
        if r["params"] == BASELINE or k in keys:
            continue
        keys.add(k)
        picked.append(r)
        if len(picked) == a.top:
            break
    by = {}
    for r in recs:
        by.setdefault(r["search"], []).append(r)
    print("trials per search:", {s: f"{len(v)} ({sum(x['state'] == 'COMPLETE' for x in v)} complete)" for s, v in sorted(by.items())})
    base = next((r for r in comp if r["params"] == BASELINE), None)
    if base:
        print(f"production settings: objective {base['objective']:.3f}, account x month {base['am']['trial']:.2f}")
    print(f"top {len(picked)} distinct settings (objective / account x month / penalty):")
    for i, r in enumerate(picked, 1):
        p = r["params"]
        print(f"  {i:>2}. {r['search']} t{r['number']:<3} {r['objective']:.3f} / {r['am']['trial']:.2f} / {r['penalty']:.3f}"
              f"  lr {p['learning_rate']:.3f} leaves {p['num_leaves']} mcs {p['min_child_samples']} rec {p['recency']:.3f}"
              f" cal m{int(p['cal_month'])}h{int(p['cal_holiday'])}j{int(p['cal_jan_reset'])}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([r["params"] for r in picked], indent=2))
    (out.with_name(out.stem + "_stage1_scores.json")).write_text(json.dumps(
        [{"search": r["search"], "number": r["number"], "objective": r["objective"], "am": r["am"]["trial"],
          "params": r["params"]} for r in picked], indent=2))
    if a.split:
        for j in range(a.split):
            part = [r["params"] for r in picked[j::a.split]]
            out.with_name(f"{out.stem}_part{j + 1}.json").write_text(json.dumps(part, indent=2))
            print(f"  part{j + 1}: {len(part)} settings")


if __name__ == "__main__":
    main()
