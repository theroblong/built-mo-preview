# Brad's Product Cannibalization Modeling Plan

If the 100-row CSV is a small sample from a 95 million row SPINS panel with at least 3 years of history, then the right approach is to treat this as a serious `UPC x geography x week` demand system problem. The work should be staged from business definition to measurement to predictive modeling to decision support.

## 1. Define the business question precisely

The first step is to lock down what "cannibalization" means for the business. Possible definitions include:

- a new SKU taking demand from existing SKUs in the same brand
- a promoted SKU pulling volume from sister items during promo periods
- assortment expansion redistributing volume across the portfolio
- cross-brand substitution within a subcategory

The exact definition determines the target variable, competitive set, validation design, and how results should be interpreted.

## 2. Build the modeling grain

The core panel should be built at:

- `UPC x Geography x Week`

From there, decide whether prediction and reporting should happen at:

- item level
- item within brand
- item within subsegment
- brand level with SKU roll-down

Weekly granularity is usually the right starting point because it captures promotions, distribution shifts, and seasonality without becoming too noisy.

## 3. Create the product hierarchy and competitive set

Cannibalization prediction depends on defining realistic substitution pools. Products should be grouped into competitive sets using attributes such as:

- brand
- pack count / size
- flavor
- nutrition bands such as protein tier
- category and subcategory metadata if available
- price tier
- geography or channel context

The goal is to avoid assuming every product competes equally with every other product.

## 4. Choose the target variable

The main target candidates are:

- `Base Units` for underlying demand net of promo effects
- `Units` for observed real-world demand

The recommended starting point is `Base Units`, followed by comparison against `Units` to understand operational impact.

## 5. Engineer the core drivers of substitution

The feature set should capture both the focal SKU and the behavior of neighboring SKUs in the same market and week.

### Own-item features

- price
- promo depth
- ACV
- TDP
- item age
- seasonality
- time trend
- weeks since launch
- base productivity

### Competitive-set features

- competitor count
- average competitor price
- minimum competitor price
- competitor promo intensity
- competitor TDP / ACV
- competitor weighted distribution
- competitor assortment breadth

### Same-brand pressure features

- number of same-brand UPCs active
- same-brand promo count
- same-brand price ladder
- overlap in flavor, size, or protein band
- new launch flags

### Market context features

- retailer or geography effects
- calendar seasonality
- holiday effects
- macro trend proxies if available
- category velocity
- category promo intensity

## 6. Measure historical cannibalization before predicting it

Before fitting a predictive model, build measurement layers that quantify what happened historically when:

- a new SKU launched
- a SKU gained distribution
- a SKU was promoted
- assortment count changed

This should include event-study style measurement and difference-in-differences style analysis where appropriate. The purpose is to establish observed transfer patterns and validate that the later predictive model is learning something meaningful.

## 7. Create candidate labels for training

Because cannibalization is often not directly labeled, define outcomes such as:

- change in focal SKU base units after competitor launch, promo, or distribution gain
- share loss within brand or segment
- residual demand decline unexplained by seasonality and own-item factors
- proportion of incremental volume on one SKU associated with declines on sibling SKUs

In practice, it is useful to create both:

- a regression target for cannibalized units
- a classification target for whether a material cannibalization event occurred

## 8. Start with interpretable baseline models

Initial model families should be strong and explainable:

- regularized regression
- gradient boosting models such as LightGBM or XGBoost
- mixed-effects or panel regression with market and time effects

These models often perform well on POS data and remain understandable to commercial stakeholders.

## 9. Move to richer panel or causal hybrids if needed

Once the baselines are stable, consider more advanced approaches if justified:

- hierarchical Bayesian demand models
- panel models with explicit cross-elasticity structure
- causal forests or uplift-style models for promo-driven substitution
- graph or embedding approaches for product similarity
- multi-task models that learn across related SKUs jointly

These should come after baselines, not before.

## 10. Design validation around time and markets

Validation should reflect how the model will actually be used. Recommended holdouts include:

- forward-chaining time splits
- holdout geographies
- holdout launch events
- holdout brands or product families when appropriate

Random row-level train/test splits should be avoided because they overstate performance in panel POS data.

## 11. Define the business outputs early

The final outputs should be decision-oriented, not just raw predictions. Examples:

- predicted cannibalized units by SKU
- donor SKUs and recipient SKU
- cannibalization rate as a percent of incremental demand
- results by market and week
- launch, pricing, and promotion scenarios

## 12. Build decision-support scenarios

After the prediction layer is stable, add scenario planning such as:

- impact of launching a new SKU in selected markets
- impact of promoting SKU A at different discount depths
- impact of expanding distribution
- impact of removing a low-velocity SKU

This turns the work into a usable planning tool for assortment and revenue management.

## 13. Operationalize and monitor

After deployment, monitor:

- prediction drift
- feature drift
- cold-start performance for new items
- changes in promo mechanics
- distribution anomalies
- geography or channel-specific degradation

Cannibalization patterns change as assortments, shoppers, and merchandising behavior change.

## Recommended first workstream

The recommended first implementation sequence is:

1. confirm the business definition of cannibalization
2. define the product hierarchy and competitive set logic
3. build the weekly `UPC x Geography x Week` panel
4. create launch, promo, price, and distribution event features
5. run historical measurement analyses to quantify observed cannibalization
6. train interpretable baseline models for cannibalized unit prediction
7. evaluate on future weeks and unseen markets
8. package results into SKU-level planning outputs

## Major risks

The main risks are:

- poorly defined competitive sets
- leakage from derived POS variables
- confusing correlation with true substitution
- mixing launch effects with distribution effects
- sparse history for new or niche SKUs

Managing those risks carefully will matter as much as model selection.
