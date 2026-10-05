# Aevah High-Growth CPG Forecasting: Commercial Event & Growth Modeling

## Core idea

For a high-growth CPG customer, **new locations, promotions, launches, distribution changes, pricing, and other commercial events should be explicit forecast drivers**, not noise that the model is expected to infer from history.

The forecast should answer:

> **What happens next given what the business is about to change?**

Rather than simply:

> What usually happens next?

The recommended architecture is:

\[
Forecast =
Base\ Demand
\times
Distribution\ Effect
\times
Seasonality
\times
Promo\ Effect
\times
Launch/Ramp\ Effect
\times
Price\ Effect
\times
Cannibalization
+ Load\ In
\]

The ML model can learn these effects rather than relying on fixed percentages.

---

# 1. New locations should be modeled as distribution events

For a high-growth customer, this is one of the most important variables.

Do not simply use:

```text
store_count = 1,200
```

Capture the **change in distribution over time**:

```text
stores_authorized
stores_selling
new_stores_this_week
stores_lost_this_week
distribution_pct
ACV_distribution
weeks_since_distribution_change
```

The model can learn a distribution ramp curve.

Example:

```text
Walmart:
800 → 1,600 stores

Week 0      Initial shipments
Week 1      42% mature velocity
Week 2      63%
Week 3      79%
Week 4      88%
Week 6      96%
```

This becomes a learned **distribution ramp curve**.

Do not assume that newly added stores immediately achieve mature velocity.

---

# 2. Distinguish load-in from consumer demand

When 500 new stores are added, shipments spike because those locations initially need to be stocked.

That does not mean consumer demand doubled.

Separate:

### Sell-in

What the CPG company ships to the retailer/distributor.

### Sell-through

What consumers actually buy.

For example:

```text
500 new stores

Initial shelf quantity:
12 units/store

Pipeline load-in:
6,000 units
```

The load-in belongs in the shipment/revenue forecast, but it should **not permanently inflate demand velocity**.

Aevah should distinguish:

```text
consumer_demand_forecast
+
inventory_load_in
+
replenishment
=
shipment_forecast
```

This distinction is especially important for rapidly expanding brands.

---

# 3. Promotions should be represented as events

Create a dedicated `commercial_event` object containing fields such as:

```text
event_id
retailer
SKU
geography
start_date
end_date
event_type
discount_depth
feature
display
ad_support
digital_support
expected_store_count
expected_distribution
funding
```

Potential event types:

```text
TPR
Rollback
BOGO
Feature
Display
Feature + Display
Digital promo
Retail media
Endcap
Club event
Sampling
```

The goal is to learn the actual demand response to each event type.

---

# 4. Promotions need three effects, not one

Instead of modeling only "promo uplift," model:

### Pre-promo dip

Consumers may delay purchases while waiting for a promotion.

### Promo lift

The primary increase during the event.

### Post-promo dip

Some promotional purchases are pantry loading rather than truly incremental consumption.

Conceptually:

```text
        Baseline
           │
      ↓ Pre-buy dip
           │
      ↑↑ Promo lift
           │
      ↓ Post-promo dip
           │
        Baseline
```

Example:

```text
Week -1      -4%
Week 0      +31%
Week +1     +24%
Week +2      -9%
Week +3      -4%
```

This is substantially more informative than applying a simple +25% multiplier during the promotion.

---

# 5. Promotional lift should depend on context

Do not create one universal promo multiplier.

The model should consider:

```text
discount_depth
retailer
SKU
category
geography
time_of_year
display
feature
digital_media
baseline_velocity
distribution
competitive_promotions
weeks_since_previous_promo
```

Example:

```text
20% discount alone          +12%
20% + feature               +19%
20% + feature + display     +31%
```

Different retailers may respond very differently to the same promotion.

---

# 6. New SKU launches need their own lifecycle model

For a high-growth customer, new SKUs should be treated separately from established products.

Each SKU can have a lifecycle state:

```text
pre-launch
launch
ramp
established
declining
discontinued
```

Useful features:

```text
weeks_since_launch
distribution_at_launch
brand_family
flavor
pack_size
price
retailer
category
launch_support
```

For a new SKU with little or no history, Aevah can borrow information from analogous products:

- other launches from the same brand
- launches at the same retailer
- similar flavors
- similar pack sizes
- similar price points
- similar initial distribution levels

This provides a cold-start forecast.

---

# 7. New SKU sales are not necessarily incremental

A new SKU selling $5M does not necessarily mean the company gained $5M in incremental demand.

Example:

```text
$5.0M new SKU sales
-$1.8M cannibalized existing SKU sales
------------------------------
$3.2M incremental revenue
```

Therefore:

\[
Incrementality =
New\ SKU\ Demand - Cannibalized\ Demand
\]

Cannibalization can vary by:

```text
retailer
category
flavor similarity
price point
shelf space
number of existing SKUs
```

This should become an explicit predictive problem in Aevah.

---

# 8. Distribution gains can cannibalize other channels

A retailer expansion can increase total brand consumption while simultaneously shifting sales from other channels.

Example:

```text
Walmart expansion:
+$8.2M Walmart
-$0.8M Amazon
-$0.3M DTC
----------------
+$7.1M net incremental
```

Aevah should therefore look for **cross-channel substitution**, not just SKU-level cannibalization.

---

# 9. Planned events need to enter the future feature matrix

Traditional ML models only know historical features.

Forecast models need access to **future known information**.

For every future week, build a feature record such as:

```text
Week: 2027-W05

Retailer: Costco
SKU: Chocolate Puff

planned_stores             620
promo_active               1
discount_pct               15%
feature                    1
display                    0
price                      $19.99
new_distribution           80 stores
weeks_since_launch         14
seasonality_index          0.94
```

The forecast engine predicts based on the actual commercial plan.

Without these future-known variables, the model cannot anticipate planned growth events.

---

# 10. Separate known future variables from unknown future variables

This distinction is critical.

## Known future

Examples:

```text
promo calendar
planned launches
authorized stores
planned distribution
price changes
retailer resets
media spend
holidays
contracted orders
```

These should be direct forecast inputs.

## Unknown future

Examples:

```text
actual consumer velocity
competitive actions
execution quality
retailer compliance
unexpected weather
unexpected stockouts
```

These must be forecasted or represented probabilistically.

This lets Aevah say:

> Given the planned promotion and store expansion, expected revenue is $12.4M.

rather than pretending $12.4M is an unconditional prediction.

---

# 11. Stockouts and supply constraints need to be modeled separately

For a high-growth customer, observed sales can substantially understate true demand because the product is unavailable.

Track:

```text
in_stock_pct
days_out_of_stock
fill_rate
inventory_on_hand
weeks_of_supply
OTIF
```

Otherwise the model can learn:

> Demand is 7 units/store/week.

when the reality is:

> Demand is 10 units/store/week, but product was out of stock 30% of the time.

Aevah should explicitly distinguish:

\[
Observed\ Sales \neq True\ Demand
\]

This can materially improve forecasts.

---

# 12. Create a growth event ledger

Aevah should maintain a timeline of material commercial events.

Example:

| Date | Event | Retailer | Scope |
|---|---|---|---|
| Jan 5 | New stores | Walmart | +450 |
| Jan 19 | Promo | Kroger | 20% TPR |
| Feb 2 | SKU launch | Target | New Puff flavor |
| Feb 15 | Distribution expansion | Costco | +3 regions |
| Mar 1 | Price increase | Amazon | +6% |

Every event should eventually be tied to:

**forecast → observed outcome → learned effect**

Over time, Aevah builds a customer-specific knowledge base of commercial event responses.

---

# 13. This becomes causal learning, not just forecasting

This is where the capability becomes strategically more valuable.

Instead of only asking:

> What will revenue be?

Aevah can ask:

> What will revenue be **because** we add 500 stores?

Or:

> How much of this promotion is truly incremental?

Or:

> Should we launch another flavor?

Example:

```text
Expected baseline              $8.4M
Add 500 Walmart stores         +$2.1M
March promo                    +$0.7M
New flavor                     +$0.9M
Cannibalization                -$0.4M
Supply constraint              -$0.2M
-----------------------------
Forecast                       $11.5M
```

The forecast is simultaneously an explanation of the major drivers.

---

# 14. Use two complementary models

For this customer, run two conceptual models.

## Model A — Baseline demand model

Predicts what happens with **no new commercial intervention**.

## Model B — Event response model

Estimates the incremental effect of:

```text
new stores
promotions
new SKUs
price changes
display
media
distribution changes
```

Then:

\[
Total\ Forecast =
Baseline + Incremental\ Event\ Effects
\]

This is cleaner than forcing one giant model to learn every phenomenon at once.

---

# 15. Keep Connor's spreadsheet methodology as a challenger

The comparison becomes much more informative when Aevah exposes the assumptions.

For example:

```text
                    Connor     Aevah
Base velocity        10.2       10.7
New store ramp        85%        73%
Promo lift            20%        29%
Post-promo dip         0%        -8%
Cannibalization       10%        18%
```

After actuals arrive:

```text
Actual promo lift: +27%
```

Aevah gets evidence that its learned event response was closer to reality.

Connor's assumptions remain visible and continuously benchmarked.

---

# 16. Recommended initial feature set

For this high-growth customer, prioritize these variables:

1. **Store/distribution count over time**
2. **Weeks since launch / distribution expansion**
3. **Initial load-in**
4. **Recent L4/L12/L26 velocity**
5. **Promo flag + depth + type**
6. **Feature/display support**
7. **Price**
8. **Seasonality**
9. **In-stock / supply constraints**
10. **SKU cannibalization**
11. **Retailer/channel**
12. **Geography**

Then add more specialized signals only when they demonstrate out-of-sample improvement.

---

# 17. The architectural shift

The critical change is:

> **High growth should not appear to the model as unexplained volatility.**

Aevah should understand the **commercial reasons growth is happening**:

- new stores
- new SKUs
- promotions
- price changes
- distribution changes
- retailer expansion
- supply constraints
- cannibalization

and forecast each of those effects explicitly.

That makes the system much more useful than simply improving a generic time-series forecast.

It also creates the foundation for a broader decision-intelligence capability where Aevah can answer both:

> **"What will happen?"**

and:

> **"What happens if we add this SKU, distribution, promotion, or price change?"**

---

# Recommended Aevah implementation

The practical architecture should become:

```text
                     DATA SOURCES
        ┌──────────────┼───────────────┐
      SPINS         IRI/Circana     Retail POS
        │               │               │
        └───────────────┼───────────────┘
                        ↓
              CANONICAL DEMAND LAYER
                        ↓
              ┌─────────────────────┐
              │ Historical Signals  │
              │ + Future Plans      │
              │ + Event Ledger      │
              └──────────┬──────────┘
                         ↓
                BASE DEMAND MODEL
                         +
                EVENT RESPONSE MODEL
                         ↓
              CANNIBALIZATION MODEL
                         ↓
                SUPPLY CONSTRAINTS
                         ↓
                  TOTAL FORECAST
                         ↓
                 ACTUAL OUTCOME
                         ↓
              LEARN EVENT RESPONSE
                         ↓
               IMPROVE NEXT FORECAST
```

The result is a forecasting system that doesn't merely learn **historical demand**. It learns **how this particular CPG business responds to the decisions it makes**.
