# Aevah Forecasting: Multi-Horizon Seasonality and Structural Growth

## Overview

Aevah needs to support forecasting for high-growth CPG businesses where demand is influenced by annual seasonality, short-term sales velocity, structural growth, retailer and distributor expansion, promotions, product launches, and external market events.

Current ML models, including XGBoost and linear regression, often focus on 4-week or 12-week forecasting windows. These models may not sufficiently account for annual seasonal patterns or growth events that are not represented in recent historical observations.

The proposed enhancement is to introduce a **Long-Horizon Seasonality & Trend Layer** as part of Aevah's broader forecasting architecture.

The objective is to produce forecasts that incorporate historical seasonal patterns, recent demand behavior, structural business growth, and forward-looking external signals.

## 1. Separate Forecast Horizon from Historical Lookback

Aevah must distinguish between:

- **Historical lookback:** The amount of historical information available to train models and construct prediction features.
- **Forecast horizon:** How far into the future the model is predicting.

A model predicting the next 4 or 12 weeks should still be able to learn from multiple years of historical data.

With approximately three years of Circana or SPINS receipt data, Aevah should generate features representing different historical periods.

### Recommended Historical Features

| Feature | Purpose |
|---|---|
| Lag 1, 4, 8, 12 weeks | Recent sales momentum |
| Lag 26 weeks | Semiannual comparison |
| Lag 52 weeks | Year-over-year patterns |
| Lag 104 weeks | Two-year historical comparison |
| Rolling 4/12/26-week averages | Short- and medium-term demand |
| Week of year | Recurring annual seasonality |
| Holiday and retail calendar features | Seasonal retail events |
| Seasonal Fourier terms | Smooth annual patterns |
| Category seasonal performance | Demand trends across comparable products |
| Distribution-adjusted velocity | Separate increased availability from increased consumer demand |

Features must be constructed without incorporating information that would not have been available at the time of the forecast.

## 2. Support Multiple Forecasting Time Scales

Aevah should support different forecasting horizons within a unified forecasting engine.

| Time Scale | Key Factors | Modeling Approach |
|---|---|---|
| Short-term: 1–4 weeks | Recent velocity, promotions, inventory, immediate external events | XGBoost / LightGBM and short-term lag features |
| Medium-term: 5–13 weeks | Distribution ramp, promotions, changing growth rates | ML ensemble and event-response models |
| Long-term: 13–52+ weeks | Annual seasonality, category cycles, structural growth | Seasonal models and longer-term trend estimation |

These forecasting approaches should contribute to a consistent forecast rather than create separate, conflicting predictions.

## 3. Separate Seasonality from Structural Growth

Rapidly growing companies can experience significant year-over-year sales changes caused by factors unrelated to seasonality.

For example, a brand experiencing 80% annual growth may have expanded distribution significantly during the same period.

Simply comparing January sales against the previous January could incorrectly classify distribution growth as a seasonal effect.

Aevah should separate the principal drivers of observed sales:

**Observed Sales = Underlying Demand Trend × Seasonal Effects × Business Event Effects**

This is a conceptual decomposition. The implementation may use additive, multiplicative, or other formulations depending on the data and validated model performance.

### Seasonal Factors

- Annual demand cycles
- Seasonal category consumption
- Holiday-related demand
- Retail merchandising calendars
- Geographic seasonal variations
- Product-specific seasonality

### Structural Growth Factors

- Retailer and distributor expansion
- Increases in weighted distribution
- New store openings
- New geographic market entry
- New product introductions
- Brand adoption and maturity
- Changes in sales velocity

### External Event Factors

- Influencer marketing campaigns
- Social media demand surges
- Retail promotions
- Competitor activity
- Supply disruptions
- Inventory constraints
- Unplanned demand shocks

Aevah must avoid double-counting when multiple models incorporate the same event or growth signal.

## 4. Introduce a Seasonal Intelligence Asset

Create a reusable, versioned **Aevah Seasonal Intelligence Asset** that exists independently of individual trained forecasting models.

This asset should maintain seasonal profiles at multiple business levels.

### Supported Levels

- Product category
- Brand
- Retailer
- Distributor or channel
- Geography
- Product family
- Individual SKU, when sufficient data exists

### Information Maintained

- Historical seasonal patterns
- Seasonal demand indices
- Holiday-related impacts
- Relevant category benchmarks
- Confidence or uncertainty estimates
- Source data and provenance
- Version history
- Effective dates
- Historical forecasting performance

### New Product Support

When a new SKU lacks sufficient sales history, Aevah should be capable of using relevant seasonal patterns from its product family, brand, or category.

As SKU-specific observations accumulate, the system should progressively incorporate its own seasonal behavior.

Customer proprietary information must remain isolated within the customer's environment. Shared seasonal intelligence across customers must not rely on pooling their private data without authorization.

## 5. Modeling Approaches to Evaluate

Aevah should evaluate multiple approaches rather than prescribe one algorithm for every customer or product.

Candidate methods include:

- XGBoost or LightGBM with expanded historical and seasonal features
- Fourier-based annual seasonality
- Dynamic harmonic regression
- Seasonal decomposition such as STL
- Hierarchical seasonal models
- Global models trained across related SKU-retailer time series
- Specialized models where sufficient observations exist
- Explicit growth and event-response models

Annual seasonal effects may be represented directly within an ML model or as a separately estimated component.

Backtesting should determine which combination performs best.

## 6. Unified Forecasting Architecture

The proposed architecture consists of the following components.

### Historical Intelligence Foundation

Use approximately three years of Circana or SPINS data, organized by SKU, retailer, geography, and time period.

### Annual Seasonality Layer

Identify recurring yearly patterns, holidays, category cycles, and relevant retail calendars.

### Core ML Forecasting Layer

Model recent demand, sales velocity, promotions, pricing, and short-term momentum.

### Structural Growth Layer

Model distribution expansion, geographic penetration, product maturity, and changing demand trajectories.

### External Event Intelligence Layer

Incorporate planned and observed business events, including influencer campaigns, product launches, and promotional activity.

### Forecast Reconciliation Layer

Combine the outputs of the forecasting components, prevent duplicated event impacts, incorporate governed expert adjustments, and generate consistent forecasts.

### Forecast Output

Provide:

- Forecasts across 1–52+ week horizons
- Expected unit sales and revenue
- SKU, retailer, channel, and geographic breakdowns
- Forecast confidence or prediction intervals
- Explanations of major demand drivers
- Scenario-based forecast comparisons

## 7. Validation and Backtesting

Before adopting additional modeling complexity, Aevah should compare the enhanced forecasting approach against existing production models.

Recommended initial experiments:

1. Current 4-week and 12-week ML models.
2. Existing models with 52-week and 104-week lag features.
3. Existing models with annual seasonal Fourier features.
4. Existing models with hierarchical seasonal profiles.
5. Hybrid forecasts incorporating seasonal, structural growth, and event intelligence.

Use rolling historical backtests at multiple forecast horizons.

Evaluate forecast accuracy, systematic bias, and uncertainty calibration by retailer, product category, SKU, and horizon.

All backtesting must respect historical information availability to prevent data leakage.

The objective is to determine which enhancements deliver measurable improvements over the current forecasting baseline.

## 8. Continuous Learning and Governance

Seasonal intelligence should evolve independently of individual model retraining cycles.

As new sales observations arrive, Aevah should:

- Compare expected seasonal demand against actual results.
- Identify persistent changes in seasonal patterns.
- Distinguish seasonal changes from structural business growth.
- Recalibrate seasonal profiles when supported by evidence.
- Evaluate the impact of external business signals.
- Retain historical versions and evaluation results.
- Update forecasting models according to performance and drift.

This allows underlying models to evolve while preserving accumulated seasonal knowledge and business context.

## 9. Core Product Principle

**Aevah should use long historical windows to understand recurring demand patterns, short windows to react to recent changes, and forward-looking business signals to anticipate non-linear growth.**

The forecasting horizon must not limit the historical patterns that a model can learn.

Aevah should progressively build reusable seasonal and business intelligence assets that improve forecasts while maintaining independence from the lifecycle of individual ML models.

## 10. Initial Implementation Priority

Begin by evaluating expanded historical features against the existing XGBoost and linear regression forecasting approaches.

Specifically:

- Test annual seasonality using 52-week historical relationships.
- Evaluate Fourier-based seasonal features.
- Introduce category and product-family seasonal profiles.
- Compare results against existing 4-week and 12-week models.
- Identify improvements by customer, retailer, SKU, and forecast horizon.
- Preserve compatibility with the broader external event and structural growth forecasting architecture.

The implementation should favor measurable forecasting improvements over unnecessary model complexity.
