# Exec summary for Rob: 2026-10-07 (Jason's session)

## Bottom line
- **Our forecast-accuracy claims don't hold.** We stopped repeating them, starting with
  Mo Chat, and track corrections in one place.
- **Every backtest's seasonal index had look-ahead.** Without it, the v12 velocity anchor
  roughly ties "repeat recent sales" at the planning level. It still beats our current
  model on established items.
- **On the longest-history PUFF SKUs, Connor's sales-per-store × stores method beats our
  model.** Recommendation: fix the backtest yardstick first, then rebuild the model as
  "Connor's anchor + ML corrections".

## 1. Accuracy claims: corrected and tracked
- **We found 13 places quoting retired figures:** 4%, 4.3%, 2–6%, 6.1% and "5× better
  than foundation models".
  - Tracker: `docs/ACCURACY_CLAIMS_REGISTER.md`. It carries a "don't quote externally
    yet" warning: today's shipped forecast hasn't been measured on the corrected setup.
- **Mo Chat is fixed** (approved by Jason, with your OK). It gives no percentage for Mo's
  own forecast and explains accuracy in plain language. It goes live on the next Mo API
  redeploy.
- **Stance (Jason):**
  - Accuracy isn't the headline for now.
  - Demand velocity forecasting stays the main deliverable.
  - Metrics like wMAPE are always explained for a CFO/FP&A reader.

## 2. Your settled-findings draft: Jason's review
- **Load only the key parts each session** (about 110 lines). Data facts and older
  results stay in the file for lookup.
- **Model vs flat at portfolio × month: not settled.** Don't cite "ML beats naive at the
  planning level".
- **BUILT's "7%" moves from FACT to an open question.**
- **Meijer brief: already rebuilt on Meijer RMA data on Sept 25.** No action.
- **Skeptic-proposed updates (live notes) for the two of you to review:**
  - **MO_113 anchor mode → reversed.**
  - **MO_125 "conn_L4W 10.7" → reversed.**
  - **README 223 → reversed.**
  - **MO_126 → re-scoped.**
  - **New rule:** every fitted input is rebuilt from data up to each cutoff.

## 3. MO_127: seasonal look-ahead (checked by the skeptic agent)
- **No honest seasonal index was possible at any 2025 cutoff.** The panel starts
  2023-10-15, so zero series had 104 weeks then.
- **The full index flatters every arm.** Flat improves from 16.0 to 9.0 at portfolio ×
  month just by adding it.
- **Honest standings** (average miss; conn and flat with no seasonal):

  | Level | conn_L4W | flat | model |
  |---|---|---|---|
  | cell × week | 32.5 | 32.8 | 36.7 |
  | account × month | 21.7 | 22.9 | 26.2 |
  | portfolio × month | 16.4 | 16.0 | 17.3 |

  - conn beats the model by 4–7pp on 26+ week series, but beats flat only on 52+.
- **Rebuilding the index honestly with MO_59's method doesn't work on 2 years of data.**
  STL with two cycles absorbs growth into the seasonal term, and the index jumps at the
  cutoff week.

## 4. MO_128: long-history PUFF vs Connor (checked by the skeptic agent)
**Focal SKUs.** Full panel history, 152 weeks (2023-10-15 to 2026-09-06), top series by
volume:

| SKU | UPC | Retailers |
|---|---|---|
| PUFF Brownie Batter 1.41oz single | 08-40229-30362 | Kroger, Circle K, Publix, UNFI, Maverik, CVS, Wegmans, AWG, Albertsons, Hy-Vee |
| PUFF Coconut 1.41oz single | 08-40229-30037 | Circle K, Kroger, Publix, Maverik, UNFI, CVS, Wegmans, Albertsons, AWG |
| PUFF Brownie Batter 4-pack | 08-40229-30380 | Walmart (1.18M base units, last 52 wks), Meijer |
| PUFF Coconut 4-pack | 08-40229-30381 | Walmart (0.99M), Publix, Meijer |

- **Wider set:** 262 PUFF series with 2+ years of history and 749 with 1+ year.
- **Walmart's 1.41oz singles are relaunches, not long-history items:** stray scans for two
  years, then about 40 TDP from Jan 2026. History needs to be counted as calendar span
  with real distribution, not rows.
- **Results:**
  - **Connor's L4W is the best method** on 52+ week PUFF (cell × week 27.4, account ×
    month 23.8). Our model scores 33.9 and 29.3.
  - **L12W (Connor's default) wins only in Q1 and Q2 2026.** Its apparent lead on 104+
    items comes from Q1 2026 plus Sam's and Walmart, so don't route to L12W.
  - **On the focal SKUs the model beats L4W on 37 of 210 retailer series,** but those are
    7% of the volume.
- **Every method misses the seasonal turns.** Q1 (New Year) is 28% of volume but 37–60%
  of monthly error, with every method 25–55% low. Q4 2025 runs 20–40% high.
- **Training without BAR helps only in late 2025.** BAR's share of training fell from
  17.6% to 3.0%, so there's little left to remove.

## 5. What production does today (audit)
- **Implemented:**
  - MO_27 + v11 (56 features)
  - source_brand **as a feature**
  - parent_brand filter
  - flavor
  - step-over-step seasonal
  - <13-week last-value router
  - lapse gate
  - feature-freeze parity
- **Not implemented:**
  - BAR exclusion or any brand stratifier
  - velocity anchor
  - 1.5× cap
  - BAR→PUFF chain-linking
  - per-store target
- **The YoY ratio is clipped to 0.5–2.0** (MO_27:571). It's a candidate to test.

## 6. Agreed roadmap (Jason approved)
1. **Fix the yardstick.**
   - Q3 2026 cutoff `2026-06-29` is a Monday → `2026-06-28` (MO_80:206; your harness).
   - About 20 monthly origins instead of 7 quarters.
   - Score new series too.
   - Count history as calendar span with distribution.
   - Rebuild every fitted input at the cutoff.
2. **Fair model training.**
   - Uncap trees (800 vs about 4,600 at convergence).
   - Time-based validation split. `va = tr.tail()` (MO_80:365) takes the last series,
     not the latest weeks; check MO_26 too.
   - Calendar-aligned year-ago for series with gaps.
   - Test removing the YoY clip.
3. **MO_129: Connor's anchor + ML corrections.** It covers promo, price, distribution and
   the New Year step-up, with velocity × doors as the target.
4. **Seasonal turns:** a pooled per-store Jan/Q4 effect and a shrunk index; revisit STL
   after Jan 2027.
5. **Optuna on the step-3 winner,** against the honest 13-week multi-origin backtest.
6. **RunPod GPUs:** parallel backtests and Optuna now, then one bounded deep-model
   challenger.

**Shipping option after step 1:** Connor-style velocity × doors (L4W) for established
items, last value for new items, no STL seasonal. ML earns its way in as the corrections
layer.

## Asks for you
1. OK the one-character cutoff fix in MO_80, and the time-based validation split.
2. Review the settled-findings draft together with Jason's answers and the skeptic
   proposals (live notes in `agents/project_memory.md`).
3. Redeploy the Mo API so the Mo Chat wording goes live.
4. Find the MO_126 script if you have it.
