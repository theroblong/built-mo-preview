# Aevah Platform — Internal Marketing Notes
**For:** Rob, Sherry, and marketing collaborators (including AI agents)
**Purpose:** Working reference for messaging, positioning, and value articulation
**Last updated:** 2026-07-08

---

## What We Are Selling

Aevah is a **CPG demand intelligence platform** that turns existing retail scanner data (SPINS, NielsenIQ) into forward-looking decisions — with models that explain themselves in plain English and can be interrogated by anyone on the team, not just data scientists.

The client-facing application built on Aevah is called **Mo**. Mo is not a chatbot bolted onto a dashboard. It is an AI analyst that has read every line of your data and can answer the question behind the question.

---

## Primary Buyer Profiles and What They Care About

### CFO / VP Finance
- "Will this forecast hold up when I present it to the board?"
- "How much of our volume is promo-dependent vs. organic demand?"
- "If we raise price 5% at Walmart, what happens to revenue?"
- **Pain:** Existing forecasts from Excel or legacy BI are black boxes. When actuals miss, no one can explain why — so no one learns.
- **What they need:** Forecast accuracy numbers they can defend, scenario modeling they can run themselves, audit trail for every recommendation.

### CIO / CTO
- "Can this run on our existing data infrastructure?"
- "Is our SPINS feed going into a third-party model we don't control?"
- "Can we swap the LLM provider if OpenAI pricing changes or if legal has concerns?"
- **Pain:** AI tools that require wholesale data migration, vendor lock-in on LLM providers, or "trust us" black boxes that can't be audited.
- **What they need:** Configurable provider stack, data stays in their environment, explainable models with audit logs.

### CEO / General Manager
- "How do I know our pricing is right vs. competitors?"
- "Are we cannibalizing ourselves with new SKU launches?"
- "What should we tell the retail buyers about our sell-through trajectory?"
- **Pain:** Decision lag — by the time the data team produces an analysis, the window has closed.
- **What they need:** Fast answers to strategic questions, confidence that the recommendation is grounded in their actual data not generic benchmarks.

### VP Sales / Account Management (Champion)
- "I'm walking into a Kroger QBR next week. What story does the data tell?"
- "Which of our SKUs is at risk and why?"
- **Pain:** Hours spent pulling SPINS reports, building Excel pivot tables, writing narrative by hand.
- **What they need:** Pull up a screen, ask a question, get a rehearsal-ready answer with supporting numbers.

### VP Finance / FP&A (Champion)
- "Our demand planning team runs Excel-based forecasts. We know they're not great but they're auditable."
- **Pain:** When the forecast misses, there's no signal about which driver caused it — price? distribution loss? competitive launch?
- **What they need:** Decomposed forecasts (base demand vs. promo lift vs. competitive pressure) with confidence intervals they can explain to a CFO.

---

## Core Value Propositions

### 1. Explainability — The Opposite of a Black Box

Most ML forecasting tools output a number. Aevah outputs a number **and an explanation**.

- Every forecast is decomposable: base demand (what you'd sell without any promotion), promo lift (SPINS-measured incremental above baseline), competitive drag (cannibalization from new SKU launches or competitor price moves).
- SHAP waterfall charts show exactly which signals drove each prediction — in plain English alongside the math.
- The causal price elasticity model (DoWhy, backdoor adjustment) doesn't just fit a curve; it controls for confounders (distribution changes, seasonality, launch phase) so the number is defensible: "We estimated price elasticity at ε = −0.35 controlling for shelf distribution and competitive activity."
- An auditor, a CFO, or a retail buyer can follow the logic.

**Talking point:** "When your demand planner leaves the company, the knowledge leaves with them. With Aevah, the logic is in the model — visible, auditable, and transferable."

### 2. Natural Language Data Interrogation — Anyone Can Ask

Mo Chat is the conversational interface on top of all of this data. It is grounded in live SPINS data, not static training data.

- An account manager can ask: *"Why is Walmart trending down for our 4-pack vs. last quarter?"* and get a specific answer citing distribution loss, a competitor price cut, or promo gap — with the supporting numbers.
- A CFO can ask: *"If we ran a 10% TPR at Kroger next quarter, what's the incremental revenue projection?"* and get a scenario with confidence bands.
- Mo cites its sources. It doesn't hallucinate. When it doesn't know something (because the data isn't there), it says so.

**Talking point:** "You already pay for SPINS data. Aevah makes it work for everyone on the team, not just the three people who know how to pull a report."

### 3. Domain-Intelligent Signals — CPG-Specific, Not Generic ML

The difference between a general forecasting tool and Aevah is the signals baked into the models:

| Signal | Why it matters in CPG |
|---|---|
| **Price elasticity by retailer** | Kroger shoppers respond differently to price than Walmart shoppers. One ε doesn't fit all. |
| **Cannibalization rate** | A new SKU launch may be stealing from your own portfolio. Seeing gross launch velocity without netting cannibalization is misleading. |
| **Promo lift decomposition** | SPINS measures incremental units above baseline — so you can separate "we sold more because of the TPR" from "everyday demand is growing." |
| **TDP change (distribution velocity)** | Distribution gain is the leading indicator that precedes sales. We track week-over-week distribution expansion as a model feature. |
| **SPINS MRM baseline** | SPINS' own Market Response Model smooths the baseline curve so seasonal peaks and promo weeks don't corrupt the no-promotion demand estimate. |
| **Temporal AR lags** | The model knows last week's sales and what happened a year ago (YAGO), so it captures momentum and seasonality without overfitting. |

A generic tool trained on revenue data misses all of this. Aevah is trained on data structured around how CPG actually works.

### 4. Forecast Accuracy — Quantified Value

From the BUILT production pipeline (104 SKUs × 78 retailers, 2.5+ years of weekly SPINS data):

- **Base units model (SPINS MRM baseline):** wMAPE = **4.3%** (MO_53, 28-feature LightGBM champion)
- **Comparison baseline (YAGO-only, no ML):** wMAPE ≈ 30–118% depending on SKU maturity
- **The gap:** 20+ percentage points of improvement attributable to domain-specific signals (cannibalization, price elasticity, TDP momentum)

**ROI framing:** For a CPG brand doing $50M in retail revenue, a 1 percentage point improvement in forecast accuracy avoids roughly $500K in inventory carrying cost, lost sales, and markdown exposure annually. A 20pp improvement = $10M in value — from data you already have.

*Note: Use these directional numbers carefully. Actual ROI depends on the client's revenue base, inventory turns, and planning cycle. Always validate with client's own finance team rather than leading with a specific dollar figure.*

### 5. Security and Configurability — Enterprise-Ready

- **Data sovereignty:** SPINS data and client sales data live in the client's Druid cluster. Nothing is sent to a third-party LLM training pipeline.
- **Configurable LLM provider:** Mo can run on Anthropic Claude (default), OpenAI GPT-4o, or any OpenAI-compatible endpoint (Azure, Mistral, Llama 4, MS Copilot). One environment variable switch. No re-engineering required.
- **Explainable audit trail:** Every model prediction is traceable to a specific feature set, training run, and data version. Appropriate for finance teams with SOX or audit requirements.
- **No vendor lock-in:** The platform is data-source agnostic. SPINS today, NielsenIQ or IRI tomorrow.

---

## Key Differentiators vs. Alternatives

### vs. Excel / Manual Planning
- Speed: hours → seconds for a scenario
- Accuracy: 4–30% wMAPE vs. 30–100%+ from simple extrapolation
- Explainability: decomposed drivers vs. "the analyst's judgment"
- Knowledge retention: model persists when the analyst leaves

### vs. Generic BI (Tableau, Power BI, Looker)
- BI shows what happened. Aevah predicts what will happen and explains why.
- BI requires a data analyst to build each view. Mo lets non-technical users ask questions in English.
- BI doesn't have domain models. Aevah's cannibalization and elasticity models are CPG-specific.

### vs. Other ML Forecasting Platforms (e.g., o9, Anaplan, Palantir)
- Those platforms are general-purpose supply chain tools requiring multi-year implementations.
- Aevah is CPG-data-native — built around SPINS' specific field definitions, retail account structures, and promo mechanics.
- Mo Chat is the differentiator: no other platform lets you interrogate your demand model in natural language with cited, grounded answers.

### vs. "We'll have our data science team build it"
- Time to value: 12–18 months to replicate what's already production-ready on Aevah.
- Domain knowledge: CPG-specific features (promo lift decomposition, SPINS MRM integration, retailer-level elasticity) take years to get right.
- Maintenance: Aevah handles model refresh on each SPINS data delivery. Internal builds require ongoing engineering headcount.

---

## Use Cases — Buyer-Ready Scenarios

### FP&A / Finance
- **Quarterly demand plan:** 13-week quantile forecast (q10/q50/q90) by SKU × retailer, updated on each SPINS delivery. Replaces the Excel extrapolation in the quarterly planning cycle.
- **Trade promotion ROI:** Compare pre-promo baseline to post-promo actuals. Mo attributes the lift to SPINS-measured incremental units. "The Kroger Q4 TPR drove 23K incremental units above baseline."
- **Scenario planning:** "What if we raise shelf price by $0.50 at Walmart?" Price elasticity model gives the demand response with a confidence band.
- **New SKU launch risk:** Cannibalization model predicts which existing SKUs will lose volume to a new launch, and by how much.

### Account Management / Sales
- **Retail QBR preparation:** Pull SKU Summary view for any retailer — velocity vs. category, launch trajectory, competitive price gap, promo calendar. Narrative-ready in 30 seconds.
- **Price gap alerts:** Competitive Price Gap events surface when a competitor has undercut by more than a threshold. Mo explains why this matters and what the expected demand response is.
- **Launch Monitor:** Track week-by-week sell-through for new SKUs. Flag when trajectory is ahead of or behind plan. Know before the buyer calls.

### Marketing / Brand
- **Elasticity by channel:** Is the brand more price-sensitive in Natural/Specialty than in Mass? Retailer-level elasticity shows where price promotions move the needle vs. where they don't.
- **Promo dependence:** What % of total scan volume is promo-lifted vs. everyday demand? A growing promo gap signals an unhealthy dependence on trade spend to maintain velocity.
- **Cannibalization map:** Which flavors or pack sizes are competing with each other? Where is own-brand cannibalization above acceptable thresholds?

---

## Objections and Responses

**"We already pay for SPINS. Why do we need another tool?"**
> SPINS gives you the data. Aevah makes it predictive and conversational. It's like having the data plus an analyst who has read every row of it and can answer questions in real time.

**"Our data science team can build models."**
> They probably can — but it will take 12–18 months to replicate what's running in production here. And CPG-specific domain knowledge (SPINS field definitions, retailer-level elasticity, promo decomposition) is hard-won. You'd be starting from scratch on problems we've already solved.

**"How do we know the AI isn't making things up?"**
> Mo only answers from grounded data — it cites the specific SPINS table, retailer, and time range for every claim. When the data doesn't support an answer, Mo says so rather than fabricating a number. The models are transparent: SHAP values show which signals drove each prediction. A CFO can follow the logic.

**"What happens to our data?"**
> Your SPINS data lives in your Druid cluster. It doesn't go into any model training pipeline. The LLM only receives query results — not raw data — and the LLM provider is configurable if your legal team requires a specific vendor.

**"Our forecast is good enough."**
> "Good enough" has a cost. At a $50M revenue base, a 20pp accuracy improvement is worth roughly $10M annually in avoided inventory risk, lost sales, and markdown exposure. The question isn't whether the current forecast is acceptable — it's what better is worth.

---

## Tone and Framing Guidance

- **Do:** Say "complement and supercharge your existing process." Not "replace."
- **Do:** Lead with the problem (decision lag, black-box models, analyst-hours wasted) before the solution.
- **Do:** Use SPINS-specific language. CFO and CIO audiences in CPG know what a TPR is, what a TDP means, what MULO represents. Don't talk down.
- **Do:** Ground every claim in a real number or a real mechanism. "We estimated ε = −0.35 using DoWhy backdoor adjustment controlling for TDP, weeks since launch, and competitive donor activity" is more credible than "our AI models price sensitivity."
- **Don't:** Say "our AI is better." Say "here is a specific question your team asks today, and here is exactly how fast and how accurately we answer it."
- **Don't:** Compare unfavorably to BUILT's existing process or any client's current tools. Frame as additive.
- **Don't:** Overstate certainty. SPINS baseline methodology is SPINS' proprietary model — it can differ from NielsenIQ by 30+ pp for the same event. Always say "SPINS-defined baseline" not "true non-promo demand."
- **Don't:** Lead with model names (LightGBM, DoWhy, SHAP) in executive conversations. Lead with outcomes. Model names belong in technical appendices.

---

## Numbers Available for Use

These are real production numbers from the BUILT deployment. Use carefully — always note these are from a specific client's data set; actual results vary.

| Metric | Value | Context |
|---|---|---|
| Base units forecast accuracy | 4.3% wMAPE | 104 SKUs × 78 retailers, 13-week horizon, LightGBM 28-feature model |
| Total units forecast accuracy | 9.47% wMAPE | Includes promo lift component — inherently more variable |
| Improvement over YAGO-only baseline | 20–25 pp | Varies by SKU maturity and retailer data quality |
| Portfolio price elasticity | ε = −0.35 | Log-log OLS, DoWhy backdoor adjustment, 78 retailers |
| Most price-sensitive retailer | ε = −2.48 | Food City Market — 7× more elastic than portfolio avg |
| Portfolio promo share | 25.6% | Share of total scan volume above SPINS MRM baseline |
| Price events validated directionally | 63% | MO_47: 30,876 events, clean price moves only |
| SPINS data scale | 53M+ rows | built_filtered_weekly, 145 weeks, 104 UPCs |
| Retailers covered | 78 | Includes major chains, regional grocery, specialty, mass |
| SKUs modeled | 104 | Full BUILT portfolio, all channels |
| LLM providers supported | 2 live | Anthropic Claude (default), OpenAI GPT-4o; others roadmapped |

---

## What Is Still Being Built (Honest Gaps)

Being accurate here helps credibility with technical buyers:

- **Temporal holdout backtesting:** Current model uses a single 13-week holdout. Rolling cross-validation by account/time is on the roadmap (MO_59+).
- **YAGO data depth:** 2025 SKUs lack 2+ years of history for seasonal pattern learning. Results improve as the dataset matures.
- **Real-time promo calendar integration:** Current promo signals come from SPINS-reported data (1–3 week lag). Direct integration with a client's trade promotion management system would improve forecast accuracy further.
- **Multi-retailer demand correlation:** Currently each retailer series is modeled independently. A portfolio-level demand model capturing cross-retailer spillover (e.g., Walmart promotion cannibalizing Kroger volume) is a Phase 3 roadmap item.

---

*This document is internal only. Numbers, model names, and methodology details should not appear verbatim in client-facing materials without review. Sherry: feel free to pull angles from here for the narrative — the "objections" section and "buyer profiles" are probably the most immediately useful for copy work.*
