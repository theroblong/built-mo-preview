"""MO_154 - Which LightGBM settings (and calendar inputs) make the production fixed direct model forecast best
across the honest backtest, especially through the holiday dip and the Q1 rise?

WHERE THIS CAME FROM: Jason (2026-10-15): "find the optimal hyperparameter tuning for the production model to make
the best possible predictions from all the data we have"; "make sure we have our best chance of showing more
accuracy for Q1 2026 and also for Q1 2027 ... the holiday decline and then New Year renewed interest up thru
promotional period getting ready for summer swim season ... the seasonal trend as well as the growth magnitude".
Approved: two studies within a $30 weekend budget; the as-of promotion statistics (MO_155) if MO_155 adopts them.

PRIOR WORK (docs/SETTLED_FINDINGS.md / README; topic words: tuning, hyperparameter, learning rate, leaves,
early stopping, seasonal, Q1, holiday, recency):
- MO_29 (PROVISIONAL, pre-correction): early stopping fires near 4,593 trees at lr 0.04 / 63 leaves; set
  n_estimators by budget; reopen if 3-fold CV confirms -> tuning under the honest harness meets the reopen-if.
- Q1 under-forecast is the known seasonal miss (Jan-Mar 2025 bias 0.68, Jan-Mar 2026 0.98, Oct-Dec 2025 1.099;
  MO_128: 52+ PUFF Q1 bias ~0.55, PROVISIONAL). No honest seasonal index at 2025 cutoffs (FACT, panel starts
  2023-10). MO_76 macro inputs archived (reopen with 2+ more years) -> not searched here.
- Production decision rule: docs/PRODUCTION_DECISION_PREREG.md Amendments 1 + 2 (criterion 4 = seasonal bias).

DESIGN (honest harness MO_80/MO_132 run_direct, refit=True, calendar targets; one seed per trial):
  AMENDED 2026-10-15 before any tuning result (docs/PRODUCTION_DECISION_PREREG.md, "Amended 2026-10-15"): Study B
  dropped; one honest study on the 15 tuning dates (2026-03/04/05 held out) in three stages:
    Stage 1  --origins 2024-12,2025-03,2025-06,2025-09,2025-12,2026-02, ~40 trials x 3 searches (--sampler-seed 1/2/3)
    Stage 2  --enqueue top 10 Stage 1 settings + production, all 15 dates; then ~30 TPE trials with --prior history
    Stage 3  top 3 x 5 seeds x 18 dates; winner by 15-date objective only; held-out dates judge it (P3, Amendment 1+2)
  Original design (kept for the record): Study A tune on the first 15 origins with 2026-03/04/05 held out; Study B
  on all 18 origins.
  Search space: learning_rate [0.02, 0.10] log; num_leaves [15, 255] log; min_child_samples [5, 200] log;
    feature_fraction [0.5, 1.0]; bagging_fraction [0.5, 1.0]; reg_alpha, reg_lambda [1e-3, 10] log;
    recency lambda [0.0, 0.05]; calendar inputs (each on/off): target month, holiday week, early-January weeks.
  Objective (lower = better): account x month miss % over the tuning origins
    + 50 x (excess of |bias - 1| beyond 0.10 for each Jan-Mar and Oct-Dec window in those origins).
  Pruning: origins scored in batches; a trial whose running score is worse than the median of finished
  trials after the first batch is stopped (Optuna MedianPruner, 5 startup trials).
  Rows the trial does not forecast use the same-seed production forecast (MO_148 rule); new/lapsed rows = 0.
  The first trial of every study is the current production settings (the baseline).

LEVELS: the objective is account x month; every trial also records cell x week and portfolio x month (pooled
and band-separated) and BY HISTORY BAND results (<13 / 13-25 / 26-51 / 52+ wks), so a winner that trades
established bands for young ones is visible. Top settings then get 5 seeds (tuned_a_avg5 / tuned_b_avg5) and
the full switching rule, with Study A judged on the held-out 2026-03/04/05 dates.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  The baseline trial reproduces direct_fixed_s42 exactly on the tuning origins (parity).
  P2  The best Study A setting beats the baseline objective on the tuning origins by at least 0.5 points.
  P3  On the held-out 2026-03/04/05 dates, the best Study A setting (5 seeds) is not worse than direct_avg5 at
      account x month by more than 0.3 (tuning generalizes rather than over-fits).
  P4  At least one calendar input is switched on in the best Study A and Study B settings (the seasonal cycle
      is learnable from calendar inputs).
  P5  Study A's and Study B's best settings agree on the calendar inputs and their learning rates are within
      a factor of 2 (the result is not an accident of which dates were tuned on).
  If P3 fails, the tuning over-fit the tuning dates and the production settings stay.
  AMENDED P2 / P5 (staged design, before any result): P2 the best Stage 2 setting beats the production settings'
  15-date objective by at least 0.5. P5 the 6-date Stage 1 screen is informative: across the 10 re-scored settings,
  rank correlation between 6-date and 15-date objectives >= 0.5.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_155
import importlib                                      # noqa: E402

import MO_80_quarterly_honest_backtest as M           # noqa: E402  import asserts forecast + training parity

importlib.reload(M)
import MO_132_one_yardstick as P                      # noqa: E402
import MO_133_ensembles as E                          # noqa: E402
import MO_134_recursive_fair_settings as B            # noqa: E402

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ROWS_IN = "mo140_rows.parquet"                        # in the dataset dir on the worker; outputs/ on the laptop
ALL_ORIGINS = [o[0] for o in M.ORIGINS_MONTHLY]
HELD_OUT = ["2026-03", "2026-04", "2026-05"]
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]
AM, CW, PM = "account x month", "cell x week", "portfolio x month"
BASELINE = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20, feature_fraction=0.8,
                bagging_fraction=0.8, reg_alpha=0.1, reg_lambda=0.2, recency=0.02,
                cal_month=False, cal_holiday=False, cal_jan_reset=False)
PENALTY = 50.0

_CACHE: dict = {}


def _init(feats_r, feats_d, promo_asof, threads):
    M.PROMO_ASOF = bool(promo_asof)
    P.D26.LGBM_BASE["n_jobs"] = threads
    _CACHE["panel"] = E._panel(feats_r, feats_d)
    _CACHE["feats_d"] = list(feats_d)


def _origin_forecast(lbl: str, params: dict) -> pd.DataFrame:
    """One origin, one parameter set, seed 42: 13-horizon direct forecasts (fit + refit)."""
    if lbl not in _CACHE:
        _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
        _CACHE[lbl] = (M._utc(c), M.cutoff_frame(_CACHE["panel"], M._utc(c)))
    cut, tr = _CACHE[lbl]
    lg = P.D26.LGBM_BASE
    for k in ("learning_rate", "num_leaves", "min_child_samples", "feature_fraction", "bagging_fraction",
              "reg_alpha", "reg_lambda"):
        lg[k] = params[k]
    lg["random_state"] = 42
    P.D26.RECENCY_LAMBDA = params["recency"]
    P.CAL_EXTRA = tuple(n for n in ("month", "holiday", "jan_reset") if params[f"cal_{n}"])
    feats = _CACHE["feats_d"] + [P.CAL_COLS[n] for n in P.CAL_EXTRA]
    f = P.run_direct(tr, feats, cut, refit=True, calendar=True)
    return f.assign(origin=lbl).rename(columns={"value": "trial"})


def score(rows: pd.DataFrame, fc: pd.DataFrame, origins: list[str]) -> dict:
    r = rows[rows["origin"].isin(origins)].copy()
    fc = fc.assign(date=pd.to_datetime(fc["date"], utc=True))
    r = r.merge(fc[["origin", "series", "date", "trial"]], on=["origin", "series", "date"], how="left")
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    miss = r["trial"].isna().values & ~zero
    r["trial"] = np.where(zero, 0.0, np.where(miss, r["direct_fixed_s42"], r["trial"]))
    ex = r[~r["is_new"]]
    arms = ["trial", "direct_fixed_s42", "direct_avg5"]
    S = M.score_levels(ex, arms)
    sb = B.season_bias(ex, arms)
    pen = sum(max(0.0, abs(v["trial"] - 1) - 0.10) for k, v in sb.items() if k.startswith(("Jan-Mar", "Oct-Dec")))
    return {"objective": S[AM]["trial"] + PENALTY * pen, "am": S[AM], "cw": S[CW], "pm": S[PM],
            "pm_bias": S["portfolio_bias"], "season_bias": sb, "penalty": pen, "fallback_rows": int(miss.sum()),
            "by_band_am": {b: {a: v[a] for a in arms} | {"n": v["n"]} for b, v in S[AM]["by_band"].items()},
            "by_band_pm": {b: {a: v[a] for a in arms} | {"n": v["n"]} for b, v in S[PM]["by_band"].items()}}


def suggest(trial) -> dict:
    return dict(
        learning_rate=trial.suggest_float("learning_rate", 0.02, 0.10, log=True),
        num_leaves=trial.suggest_int("num_leaves", 15, 255, log=True),
        min_child_samples=trial.suggest_int("min_child_samples", 5, 200, log=True),
        feature_fraction=trial.suggest_float("feature_fraction", 0.5, 1.0),
        bagging_fraction=trial.suggest_float("bagging_fraction", 0.5, 1.0),
        reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        recency=trial.suggest_float("recency", 0.0, 0.05),
        cal_month=trial.suggest_categorical("cal_month", [False, True]),
        cal_holiday=trial.suggest_categorical("cal_holiday", [False, True]),
        cal_jan_reset=trial.suggest_categorical("cal_jan_reset", [False, True]))


def _distributions() -> dict:
    """The search space as Optuna distributions (must match suggest()), for adding prior trials as history."""
    from optuna.distributions import CategoricalDistribution as C, FloatDistribution as F, IntDistribution as I
    return dict(learning_rate=F(0.02, 0.10, log=True), num_leaves=I(15, 255, log=True),
                min_child_samples=I(5, 200, log=True), feature_fraction=F(0.5, 1.0), bagging_fraction=F(0.5, 1.0),
                reg_alpha=F(1e-3, 10.0, log=True), reg_lambda=F(1e-3, 10.0, log=True), recency=F(0.0, 0.05),
                cal_month=C([False, True]), cal_holiday=C([False, True]), cal_jan_reset=C([False, True]))


def _prior_records(paths: str, tune: list[str]) -> list[dict]:
    """COMPLETE trial records from earlier jobs' trials_*.jsonl, scored on exactly these tuning dates."""
    recs = []
    for p in [x for x in paths.split(",") if x]:
        for line in Path(p).read_text().splitlines():
            r = json.loads(line)
            if r.get("state") == "COMPLETE" and sorted(r.get("origins", [])) == sorted(tune):
                recs.append(r)
    return recs


def run_study(a) -> None:
    import shutil
    import optuna
    from optuna.storages import JournalStorage
    from optuna.storages.journal import JournalFileBackend
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    journal = out / f"study_{a.name}.log"
    resume = os.environ.get("AEVAH_RESUME_FROM", "")      # continue a study after a job hit its time cap
    if resume and Path(resume).name == journal.name and not journal.exists():
        shutil.copy(resume, journal)
    data_dir = Path(a.data_dir)
    rows = pd.read_parquet(data_dir / ROWS_IN)
    rows["date"] = pd.to_datetime(rows["date"], utc=True)
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    tune = [o for o in ALL_ORIGINS if a.study == "B" or o not in HELD_OUT]
    if a.origins:                                     # Stage 1 screen dates (and smoke tests)
        tune = [o for o in tune if o in a.origins.split(",")]
    # interleave years so every batch mixes seasons (running score comparable across batches)
    tune = sorted(tune, key=lambda o: (int(o[5:7]) % 3, o))
    batches = [tune[i:i + a.parallel] for i in range(0, len(tune), a.parallel)]
    storage = JournalStorage(JournalFileBackend(str(journal)))
    study = optuna.create_study(study_name=f"mo154_{a.name}", direction="minimize", storage=storage,
                                load_if_exists=True, sampler=optuna.samplers.TPESampler(seed=a.sampler_seed),
                                pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0))
    if len(study.trials) == 0:
        # Stage 2: earlier jobs' trials on the same dates become history without re-computation
        dist = _distributions()
        for r in _prior_records(a.prior, tune):
            study.add_trial(optuna.trial.create_trial(params=r["params"], distributions=dist, value=r["objective"]))
        if not a.no_baseline:
            study.enqueue_trial({k: v for k, v in BASELINE.items()})
        if a.enqueue:                                 # Stage 2 re-scoring: settings evaluated before any TPE trial
            for p in json.loads(Path(a.enqueue).read_text()):
                study.enqueue_trial(p)
    t_end = time.time() + a.seconds
    log = out / f"trials_{a.name}.jsonl"
    with ProcessPoolExecutor(max_workers=a.parallel, mp_context=get_context("spawn"), initializer=_init,
                             initargs=(feats_r, feats_d, a.promo_asof, a.threads)) as ex:
        n = 0
        while n < a.trials and time.time() < t_end:
            trial = study.ask()
            params = suggest(trial)
            t0, parts, pruned = time.time(), [], False
            for bi, batch in enumerate(batches):
                futs = [ex.submit(_origin_forecast, o, params) for o in batch]
                parts += [f.result() for f in as_completed(futs)]
                done = [o for b in batches[:bi + 1] for o in b]
                running = score(rows, pd.concat(parts, ignore_index=True), done)["objective"]
                trial.report(running, bi)
                if trial.should_prune():
                    pruned = True
                    break
            rec = {"number": trial.number, "params": params, "seconds": round(time.time() - t0, 1), "origins": tune}
            if pruned:
                study.tell(trial, state=optuna.trial.TrialState.PRUNED)
                rec["state"] = "PRUNED"
            else:
                S = score(rows, pd.concat(parts, ignore_index=True), tune)
                study.tell(trial, S["objective"])
                rec |= {"state": "COMPLETE", **S}
            with open(log, "a") as fh:
                fh.write(json.dumps(rec, default=float) + "\n")
            print(f"trial {trial.number} {rec['state']} obj={rec.get('objective', float('nan')):.3f} "
                  f"am={rec.get('am', {}).get('trial', float('nan')):.2f} {rec['seconds']}s {params}", flush=True)
            n += 1
    best = study.best_trial
    (out / f"best_{a.name}.json").write_text(json.dumps({"number": best.number, "value": best.value,
                                                          "params": best.params, "tune_origins": tune}, indent=2))
    print("BEST", best.number, round(best.value, 3), best.params, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tune"])
    ap.add_argument("--study", choices=["A", "B"], required=True)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seconds", type=int, default=3 * 3600)
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--sampler-seed", type=int, default=1)
    ap.add_argument("--promo-asof", type=int, default=0)
    ap.add_argument("--origins", default="", help="restrict tuning origins (Stage 1 screen dates; smoke tests)")
    ap.add_argument("--name", default="", help="study/file name, e.g. s1a; defaults to --study")
    ap.add_argument("--enqueue", default="", help="JSON list of settings to evaluate first (Stage 2 re-scoring)")
    ap.add_argument("--prior", default="", help="comma-separated trials_*.jsonl whose COMPLETE trials on the same "
                                                "dates are added as history (Stage 2 TPE)")
    ap.add_argument("--no-baseline", action="store_true", help="do not enqueue the production settings")
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo154_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--data-dir", default=os.environ.get("AEVAH_DATASET_DIR", "outputs"))
    a = ap.parse_args()
    a.name = a.name or a.study
    run_study(a)


if __name__ == "__main__":
    main()
