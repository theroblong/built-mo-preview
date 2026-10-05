# Moving Mo's model training off a laptop

**From:** Jason
**To:** Rob
**Date:** 5 October 2026

Short version: the forecasting work has outgrown my MacBook, and it is now costing us *science*, not
just time. I want to move training and experimentation onto the platform engineering lab hardware.
Below is what that actually buys, including where I think a GPU helps and where it honestly does not.

---

## Where we are today

Everything — training, hyperparameter search, backtests, chart generation — runs on my laptop,
serially, against a 93K-row panel of roughly 2,100 item × retailer × market series.

This week alone that meant:

- A hyperparameter search I had to **stop after 12 completed trials** because the full run was
  projected at 48 hours, and the laptop had to stay open, plugged in, and awake for it.
- **Pausing that search entirely** to run a different experiment, because the two would have fought
  over the same cores.
- Killing a week-old dev server that was burning a core, and adding a sleep-inhibitor, just to keep
  an overnight job alive.
- Nine separate experiments run one after another over two days that have no dependency on each
  other and could have run simultaneously.

## What the laptop is actually costing us

This is the part that matters more than wall-clock.

**1. Our headline backtest covers one account, not the portfolio.** The honest quarterly backtest
scores KROGER Conventional Food — between 20 and 39 series per quarter. Every significant finding
this week ends with the same caveat: *"confirm portfolio-wide before treating this as settled."* We
have not confirmed any of them, because portfolio-wide is roughly 50× the compute and nobody will
wait two days for one answer. **We are making architecture decisions on a 2% sample.**

**2. We cannot afford to repeat experiments, so single-fold results slip through.** Twice this week a
result looked like a win on one fold and reversed when I ran all four. Both times I caught it. The
reason it is a real risk is that running all folds is expensive enough to feel optional.

**3. Search is truncated.** The tuning we did run found a measured **2.6% accuracy improvement from
hyperparameters alone**, on 22 trials. Published practice for this kind of search is several hundred.
We stopped at 12 on the clean re-run.

**4. Deep-learning approaches are simply off the table.** Not rejected on evidence — unrunnable.

**One honest caveat against my own argument:** the biggest speedup I got this week was **55×, and it
came from fixing my own code**, not from hardware. The scorer was making ~21,500 one-row predictions
per fold where 13 batched calls would do. Hardware would have hidden that bug rather than exposing
it. So this is not a "throw silicon at it" request — I want to be clear I have done the cheap
optimization first.

---

## What lab hardware unlocks, ranked honestly

**1. Many CPU cores — the biggest win, and it is not the GPU.**

Our model is LightGBM on ~93K rows. That is a small dataset by GBDT standards, and gradient-boosted
trees on tabular data of this size see **modest gains from GPU** — the honest answer is that a GPU
would not speed up today's training much at all. What we need is **parallelism**: hyperparameter
trials are embarrassingly parallel, and so are per-account backtests. Sixteen or thirty-two cores
turns a 48-hour search into an overnight one, and makes portfolio-wide backtests routine instead of
exceptional.

**2. RAM.** Portfolio-wide backtests hold many fitted models and full prediction grids in memory at
once. And the panel is about to grow substantially — see below.

**3. Always-on.** Long runs should not depend on a laptop lid staying open. Resumable, schedulable,
survives a closed laptop and a commute.

**4. GPU — for the work we have deferred, not the work we do now.** This is where I would be
overselling if I claimed otherwise. GPU matters for:
- **Time-series foundation models** (Chronos-2 and similar) — pretrained on millions of series, used
  zero-shot. This is the most interesting unexplored direction we have, and it is the one most likely
  to handle the short-history problem that is currently our largest structural error source.
- **Neural forecasters** (TFT, N-BEATS). We measured N-BEATS at 46–118% error earlier and shelved it;
  that was an undertrained verdict reached on a laptop, and it deserves a fair retest.
- **Anything using text or embeddings** — product descriptions, flavor similarity, review signals.

---

## The modeling roadmap this makes possible

**Immediately, with cores and RAM:**
- Finish the hyperparameter search properly (we have a measured 2.6% sitting there, truncated).
- Promote every backtest from one account to the full portfolio, so our conclusions stop carrying an
  asterisk.
- Run the experiment queue in parallel instead of serially.

**Next, with headroom:**
- **New-item arrival modeling.** Our single largest measured error source: at a 13-week horizon, a
  median **14.4%** of actual volume comes from item-retailer combinations that did not exist when the
  forecast was made. We have ~1,000 observed launches to learn from. Brian confirmed the business
  mechanism on Thursday — new distribution means roughly two months of pipeline inventory filling
  both the shelf and the supplier warehouse before demand settles.
- **Per-account and per-channel model specialization** instead of one global model.
- **Proper uncertainty calibration.** Our current intervals are far too narrow and we know it;
  conformal methods need many repeated backtests, which is exactly what we cannot afford today.

**With GPU:**
- Foundation-model evaluation (Chronos-2 zero-shot vs our trained model).
- A fair retest of the neural approaches.
- Richer product representations.

**Data growth already committed.** Costco CRX is integrated, NS2 sell-in is coming for the
data-dark retailers, and Brian offered us shipment data for Casey's and the convenience chains that
SPINS does not cover. Each one multiplies the panel. The hardware question gets harder if we wait.

---

## What I am asking for

Access to the platform engineering lab hardware for model training and experimentation — ideally
something I can submit long jobs to and walk away from.

Priority order, to be explicit: **CPU cores first, RAM second, GPU third.** If the GPU box is what is
available, it is still a large win on cores and memory alone, and it opens the foundation-model work
as a bonus. But I do not want to justify it on GPU grounds, because for our current model that would
not be true.

Happy to walk through any of the measurements behind this. The short version is that we have an
experiment queue with real candidates in it, and the constraint on getting through it is no longer
ideas — it is a laptop.
