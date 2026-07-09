# Aevah Platform — Internal Marketing Notes
**For:** Rob, Sherry, and marketing collaborators (including AI agents)
**Purpose:** Working reference for messaging, positioning, and value articulation
**Last updated:** 2026-07-08

---

## What We Are Selling

Aevah is a **CPG demand intelligence platform** that turns existing retail scanner data (SPINS, NielsenIQ) into forward-looking decisions — with models that explain themselves in plain English and can be interrogated by anyone on the team, not just data scientists.

The client-facing application built on Aevah is called **Mo**. Mo's conversational interface — **Aevah AI Assist** (also called AI Avatars) — is not a chatbot bolted onto a dashboard. It is an AI analyst that has read every line of your data and can answer the question behind the question, using your business's own language and context.

### Who We Serve — Growth-Stage and Established Brands

Aevah is built for both ends of the CPG maturity curve, and we have active clients in both categories:

**Dynamically growing / expanding brands** (e.g., newer brands in active retail rollout):
- Distribution ramp is the dominant variable — TDP expansion drives volume more than anything else in the first 2 years
- SKU portfolio is still evolving; new launches cannibalize siblings; the risk of self-disruption is real and under-measured
- Forecasting is hard because there's no 3-year history — models need to borrow from analogous launches and category curves
- The FP&A team is small; no one has time to build and maintain ML models from scratch
- **Aevah advantage:** cold-start forecasting using category-level seasonality, TDP ramp modeling, and cannibalization-aware portfolio simulation

**Established / mature CPG brands** (e.g., brands with 5+ years of retail presence across major accounts):
- Distribution is largely stable; velocity and pricing are the primary levers
- Promo dependence is a growing concern — promo share creep erodes margin without growing real demand
- Competitive dynamics are intensifying; price gap monitoring and elasticity modeling become critical
- Planning teams have historical data but no good way to decompose it (what's seasonal vs. promo-driven vs. organic?)
- **Aevah advantage:** decomposed demand curves, retailer-level price elasticity, SPINS MRM promo baseline, competitive price gap events

The platform flexes to both contexts using the same data pipeline and the same Mo interface. The domain signals are the same; the weight placed on each shifts with the brand's lifecycle stage — and the model learns this automatically.

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
- "Do we have to rip and replace what our data science team already built?"
- **Pain:** AI tools that require wholesale data migration, vendor lock-in on LLM providers, or "trust us" black boxes that can't be audited. Also: fear of buying a tool that boxes out their internal team.
- **What they need:** Configurable provider stack, data stays in their environment, explainable models with audit logs — and a clear answer on build vs. buy flexibility.
- **Key message for this buyer:** Aevah is an extensibility harness, not a walled garden. Scored outputs (forecasts, elasticity, cannibalization) are available as structured data your team can query, extend, or feed into internal tools. You're not locked out of your own models.

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

### 2. Natural Language Data Interrogation — Anyone Can Ask, No Training Required

**Aevah AI Assist** (also referred to as AI Avatars) is the conversational interface on top of all of this data. It is grounded in live SPINS data and your business's own enterprise language — not static training data or generic CPG knowledge.

- An account manager can ask: *"Why is Walmart trending down for our 4-pack vs. last quarter?"* and get a specific answer citing distribution loss, a competitor price cut, or promo gap — with the supporting numbers.
- A CFO can ask: *"If we ran a 10% TPR at Kroger next quarter, what's the incremental revenue projection?"* and get a scenario with confidence bands.
- Aevah AI Assist cites its sources. It doesn't hallucinate. When it doesn't know something (because the data isn't there), it says so.

**Usability advantage:** Unlike traditional enterprise software that requires weeks of onboarding and role-specific training, Aevah AI Assist is intuitive by design. If a user can describe their question in plain English — the way they'd ask a colleague — they can use it immediately. There is no query language to learn, no report template to configure, no dashboard to navigate. The interface meets users where they are, in the language they already use to talk about their business.

**Talking point:** "You already pay for SPINS data. Aevah AI Assist makes it work for everyone on the team — not just the three people who know how to pull a report, and without a training program to get there."

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

- **Base units model (SPINS MRM baseline):** wMAPE = **4.3%** (Aevah demand model, 28 CPG-domain features)
- **Comparison baseline (YAGO-only, no ML):** wMAPE ≈ 30–118% depending on SKU maturity
- **The gap:** 20+ percentage points of improvement attributable to domain-specific signals (cannibalization, price elasticity, TDP momentum)

**ROI framing:** For a CPG brand doing $50M in retail revenue, a 1 percentage point improvement in forecast accuracy avoids roughly $500K in inventory carrying cost, lost sales, and markdown exposure annually. A 20pp improvement = $10M in value — from data you already have.

*Note: Use these directional numbers carefully. Actual ROI depends on the client's revenue base, inventory turns, and planning cycle. Always validate with client's own finance team rather than leading with a specific dollar figure.*

### 5. Security and Configurability — Enterprise-Ready

- **Data sovereignty:** SPINS data and client sales data live in the client's Druid cluster. Nothing is sent to a third-party LLM training pipeline.
- **Configurable LLM provider:** Aevah AI Assist can run on Anthropic Claude (default), OpenAI GPT-4o, or any OpenAI-compatible endpoint (Azure, Mistral, Llama 4, MS Copilot). One environment variable switch. No re-engineering required.
- **Explainable audit trail:** Every model prediction is traceable to a specific feature set, training run, and data version. Appropriate for finance teams with SOX or audit requirements.
- **No vendor lock-in:** The platform is data-source agnostic. SPINS today, NielsenIQ or IRI tomorrow.

### 6. Continuous Improvement — Value That Compounds Over Time

Most software delivers its value on day one and stays static until the next paid upgrade. Aevah is different: the longer it runs on your data, the more accurate and useful it becomes.

- **You get improvements today.** The models are production-ready at launch — not a proof of concept that needs months of tuning before it's useful. Clients see accurate forecasts from the first SPINS delivery.
- **Retraining on every data delivery.** Each time a new SPINS file arrives, models retrain on the expanded dataset. A SKU that was too new to forecast reliably six months ago now has enough history to model well. A retailer that just rolled out your product gains a properly calibrated baseline automatically.
- **Backtesting before anything goes live.** Every retrained model is validated against a held-out historical period before it replaces the prior version. If the new model is worse, the previous champion stays in production. Clients never unknowingly receive a degraded forecast.
- **Accuracy improves as your portfolio matures.** New SKUs gain seasonal patterns, YAGO comparisons become available, and competitive context deepens. The model learns the shape of your business over time — not just the level.
- **Platform-level refinements flow to all clients.** Signal improvements, new CPG domain features, and calibration updates developed across the platform are available to every deployment — not just the clients who requested them.

**Contrast with an internal build:** A model built in-house starts degrading the moment the data scientist who built it moves on. Without dedicated retraining infrastructure and backtesting pipelines, most internal ML projects are stale within 12 months of launch. Aevah handles this as a core part of the platform, not as an afterthought.

**Talking point:** *"You're not buying a snapshot. You're buying a system that keeps getting better on your data — automatically, with backtesting guardrails so you always know the model that's running is the best one we've seen."*

---

## Foundation Model Benchmark — The "Domain Knowledge Gap" Story

*Added 2026-07-08 after MO_62 live benchmark. Use this section when a buyer asks "why not just use ChatGPT/Google/Amazon for forecasting?" or when showcasing AI credibility.*

### What We Tested

We ran a head-to-head accuracy test: Aevah (trained with CPG domain signals) vs. four general-purpose AI forecasting models from the world's largest AI labs — all running on the same real data, same time period, same evaluation rules.

| Model | Organization | Training data |
|---|---|---|
| **Chronos** | Amazon | Billions of generic time series from public datasets |
| **TimesFM** | Google | 100B+ time points from diverse online sources |
| **Moirai** | Salesforce | Large-scale mixed-domain time series |
| **Granite TTM** | IBM | Enterprise time series benchmark suite |

All four are state-of-the-art. All four are used by large companies. All four run entirely on local hardware — no data leaves the building.

### What We Found

We forecast 100 SKU-retailer combinations over a 13-week holdout period that none of the models had ever seen:

| | Forecast error (lower = better) |
|---|---|
| **Aevah** | **6.1%** |
| Chronos (Amazon) | 27.7% |
| Granite TTM (IBM) | 27.7% |
| Moirai (Salesforce) | 32.3% |
| TimesFM (Google) | 38.1% |
| Naïve baseline (last known value) | 37.1% |

Aevah is **5× more accurate** than the average of the four foundation models — and actually beats Google's model by more than the naïve "just repeat last week" approach.

### Why the Gap Exists (Plain English for Non-Technical Buyers)

The big tech models are trained on billions of data points and are genuinely impressive for many tasks. But they were never trained on CPG retail data, and they don't know what a TDP is.

Three things kill their accuracy on a dataset like BUILT's:

**1. They can't see distribution.** When a product goes from 200 stores to 800 stores in a quarter, sales go up — obviously. But the model needs to know that's why. TDP (Total Distribution Points) is the signal that explains distribution velocity. Foundation models have no concept of this. Without it, they see a sales surge and don't know if it's real demand growth or a shelf rollout.

**2. They don't know about cannibalization.** When a company launches a new cookie dough bar, it may steal sales from the brownie bar. Foundation models treat every SKU independently — they don't know you own both. Aevah models the portfolio as a connected system.

**3. They confuse "price went down" with "demand went up."** Price promotions create temporary sales spikes that look like organic demand. SPINS' MRM baseline separates the two. Foundation models have no way to make this distinction from sales numbers alone.

The lesson isn't that Amazon and Google can't build good AI. They can. The lesson is that **general intelligence isn't the same as domain intelligence** — and in CPG forecasting, the domain knowledge is the competitive moat.

This gap is most pronounced for **growth-stage brands** (the hardest forecasting problem in CPG). A new SKU with 18 months of history has almost no signal for a generic foundation model to work with. Aevah's approach — borrowing category seasonality, modeling TDP ramp explicitly, and adjusting for sibling SKU cannibalization — is built exactly for this case. For **established brands**, the gap is smaller but still decisive (30+ pp on mature series with stable seasonality).

### Suggested Horserace Visual for Client Presentations

*See `outputs/mo62_foundation_benchmark.png` for the actual chart. For client-facing use, hide the Y-axis unit labels (units sold) but keep the % error labels — this shows the accuracy story without exposing proprietary volume data.*

**For a pitch deck or one-pager, suggest a two-panel visual:**

**Panel 1 — The Horserace:** Horizontal bar chart of forecast accuracy (% error), each model as a bar, Aevah bar highlighted in green, all others in orange/gray. No unit quantities anywhere. Only accuracy percentages. Label each bar: "Amazon," "Google," "Salesforce," "IBM," "Aevah." Title: *"Who Predicts CPG Demand Most Accurately?"*

**Panel 2 — The Gap:** Side-by-side columns showing "Foundation Models (avg)" vs. "Aevah + CPG Signals." Label the gap with the multiplier (5×). Add three callout boxes beneath explaining the gap: Distribution Signal, Cannibalization, Promo Decomposition.

**Framing for the room:** *"These are the same AI models that power some of the world's most sophisticated technology companies. On generic data, they're remarkable. On your SPINS data, without CPG domain features, they perform no better than guessing last week's number. That 30pp gap is what CPG expertise looks like when it's baked into a model."*

### Objection Handling

**"Can't we just use one of these foundation models ourselves?"**
> You could download and run them today — they're open source. But they would give you 30–38% error rates on your own data, vs. 6% from a domain-intelligent model. The bottleneck isn't the AI architecture. It's the CPG-specific feature engineering that takes years of domain knowledge to get right.

**"What if Google/Amazon improves their model?"**
> They will, and they should. But the domain knowledge gap isn't a model parameter — it's signal that doesn't exist in any public training dataset. No foundation model trained on public data knows what BUILT's TDP trajectory is, or how your 4-pack cannibalizes your 12-pack. That signal only exists inside your SPINS pipeline.

**"Isn't this just benchmarking against models that weren't designed for CPG?"**
> Exactly — and that's the point. These are the tools buyers would reach for if they didn't have Aevah. The comparison shows what "good enough" actually costs.

---

## "How Is This Different From Just Using Claude or ChatGPT?"

This question will come up in almost every technical or executive conversation. The short answer: **frontier LLMs are the language layer — Aevah is the intelligence layer. They work together.** Aevah AI Assist is already powered by Claude and GPT-4o. The question isn't Claude vs. Aevah; it's what Claude can do without Aevah vs. what it can do with it.

### What a Frontier LLM Can and Can't Do With Your SPINS Data

A frontier model like Claude is a remarkable generalist. It can reason about CPG concepts, explain what a TDP is, and help draft a retail QBR narrative. What it cannot do:

- **Train on your data.** Claude doesn't know what your Walmart BB 4-pack sold last Tuesday. It knows what protein bars are. Those are entirely different things. Without a purpose-built data pipeline connecting your specific SPINS feed to structured model outputs, every answer it gives about your business is a plausible guess — not a grounded fact.
- **Produce calibrated quantitative forecasts.** Ask Claude "what will our Kroger velocity be in Q4?" and you'll get a thoughtful non-answer or a hallucinated number. Aevah runs a statistical demand model on 2.5 years of your weekly SPINS history and returns a quantile forecast (q10/q50/q90) with a documented error rate. Those are fundamentally different outputs.
- **Control for confounders.** Price elasticity isn't "sales go up when price goes down." It requires controlling for distribution changes, promotional activity, seasonality, and launch phase simultaneously. Claude knows this conceptually. Aevah's causal model actually does it — with an audit trail showing which confounders were adjusted.
- **Detect cannibalization.** Identifying that your new cookie dough SKU is stealing 18% of your brownie bar's volume requires cross-SKU modeling across retailers and time. Claude can define cannibalization. Aevah measures it.
- **Hold 53 million rows in context.** LLMs have finite context windows. Even with retrieval-augmented generation (RAG), a generic wrapper can only surface fragments of your SPINS data at a time — not run models across the full dataset. Aevah processes the entire feed on every training run.

### Why a Wrapper Around a Frontier LLM Falls Short

Some teams try to solve this with a custom GPT or an LLM wrapper connected to their data warehouse. This gives you natural language query capability — which is valuable. But it still doesn't give you:

- **Quantitative models.** Querying a database in natural language is not the same as running demand forecasts, elasticity estimation, or cannibalization scoring. A wrapper can retrieve your sales history; it can't model it.
- **Validated accuracy.** A wrapper gives you plausible-sounding answers. Aevah gives you answers with documented error rates, backtested against held-out data. The difference matters when a CFO asks "how confident are you?"
- **CPG domain features.** The signals that make forecasting accurate — TDP velocity, promo lift decomposition, rolling cannibalization pressure, retailer-level elasticity — don't emerge from an LLM reading your data. They have to be engineered by someone who understands how CPG retail data actually works. That work is already done in Aevah.
- **Grounded citations.** Aevah AI Assist cites the specific SPINS table, retailer, and time range behind every claim. A generic wrapper hallucinates confidently when the data doesn't support a clean answer. Aevah's architecture forces the LLM to work from query results, not from its training priors.

### The Right Mental Model

Think of it this way: a frontier LLM is a brilliant analyst who has read every book about CPG. Aevah is the same analyst — but one who has also spent three years studying your specific brand's data, built proprietary models on it, validated those models against real outcomes, and can now answer questions about your business with both expertise and evidence.

Aevah AI Assist uses Claude and GPT-4o as the conversational interface on top of those models. The LLM explains what the models found, in your language and your business's terminology, tailored to your question. Without the models underneath, the LLM is just talking about CPG in general. With them, it's talking about your brand, your retailers, your SKUs — grounded in your data, cited, and auditable. This is what makes it feel like a frontier LLM while actually being grounded in your enterprise data.

**Talking point:** *"Claude and ChatGPT are already inside Aevah — that's how Mo talks to you. The question is what they have to work with. A frontier LLM without a purpose-built data pipeline is a brilliant analyst with no access to your files. Aevah is what gives them your files — modeled, validated, and queryable."*

### Objection: "We could build our own wrapper around the API"

> You could, and it would give you natural language SQL queries — useful. But it wouldn't give you a demand forecast, a price elasticity estimate, a cannibalization score, or a causal event analysis. Those require quantitative models, not just language models. Building those models on SPINS data, with CPG-specific domain features and proper backtesting, is 12–18 months of work. Aevah has already done it.

### Objection: "Can't the LLM just figure out the patterns from the data?"

> Not at the accuracy level your finance team needs. LLMs generate plausible outputs — they're optimized for coherence, not calibration. When Aevah says forecast accuracy is 6.1% error, that's a validated number from a held-out backtest. When a frontier LLM estimates your Q4 velocity, there's no equivalent validation behind it. For exploratory questions, LLM reasoning is valuable. For a demand plan you're presenting to your board, you need statistical models with documented error rates.

---

## Key Differentiators vs. Alternatives

### vs. Excel / Manual Planning
- Speed: hours → seconds for a scenario
- Accuracy: 4–30% wMAPE vs. 30–100%+ from simple extrapolation
- Explainability: decomposed drivers vs. "the analyst's judgment"
- Knowledge retention: model persists when the analyst leaves

### vs. Generic BI (Tableau, Power BI, Looker)
- BI shows what happened. Aevah predicts what will happen and explains why.
- BI requires a data analyst to build each view. Aevah AI Assist lets non-technical users ask questions in plain English — no training program required.
- BI doesn't have domain models. Aevah's cannibalization and elasticity models are CPG-specific.

### vs. Other ML Forecasting Platforms (e.g., o9, Anaplan, Palantir)
- Those platforms are general-purpose supply chain tools requiring multi-year implementations.
- Aevah is CPG-data-native — built around SPINS' specific field definitions, retail account structures, and promo mechanics.
- Aevah AI Assist is the differentiator: no other platform lets you interrogate your demand model in natural language with cited, grounded answers — in your enterprise language, with no system training required.

### vs. "Why Not Just Use Claude / ChatGPT Directly?"
- Frontier LLMs are already inside Aevah — Aevah AI Assist runs on Claude and GPT-4o. This is not an either/or question.
- A frontier LLM without Aevah underneath is a brilliant analyst with no access to your files. It knows what CPG is; it doesn't know what your Walmart 4-pack sold last Tuesday.
- LLMs generate plausible outputs. Aevah generates validated outputs — backtested, with documented error rates. A CFO can defend a 6.1% error rate; they cannot defend "the AI sounded confident."
- Building the quantitative layer (demand forecasts, elasticity estimation, cannibalization scoring) on top of a raw LLM API requires the same 12–18 months of domain engineering as building it from scratch. Aevah has already done it.
- See the full treatment in the "How Is This Different From Just Using Claude or ChatGPT?" section above.

### vs. "We'll have our data science team build it"
- Time to value: 12–18 months to replicate what's already production-ready on Aevah.
- Domain knowledge: CPG-specific features (promo lift decomposition, SPINS MRM integration, retailer-level elasticity) take years to get right.
- Maintenance: Aevah handles model refresh, retraining, and backtesting on each SPINS data delivery. Internal builds require ongoing engineering headcount — and most go stale within 12 months when the original builder moves on.
- Continuous improvement: Aevah's accuracy compounds over time as SKUs mature and history deepens. An internal build requires active investment to improve; Aevah improves by design.

---

## Build vs. Buy — Aevah Serves Both

Most enterprise software forces a binary choice: buy a vendor's black box or build your own from scratch. Aevah is designed to support both paths — and the path in between.

### Turnkey (Buy)

For teams that want fast time-to-value without internal data science investment:

- Connect your SPINS feed. Aevah ingests, validates, enriches, and models it.
- Aevah is live within weeks — SKU forecasts, price elasticity, cannibalization scores, competitive event alerts, and Aevah AI Assist for natural language Q&A.
- No ML engineers required on the client side. The platform handles model refresh on each SPINS delivery.
- **Best for:** Brands whose competitive edge is in sales, marketing, and trade — not in building data infrastructure. Teams that want the answers, not the engineering project.

### Extensibility Harness (Build on Top)

For teams with existing data science capability that want to integrate Aevah's CPG intelligence into their own workflows and tools:

- Aevah's scored outputs (elasticity, cannibalization, event queue, forecasts) are available as Druid tables and API endpoints — queryable from any BI tool, notebook, or internal app.
- Aevah AI Assist's natural language layer is configurable: LLM provider, system prompt, tool definitions, and screen logic are all accessible for customization.
- New models and signals can be plugged into the pipeline alongside Aevah's core models.
- **Best for:** Teams with data science or engineering resources who want to move fast on the CPG foundation (avoiding years of domain feature work) while owning the last-mile integration and customization.

### The Middle Path

Many clients start turnkey and evolve toward customization as they grow into the platform. Aevah's architecture supports this progression without re-platforming — the same data, the same models, the same API, with progressively more surface area exposed for client-side extension.

**Talking point:** *"We're not asking you to choose between a black box you can't touch and a ground-up build that takes two years. Aevah is the CPG intelligence foundation — you decide how much you want to customize on top of it."*

### Objection: "We want to own our own models"

> You can. Aevah's scored outputs are exposed as structured data — your data science team can train on them, extend them, or use them as features in your own models. What you don't have to rebuild is the CPG domain feature pipeline underneath: the promo decomposition, the cannibalization detection, the TDP velocity signals. Those take years. Start there, own the rest.

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
> Aevah AI Assist only answers from grounded data — it cites the specific SPINS table, retailer, and time range for every claim. When the data doesn't support an answer, it says so rather than fabricating a number. The models are transparent: every prediction traces back to specific signals a CFO can follow.

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
- **Don't:** Lead with model names or internal implementation details in executive conversations. Lead with outcomes. Technical specifics belong in separate conversations with data science buyers only.

---

## Numbers Available for Use

These are real production numbers from the BUILT deployment. Use carefully — always note these are from a specific client's data set; actual results vary.

| Metric | Value | Context |
|---|---|---|
| Base units forecast accuracy | 4.3% wMAPE | 104 SKUs × 78 retailers, 13-week horizon, Aevah demand model |
| Total units forecast accuracy | 9.47% wMAPE | Includes promo lift component — inherently more variable |
| Improvement over YAGO-only baseline | 20–25 pp | Varies by SKU maturity and retailer data quality |
| **Foundation model benchmark — Aevah vs. Amazon Chronos** | **6.1% vs. 27.7%** | Same 13-week holdout, 100 series; Aevah 4.5× better |
| **Foundation model benchmark — Aevah vs. Google TimesFM** | **6.1% vs. 38.1%** | Aevah 6.2× better; Google model tied with naïve baseline |
| **Foundation model benchmark — Aevah vs. Salesforce Moirai** | **6.1% vs. 32.3%** | Aevah 5.3× better |
| **Foundation model benchmark — Aevah vs. IBM Granite TTM** | **6.1% vs. 27.7%** | Aevah 4.5× better |
| Foundation model average (all 4) | 31.6% wMAPE | 5.1× worse than Aevah; gap = CPG domain signals |
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
