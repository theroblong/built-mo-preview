# External Forecast Accuracy Sources for CPG and Retail Demand Planning

Prepared: July 2, 2026  
Audience: BUILT CFO, VP Finance, FP&A, and report authors  
Purpose: document external support for a defensible CPG/retail forecast accuracy benchmark and provide language that can be used in finance-facing materials.

## Executive Read

There is no single universal "CPG industry standard" forecast accuracy number. Forecast accuracy depends heavily on the level of detail being forecast:

- Total company, category, or monthly forecasts are naturally easier.
- SKU-retailer, SKU-store, or weekly forecasts are harder.
- Promotions, price changes, new distribution, new SKUs, intermittent demand, and cannibalization make the problem harder still.

For BUILT's use case, the most defensible external position is:

> External retail and CPG benchmarks show that SKU-store and SKU-retailer forecasting error varies widely by granularity, promotion intensity, and demand intermittency. For finance planning, +/-35% is best described as a conservative manual/spreadsheet benchmark, not as a universal industry standard.

That framing lets us keep the 167% precision improvement narrative while avoiding an overclaim.

## Recommended Benchmark Framing

Use this language in executive materials:

> The source reports use +/-35% as a conservative manual/spreadsheet planning benchmark for CPG demand forecasting at SKU-retailer level. External retail and CPG sources support the broader point: granular forecasts are materially harder when demand is intermittent, promotion-driven, and affected by price, distribution, and assortment changes.

Use this for the headline comparison:

> Mo improved precision by 167% by moving from a conservative +/-35% manual benchmark to +/-13.1% across BUILT's data. In the strongest forecasts, Mo reached +/-4.5%, a 678% precision increase versus that same benchmark.

Avoid this wording:

> The industry standard forecast accuracy is 35%.

Why: external sources support a benchmark range and the difficulty of the use case, but not one universal CPG standard.

## Source Map

| Source | Why It Matters | What It Supports | Use in Our Narrative |
| --- | --- | --- | --- |
| M5 Accuracy Competition, International Journal of Forecasting | Public benchmark for hierarchical Walmart retail sales forecasting | Forecasting 42,840 Walmart unit-sales series, including 30,490 lowest-level forecasts | External proof that SKU/store retail forecasting is a known hard benchmark problem |
| M5 Methods GitHub Repository | Public benchmark data, scores, methods, and benchmark files | Includes benchmark scores, winning methods, competitor guide, and source data references | Backup source for reproducible benchmark context |
| M5 Representativeness Study | Tests whether M5-style retail data generalizes beyond Walmart | Compares M5 with Corporacion Favorita grocery and a Greek supermarket chain; notes M5 winners improved more than 20% over top benchmarks | Supports using retail grocery benchmark evidence for CPG planning discussions |
| IRI / ATLAS CPG Sales Forecasting Paper | Closest academic source to CPG SKU/store forecasting | Uses 165M weekly transactions, 1,500+ grocery stores, 15,560 products, and eight CPG categories | Supports relevance to CPG, grocery, weekly sales, product-store forecasting, and competitive demand dynamics |
| Trade Promotion Forecasting / Aberdeen Trail | Directly relevant to promo, price, and lift planning | Secondary summaries cite best-in-class forecast accuracy around 72% and laggards around 42% in trade-promotion contexts | Directional support for a wide error range in promo-heavy CPG forecasting; use with caveat until the original report is obtained |
| Hyndman & Koehler, Forecast Accuracy Measures | Methodology authority | Explains that common accuracy measures can be unreliable and proposes scaled measures for comparing across time series | Supports careful wording around MAPE, wMAPE, confidence intervals, and intermittent demand |

## External Source Details

### 1. M5 Accuracy Competition

Source: https://www.sciencedirect.com/science/article/pii/S0169207021001874  
DOI: https://doi.org/10.1016/j.ijforecast.2021.11.013  
Title: "M5 accuracy competition: Results, findings, and conclusions"  
Authors: Spyros Makridakis, Evangelos Spiliotis, Vassilios Assimakopoulos  
Journal: International Journal of Forecasting, Volume 38, Issue 4, October-December 2022, Pages 1346-1364

Key points:

- The competition focused on hierarchical Walmart unit sales forecasting.
- It included 42,840 time series.
- It required 30,490 point forecasts at the lowest cross-sectional aggregation level.
- The topic is directly retail-sales forecasting, not generic statistical forecasting.

How we use it:

- This is the strongest public benchmark for retail SKU/store-style forecasting.
- It supports the claim that granular retail demand forecasting is a recognized benchmark problem.
- It does not directly provide a universal CPG MAPE standard.

Finance-facing wording:

> Public retail forecasting benchmarks such as M5 show that SKU-store demand forecasting is a recognized hard problem, especially when forecasts must reconcile granular item/store behavior with higher-level planning needs.

### 2. M5 Methods Repository

Source: https://github.com/Mcompetitions/M5-methods

Key points:

- The repository includes code of winning methods.
- It includes "Scores and Ranks.xlsx" for top submissions and benchmarks.
- It includes the competitor guide, benchmark submissions, and validation/evaluation materials.

How we use it:

- This is useful as the reproducibility source behind the M5 benchmark.
- It can support a footnote or appendix if someone asks where benchmark scores and methods live.

Finance-facing wording:

> The M5 benchmark is not just an academic paper; the competition data, benchmark methods, and scores are publicly available for review.

### 3. M5 Representativeness Study

Source: https://arxiv.org/abs/2103.02941  
Title: "Exploring the representativeness of the M5 competition data"  
Authors: Evangelos Theodorou, Shengjie Wang, Yanfei Kang, Evangelos Spiliotis, Spyros Makridakis, Vassilios Assimakopoulos

Key points:

- The paper evaluates whether the Walmart M5 data is representative of other retail firms.
- It compares M5 with Corporacion Favorita grocery and a Greek supermarket chain.
- It says the M5 winners improved more than 20% over the top-performing benchmarks according to the competition measures.
- It notes that retail sales series can be intermittent, lumpy, smooth, or erratic.
- It notes that M5 included special days, holidays, selling prices, and promotion activity.

How we use it:

- This source bridges from Walmart to grocery and CPG-style planning.
- It supports the idea that external benchmarks are relevant but context-dependent.
- It supports our caution that accuracy varies by series type and planning level.

Finance-facing wording:

> Retail benchmark research shows that the relevant comparison is not one universal accuracy number; it is performance at the same planning level, with similar price, promotion, and intermittency dynamics.

### 4. IRI / ATLAS CPG Sales Forecasting Paper

Source: https://arxiv.org/abs/2011.03452  
DOI: https://doi.org/10.48550/arXiv.2011.03452  
Title: "Improving Sales Forecasting Accuracy: A Tensor Factorization Approach with Demand Awareness"  
Authors: Xuan Bi, Gediminas Adomavicius, William Li, Annie Qu

Key points:

- The paper focuses on forecasting sales for each product in each store.
- It uses IRI data: 164.9M weekly transaction records.
- It covers more than 1,500 grocery stores and 15,560 products.
- It includes eight CPG categories: razor blades, coffee, deodorant, diapers, frozen pizza, milk, photography, and toothpaste.
- It explicitly discusses local consumer demand dynamics and competition across stores/products.

How we use it:

- This is the closest external academic fit to BUILT's use case.
- It supports the value of forecasting at product/store level.
- It supports the relevance of demand dynamics, competitive pressure, assortment effects, and large-scale CPG transaction data.

Finance-facing wording:

> CPG forecasting research using IRI weekly transaction data shows that product-store forecasting is materially affected by local demand dynamics and competitive product behavior. That is the same class of planning problem BUILT faces when forecasting by SKU, retailer, price, promotion, and distribution context.

### 5. Trade Promotion Forecasting and Aberdeen Benchmark Trail

Source trail: https://en.wikipedia.org/wiki/Trade_promotion_forecasting  
Underlying cited sources include Aberdeen Group and Consumer Goods Technology reports, including "Plan, Spend and Prosper: Making the Most of Trade Promotion" and "Trade Promotion Management: The Haves and Have-Nots."

Key points from secondary summaries:

- Trade promotion ROI depends on identifying baseline demand and uplift.
- Bottom-up forecasting at SKU-account/POS level is difficult because it requires product attributes, history, store specifics, and promotion attributes.
- Secondary summaries cite best-in-class forecasting companies with average forecast accuracy around 72%.
- The same summaries cite laggard forecasting companies with average accuracy around 42%.
- That implies rough error rates of 28% to 58% in promotion-heavy contexts, depending on how accuracy is defined.
- Secondary summaries also cite high Excel usage in trade promotion forecasting.

How we use it:

- This is highly relevant to BUILT's price, promotion, and trade-spend story.
- It is useful directional support for a wide benchmark range.
- It should not be used as the sole support for a formal "industry standard" without retrieving the original Aberdeen report.

Finance-facing wording:

> External trade-promotion sources show that promo-heavy CPG forecasting can carry materially wider error ranges than aggregate demand planning, especially when teams must separate base demand from promotion lift.

Safe caveat:

> The Aberdeen figures are useful directional benchmarks, but they should be cited as secondary-source support unless the original Aberdeen report is obtained.

### 6. Hyndman & Koehler on Forecast Accuracy Measures

Source: https://robjhyndman.com/publications/another-look-at-measures-of-forecast-accuracy/  
Title: "Another look at measures of forecast accuracy"  
Authors: Rob J. Hyndman and Anne B. Koehler  
Journal: International Journal of Forecasting 22(4), 679-688, 2006

Key points:

- Common forecast accuracy measures can be unreliable in common situations.
- The authors propose mean absolute scaled error as a standard for comparing forecast accuracy across multiple time series.
- This matters for CPG because SKU/store series often include low volume, zeros, intermittent demand, and large variation in scale.

How we use it:

- This supports careful wording around MAPE, wMAPE, confidence intervals, and comparisons across many SKU-retailer series.
- It helps explain why a single percentage benchmark can mislead if the planning level is not defined.

Finance-facing wording:

> Forecast accuracy percentages need to be interpreted at the same planning level and with the same metric. Granular SKU-retailer series are not comparable to aggregate company-level forecasts unless the metric and aggregation level are defined.

## Suggested Benchmark Position for BUILT Reports

The strongest, cleanest statement:

> For this report, +/-35% is used as a conservative manual/spreadsheet benchmark for granular CPG demand planning. External retail and CPG sources support that granular SKU-store and SKU-retailer forecasts are substantially harder than aggregate forecasts, particularly when promotion, price, distribution, new SKUs, and intermittent demand are present.

The precision comparison:

| Benchmark | Planning Range | Precision Index | Plain-English Meaning |
| --- | ---: | ---: | --- |
| Manual/spreadsheet benchmark | +/-35.0% | 1.0x | Conservative planning comparison for granular CPG forecasts |
| Mo across BUILT data | +/-13.1% | 2.7x | 167% more precise than the benchmark |
| Mo strongest forecasts | +/-4.5% | 7.8x | 678% more precise than the benchmark |

Precision math:

- 35.0 / 13.1 = 2.67x as precise.
- 2.67x minus 1.00x = 167% precision increase.
- 35.0 / 4.5 = 7.78x as precise.
- 7.78x minus 1.00x = 678% precision increase.

## Claims We Can Support

- Granular retail and CPG forecasting is a hard, well-documented problem.
- Public retail benchmarks exist, especially M5 for Walmart hierarchical unit sales.
- CPG product-store forecasting has been studied using IRI weekly transaction data at large scale.
- Forecast accuracy depends heavily on aggregation level, horizon, intermittency, promotion, price, and distribution dynamics.
- A +/-35% manual/spreadsheet benchmark is reasonable as a conservative planning benchmark, if described as such.
- Mo's +/-13.1% and +/-4.5% figures are stronger when compared to a defined benchmark, not an undefined "industry standard."

## Claims to Avoid

- "The CPG industry standard is 35%."
- "All CPG forecasts are usually +/-35%."
- "Mo beats the industry standard by X" without defining the benchmark and planning level.
- "Cannibalization accuracy" as a percentage unless a true validation metric exists.
- MAPE comparisons across series unless the metric and aggregation level are clearly defined.

## Recommended Footnote Language

> Benchmark note: +/-35% is used as a conservative manual/spreadsheet benchmark for granular CPG demand planning, not as a universal industry standard. External retail and CPG forecasting research shows that SKU-store and SKU-retailer forecasts vary widely by aggregation level, forecast horizon, promotion intensity, price changes, distribution dynamics, and demand intermittency. Relevant external references include the M5 Walmart retail forecasting benchmark, M5 representativeness work comparing Walmart with grocery retailers, IRI-based CPG product-store forecasting research, trade-promotion forecasting literature, and Hyndman & Koehler's work on forecast accuracy measures.

## Source Links

- M5 Accuracy Competition: https://www.sciencedirect.com/science/article/pii/S0169207021001874
- M5 DOI: https://doi.org/10.1016/j.ijforecast.2021.11.013
- M5 Methods Repository: https://github.com/Mcompetitions/M5-methods
- M5 Representativeness Study: https://arxiv.org/abs/2103.02941
- IRI / ATLAS CPG Forecasting Paper: https://arxiv.org/abs/2011.03452
- IRI / ATLAS DOI: https://doi.org/10.48550/arXiv.2011.03452
- Hyndman & Koehler Forecast Accuracy Measures: https://robjhyndman.com/publications/another-look-at-measures-of-forecast-accuracy/
- Trade Promotion Forecasting Source Trail: https://en.wikipedia.org/wiki/Trade_promotion_forecasting

