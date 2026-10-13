# Aevah compute workload profiles (done and planned)

Written for: an agent or engineer sizing this work on other infrastructure (other clouds, CPU-only
workers, local machines). As of October 13, 2026.

**Sources and rules.** Run times come from worker-recorded timings, logs and notes in this repo.
Money figures come only from RunPod billing (`compute_budget`). Per-job and per-test figures are
labelled **Estimate**, because RunPod splits shared hourly charges across overlapping jobs. Policy
caps and reservations in runpodagent are admission limits, not costs, and are not used here. Where
nothing was measured, this file says **not measured** instead of guessing.

## 1. Infrastructure in use today

| Machine | Spec | Used for |
|---|---|---|
| Laptop (Jason) | Apple M3, 8 cores (4 performance), 16 GB RAM, Python 3.12 | smoke tests, forward forecast saves, descriptive analysis, document builds, local LLM tests |
| RunPod Serverless worker (EU-RO-1) | GPU host (RTX A5000 / 3090 / A4000 / L4 / 4090 class, 24 GB) with **32-48 usable CPU cores**, no cgroup CPU quota, cgroup memory ~46 GB, /tmp ~5.4 GB, Python 3.11.11, Linux x86_64; 60 GB network volume (oonje2c8lx) for data, model caches and MLflow; up to 3 jobs at once | backtests (18 forecast dates), parity checks; planned neural models and tuning |
| Druid cluster (SPINS data) | 8 task slots (2 middle managers x 4); MSQ queries; maxNumTasks 4 (the controller counts as a task) | ingestion, table rebuilds, feature tables, data pulls |

Worker image packages (runpodagent `docs/FORECAST-WORKER.md`): PyTorch 2.6.0+cu124 (CUDA 12.4),
LightGBM, statsforecast, neuralforecast 3.1.9, lightning / pytorch-lightning 2.5.6,
chronos-forecasting 2.3.2, mlflow-skinny 3.17.0. No pretrained weights in the image: they download
on first use to `/runpod-volume/aevah/huggingface`. GPU benchmark passed on an NVIDIA L4
(runpodagent `docs/VALIDATION.md`).

Known worker behaviors:
- Worker speed varies by host. In MO_140, one job's fits ran about 2.5x faster than the other two.
- Queue wait in EU-RO-1 has ranged from 1 to 16 minutes.
- 48 OpenMP threads stalled LightGBM (parity job 002 timed out). Pin threads: 6-8 per process.
- CPU throughput was measured at 220 GFLOPS (matrix multiply) on a worker vs 225 on the laptop.
  Per-core speed is similar; the worker wins on core count.

## 2. Summary of workload types

| # | Workload | Status | Hardware it needs | Parallelism | Measured time | Measured cost (RunPod) |
|---|---|---|---|---|---|---|
| A | LightGBM direct-model backtest (the main research test) | done, routine | CPU (GPU idle) | by forecast date; 6 per worker x 6 threads | 13.4 fit-hours per standard test; ~1.3 h wall on 3 workers | **Estimate** $1.0-2.2 per test |
| B | Recursive LightGBM (served model) + forward forecast saves | done, routine | CPU | by seed / date | laptop: 3,440 s for 10 model trainings at one cutoff | laptop: $0 |
| C | Statistical baselines (ETS, SES, Holt, naive; seasonal index) | done | CPU, light | by series | not measured (small) | inside A/B |
| D | Hyperparameter tuning (Optuna) | done on the earlier recursive objective (paused); **planned last** for the final model | CPU | by trial (parallel trials) | earlier study: up to 20 min per trial, ~13 h per 30 trials | not measured |
| E | Neural forecasting (TFT, N-HiTS, TCN; Chronos-2 comparison) | **planned**; earlier laptop attempts blocked by package conflicts | GPU | by forecast date / model | not measured | not measured |
| F | Druid batch SQL (ingest, rebuilds, feature tables) | done, recurring with each SPINS delivery | Druid task slots | maxNumTasks 4 of 8 slots | backup of 72.6M rows done; heaviest step (Q2) 5-11 h | not RunPod |
| G | LLM inference for Mo Chat | done (tested) | Mac GPU (MLX) or hosted API | per request | 4-45 s per answer depending on model | not RunPod |
| H | Descriptive analysis + client documents (e.g. MO_142 Meijer brief) | done | laptop + Druid | none needed | minutes (not timed) | $0 |

## 3. Profiles

### A. LightGBM direct-model backtest (reference: MO_140, October 13, 2026)

**What it does.** For each forecast date ("origin"), it trains on data before that date, forecasts
the next 13 weeks and saves the forecasts. CPU-only; no GPU code runs.
- Model: LightGBM `LGBMRegressor`, objective=quantile (alpha 0.5) on log1p(units), "direct
  multi-horizon" (one model per horizon h = 1..13 weeks).
- Per model:
  - an early-stopping fit: up to 3,000 trees, learning_rate 0.05, num_leaves 63,
    min_child_samples 20, feature_fraction 0.8, bagging 0.8 / freq 5, early stop 100, recency
    sample weights;
  - then a refit on all data up to the cutoff at the best iteration.
  - So one **fit** (one arm x one forecast date) = 13 horizons x 2 = **26 LightGBM trainings**.
- A standard test = 18 forecast dates x 6 fits (1 baseline + 1 candidate with 5 random seeds) =
  **108 fits = 2,808 LightGBM trainings**. Feature building and scoring are small by comparison.

**Data.**
- One Parquet panel: 38.5 MB on disk, about 384 MB in pandas. It has 190,375 rows x 123 columns,
  covering 3,347 series (item x retailer) over 152 weekly periods.
- Plus two small JSON files and small side tables. Dataset folder 37 MB; code folder 20 MB.
- Output: one forecast Parquet per fit, a few MB per job.

**How it runs now.**
- 3 jobs of 6 forecast dates each, run concurrently.
- Inside a job, 6 dates run in parallel processes with 6 LightGBM threads each
  (`--parallel 6 --threads 6`).

**Measured run time** (worker-recorded seconds per fit; each fit uses 6 threads):

| Job | Forecast dates | Fits | Sum of fit-seconds | Fit min / median / max |
|---|---|---|---|---|
| 001 | 2024-12 ... 2026-03 | 36 | 6,864 | 84 / 183 / 316 |
| 002 | 2025-01 ... 2026-04 | 36 | 20,020 | 268 / 452 / 1,549 |
| 003 | 2025-02 ... 2026-05 | 36 | 21,637 | 233 / 464 / 1,526 |
| All | 18 | 108 | 48,521 (13.4 fit-hours) | |

- Totals: about 13.4 fit-hours x 6 threads, so at most about 80 core-hours. Wall time 0.5-1.3 h per
  job, about 1.3 h for the whole test.
- Later forecast dates train on more history, so they take longer.
- Single-machine reference, laptop (M3, one fit at a time, all cores, forecast date 2025-01):
  - 190 s baseline fit, 256 s candidate fit;
  - a whole test run sequentially would take about 18 x (190 + 5 x 256) s, roughly 7.3 h.

**Measured cost** (RunPod billing, **Estimate** per test):

| Test | Cost |
|---|---|
| MO_133 (main model, 5 seeds) | $1.40 |
| MO_134 | $0.64 |
| MO_135 | $0.22 |
| MO_136 | $2.20 |
| MO_137 | $1.05 |
| MO_139 | $0.97 |
| MO_140 | $1.76 |

Setup, smoke and parity checks came to $0.42. October to date, RunPod billed $8.68 for the
endpoint plus $0.93 for storage.

**Constraints.**
- Results must reproduce exactly. A parity check requires the baseline fit to match saved forecasts
  exactly on the same platform (Linux x86_64, Python 3.11). A different OS or CPU architecture can
  shift floats slightly, so parity must be re-established on new infrastructure.
- Work is independent by forecast date and by seed, so it splits cleanly across machines.

### B. Recursive LightGBM (served model) and forward forecast saves

- **What:** the production model forecasts one week at a time, feeding its own forecast back in.
  It shares LightGBM settings with A, plus a seasonal blend and a store-count gate.
- **Worker:**
  - recursive arm about 86-90 s per forecast date;
  - a direct seed 84-121 s per arm (MO_133 job 001, `--parallel 2 --threads 8`, 604 s total);
  - two-way parallel ran without slowdown.
- **Laptop:**
  - forward save `register-add5`: 5 seeds of the direct model + 5 seeds of a Tweedie variant at one
    cutoff took **3,440 s** (27,521 forecasts);
  - a one-seed test of both took 689 s.
- **Earlier recursive test:** 554 series x 13 steps x 2 arms in about 1-2 minutes.
- Production refresh run time: not measured.

### C. Statistical baselines

- **What:** statsforecast models (AutoETS, SES, Holt damped, Naive) per series, and the seasonal
  index build (MO_59).
- They run inside A and B, and on the laptop.
- Light CPU work; the run time was never measured separately.

### D. Hyperparameter tuning (Optuna)

**Done** (earlier recursive objective, MO_28; machine not recorded):
- v1 was stopped at trial 15 when its estimated finish stretched to 5 days.
- v2 was set for 60 trials at no more than 20 minutes per trial.
- Notes record "trial 30 of 60, best 31.89, about 13 hours per 30 trials" and 12 completed trials
  in the preserved study.
- Paused, because that study does not transfer if production moves to the direct model.
- Tree-budget probe (MO_29): one q50 fit with a 12,000-tree cap; the curve ended at 4,593 trees.

**Planned:**
- **Last, after the model and inputs are final.**
- Optuna TPE with pruning, on the honest multi-date 13-week objective.
- An earlier plan sized 150 trials at about 1-2 minutes per trial ("fits a weekend").

**Sizing.**
- One trial = (forecast dates scored per trial) x (seeds) x (fit time from profile A).
- For example, a trial scored on 6 dates with 1 seed = 6 fits, about 20-75 minutes of 6-thread
  time on worker hardware.
- GPU does not speed LightGBM at this size. Parallel trials do, so this is a CPU workload that
  scales by trial.
- Cost: not measured. Project it from profile A's RunPod Estimates once trials per day and dates
  per trial are fixed.

### E. Neural forecasting (planned)

**Models:**
- TFT, N-HiTS and TCN via neuralforecast 3.1.9 on the worker GPU.
- Chronos-2 (chronos-forecasting 2.3.2) as a zero-shot comparison only, not for production unless
  extremely good.
- The roadmap also lists DeepAR as a bounded challenger.

**History:**
- Earlier laptop attempts at TFT, N-BEATS and Chronos-2 were blocked by a torch/torchvision version
  conflict (MO_38/66).
- One TFT evaluation ran on the earlier, flawed benchmark (provisional).
- The worker image now has compatible versions.

**Data scale:**
- Same panel as A: 3,347 series x 152 weeks, about 190k rows.
- Notes flag that the data is small for deep models: about 260 long series, under 3 years of history.

**Expected shape:**
- One global model per forecast date (18 dates), possibly several seeds.
- GPU training followed by inference; work splits by date.
- Pretrained weights (Chronos-2) download once into the volume cache.

**Not measured:** epochs to converge, time per epoch, GPU memory, cost. First step is a bounded
timing test (smoke default: 5 minutes, $0.50 ceiling).

### F. Druid batch SQL

- **Cluster:** 8 task slots. Use maxNumTasks 4: the controller counts as a task, and 8 ran slower
  than 4 on this cluster. An older note saying 16 is out of date.
  - Writes use REPLACE ... OVERWRITE WHERE (scoped to the window); never INSERT except one step.
  - Poll progress through the Tasks API.
- **Done:**
  - backup of `built_filtered_weekly` (72,643,134 rows);
  - SPINS ingestion (about 107M rows total, about 10.4M new per delivery);
  - feature and scoring tables.
- **Heaviest step:** Q2 `comparison_pool_weekly`, recorded at about 11.4 h with maxNumTasks 8 and
  5-6 h elsewhere. It runs in one-year batches.
- **Planned:** the 25-step rebuild that fixes the MULO label, with the next SPINS delivery (EXPLAIN
  dry run of all steps passed).
- Not RunPod; cost depends on the Druid hosting, which this file does not cover.

### G. LLM inference (Mo Chat)

- Target: answers in under 5 seconds.
- Local, on the 16 GB Mac:
  - Qwen3-8B (MLX 4-bit, about 4.35 GB, served by vllm-mlx): about 4 s warm, 15-25 s with full
    context;
  - Gemma 4 12B (4-bit, 8.3 GB): 25-45 s.
- Hosted: Claude Haiku, first token in 1-2 s, 4-8 s total. An OpenAI backup is configured.
- GPU hosting of the local model was considered, not run.

### H. Descriptive analysis and client documents

- **Example:** MO_142, the Meijer brief v2.
- **Druid pulls:**
  - BUILT rows for 38 retailer geographies (37k rows);
  - all bar brands at Meijer stores (115k rows);
  - category totals.
- **Analysis on the laptop:** pandas and statsmodels fixed-effects regressions; launch and placebo
  calculations.
- **Document build:** matplotlib charts, python-docx, and the PDF exported by Microsoft Word.
- Minutes per run; not timed. No GPU or worker needed.

## 4. Measurement gaps (measure before sizing)

- Peak RAM per fit process in profile A (6 run at once per worker; the panel itself is about 0.4 GB).
- Exact LightGBM version in the worker image (hash-locked; see runpodagent `docs/FORECAST-WORKER.md`).
- Neural models (E): epochs, time per epoch, GPU memory, and cost from a timing test.
- Optuna (D): time per trial on the final objective and how many trials can run in parallel.
- RunPod CPU-only workers: speed per core and price. Not available through our tools; RunPod's
  pricing page lists CPU worker rates.
- Production refresh run time (B) and statistical-baseline time (C).

## 5. Practical guidance for another environment

- Profiles A, B, C, D and H are **CPU workloads**. The best fit is many fast cores (32+) with
  6-8 threads per process and processes split by forecast date or trial. RAM per process is not
  measured (the shared panel is about 0.4 GB in memory); measure it before sizing. A GPU adds nothing
  to them.
- Profile E is the only **GPU workload**; a 24 GB card is enough at this data size.
- Profile F stays on Druid.
- Profile G is latency-bound: a Mac GPU (MLX) or a hosted API.
- Whatever replaces the current worker must first pass the parity check (profile A constraints)
  before its results count.
