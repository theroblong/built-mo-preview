# Talking Points: Why a Frontier LLM Will Never Do What Our Ensemble Model Does

---

**Q: We need to help the CFO understand why a frontier LLM isn't going to ever produce what our ensemble model does.**

---

**A:**

### The one-sentence answer

A frontier LLM predicts the next word in a text sequence. We predict next quarter's demand for a specific SKU at a specific retailer — using signals that have never been published anywhere on the internet.

---

### How much does accuracy matter?

Before any technology comparison, anchor on the dollars. Independent CPG supply chain research puts the value of a 1% improvement in forecast accuracy at **$1.43M–$3.52M per year** for a mid-to-large CPG company — in reduced inventory carrying costs, markdown risk, and lost-sale prevention alone. That is before the revenue upside from better promotional timing and distribution decisions.

We validated this on real scan data across IRI, Nielsen, and SPINS. Our ensemble model — trained on domain-specific CPG signals — produces **5× lower forecast error** than the next best AI alternative tested. If a 1% gain is worth $1.43M, a 20–30 point accuracy gap is not a rounding error. It is a strategic liability.

That is the opening question for any CFO: *how much does accuracy matter to your business?* Everything else follows from that answer.

---

### If they say "can't ChatGPT just do this?"

Start here: GPT-4, Gemini, Claude — these are trained on public text. They have never seen your scan data, your TDP trajectory, your promotional cadence, or the relationship between a $0.05 price move and unit velocity in your specific channel. Asking a frontier LLM to forecast your demand is the right question aimed at the wrong tool. It's like hiring a world-class copywriter to run your supply chain.

At a technical level: LLMs are transformer models trained to predict the next token in a text sequence — the order of words and letters, forwards and backwards, across vast amounts of publicly available language. That is a remarkable capability. It is not demand forecasting. It is not trained on any particular business or process. It has no concept of your retail accounts, your pack sizes, your promotional lift history, or your competitive price gaps.

---

### Three things a frontier LLM structurally cannot do

**1. See your data.**
It has no access to your weekly POS actuals, distribution points, average retail price, or promo history. It would be constructing a guess from general category knowledge, not from what actually happened in your stores last week.

**2. Explain *why* demand is changing.**
A CFO's question is never just *what* — it's *why*, and *what to do about it*. Our model's output says: "This forecast is driven by +4 TDP points and a widening competitor price gap." A frontier LLM says: "Sales may increase." Those are not the same thing.

**3. Give calibrated uncertainty.**
Finance needs low / base / high scenario bands with defined confidence. LLMs generate prose. They do not produce quantile distributions, and they cannot tell you the 90th percentile demand case for your Q3 planning cycle.

---

### Straight from the source — Claude's own buying agent

When asked directly: *"If I wanted to use Claude over batch ingestion data and multiple tables — one of them 300 million rows and 300 columns — how much might it cost to forecast and detect events that are accurate and repeatable and deterministic?"*

Claude's official buying agent gave three answers that matter:

**1. You cannot feed a 300-million-row table to Claude.**
> "The model works on the text you send it, so a table that size gets processed in whatever slices your pipeline extracts and passes in, not all at once."

The cost driver is tokens sent and returned — not the intelligence derived from the full dataset. You would be paying per query, per slice, with no model that has actually learned from your complete demand history.

**2. Claude is not deterministic or repeatable.**
> "Claude is a generative model, so identical inputs won't always produce byte-identical outputs."

A CFO's planning process cannot run on a model that gives a different answer each time the same question is asked. Finance requires auditability. LLMs structurally cannot provide it.

**3. Claude itself recommends using statistical models to do the actual forecasting.**
> "Teams that need accurate, repeatable forecasting typically pair the model with deterministic code and statistical models, using Claude to orchestrate or interpret rather than to compute the forecast itself."

This is not a criticism of LLMs — it is an accurate description of what they are for. Claude is excellent at orchestrating and interpreting. The statistical model that actually computes the forecast — trained on your specific scan data, with domain-specific signals, producing quantile outputs — that is what Aevah builds. The two are not in competition. One answers questions; the other runs your business.

---

### The enterprise cost reality — confirmed by a competing AI

When asked directly how much it would cost for 100 users to forecast over a 300-million-row × 300-column table joined with 10 other enterprise tables, Google Gemini gave this answer:

> "Directly feeding a table with 300 million rows and 300 columns into Claude or ChatGPT to run forecasts is **mathematically and technically impossible.**"
>
> "A single dataset of that size represents roughly 90 billion individual data cells. Converted into text format for an AI to read, this translates to **over 180 billion tokens.** The maximum capacity of the largest LLM context windows is 1 million tokens — trying to process this directly would require a context window **180,000 times larger** than what current technology allows."

This is the data access problem stated in hard numbers. A frontier LLM cannot see your dataset — not in principle, not in practice, not with any current or near-term architecture.

**What actually happens instead (per Gemini's own description):**

```
[100 Users] ──> [Claude / ChatGPT] ──> Generates SQL ──> [Data Warehouse]
                                                                 │
[User Interface] <── Synthesized text <── Aggregated results (KB) ─┘
```

The LLM translates natural language into SQL. The warehouse runs the heavy join. The aggregated result — a few kilobytes — comes back to the LLM to summarize in prose. **The LLM is not forecasting. It is writing SQL and narrating summaries.** That is a fundamentally different capability from a model that has actually learned your demand patterns.

**What Gemini estimated for 100 enterprise users:**

| Component | Monthly cost |
|-----------|-------------|
| LLM seats (Claude Enterprise ~$20/seat, ChatGPT ~$60/seat) | $2,000–$6,000 |
| LLM token API overages (queries + summaries) | $500–$1,500 |
| Data warehouse compute (Snowflake/Databricks, 300M-row joins) | $4,000–$12,000 |
| **Total** | **$6,500–$19,500/month** |

And Gemini's caveat on Claude Enterprise specifically:

> "If your 100 users are power analysts constantly generating massive forecasting reports, token costs can push your true Claude cost up to **$60 to $250+ per user/month.**"

So the tool that "can't do the forecasting" still costs $78K–$234K per year at the high end — before you have a single trained forecast model. The warehouse compute is the real exposure, because every unoptimized LLM-generated SQL query risks a full-table scan on a 300-million-row dataset.

**The summary:** A third competing AI, given a direct question about enterprise forecasting at your scale, confirmed: (1) direct data ingestion is impossible, (2) the LLM's actual role is SQL generation and text synthesis, (3) the real cost driver is the warehouse, not the LLM. None of this is our framing — it is what the systems themselves say about their own limitations.

Our ensemble model sidesteps this entirely. The demand patterns are learned once, at training time, from your complete scan history. Inference is a fast lookup, not a 300-million-row join. And the output is a calibrated quantile forecast — not a prose summary of a database query.

---

### "What about AI models built specifically for forecasting?"

Good instinct — and we tested those too. Chronos, TimesFM, Moirai, Granite TTM: foundation models purpose-built for time-series forecasting, trained on millions of series. Our ensemble model beat the average of all four by **5.1×** on error rate. The reason: they are general-purpose. We are not. Every signal in our model — distribution momentum, price elasticity, cannibalization pressure, promotional lift — was engineered specifically for CPG sell-through at retail, and learned from your own scan history, not the public internet.

---

### Exploration vs. operation — the distinction that matters

LLMs are extraordinary exploration tools. You can ask them anything, brainstorm scenarios, draft documents, synthesize research. That value is real.

But once you have a business target — a specific forecast you need to hit, a planning cycle you need to run, a decision that has to be made every week — you need to *operationalize*. Exploration is open-ended. Operation is repeatable, consistent, auditable, and governed.

**Aevah operationalizes AI.** The same statistical pipeline runs every quarter on fresh scan data, producing the same structured output: quantile forecasts, driver attribution, scenario bands. A CFO can rely on it because it does not change its mind based on how a question is phrased. It does not hallucinate a promotional effect that never happened. It runs the same way every time and you can audit every step.

---

### The harness, the guardrails, and the governance

The model is one piece. What makes it production-ready is what surrounds it.

An LLM — even one pointed at your data — is a raw capability. Making it useful for a repeatable business process requires: a data preparation pipeline that cleans and structures your scan inputs the same way every run; statistical guardrails that catch nonsensical outputs before they reach a planner; governance that creates an audit trail so finance can explain a forecast to a board; and a user harness that surfaces the right answer to the right person in the right context.

Building that harness on top of a general-purpose LLM is months of custom engineering work — and it still does not give you a model that has learned the demand patterns in your category. It gives you a wrapper around a generic model. That is a fundamentally different thing.

---

### The moat argument (for the CFO who asks about build vs. buy)

A frontier LLM API call costs the same for every company in your category. Our model is trained on your data, with signals derived from your retail relationships. That proprietary fit is the edge. Every quarter it retrains on new actuals — compounding accuracy over time. An LLM stays static between public training runs, with no knowledge of what happened at any retailer last Tuesday.

The question is not "LLM or model?" The question is: do you want a generic answer available to every competitor, or a model that knows your business specifically and gets smarter every time you get new data?

---

### On Palantir — if it comes up

Palantir is the nearest established competitor in enterprise AI operationalization and the right reference point for a sophisticated buyer. Their AIP platform does something real: it wraps LLMs in a structured business context layer (their "Ontology") so that a general model can reason about your specific operations with governance and security controls. That is a meaningful advance over raw LLM access.

But understand what it is and what it is not:

- **Palantir AIP is a platform for building AI applications.** You still have to build the forecasting application on top of it. It is infrastructure, not a pre-built CPG demand model.
- **The model at the core is still a general LLM.** Palantir wraps it in context; they do not replace it with a purpose-trained statistical model that has learned your demand patterns from your scan history.
- **Palantir's scale and sales motion is government and large enterprise.** Their AIP Bootcamp strategy compresses sales cycles — but the implementation, ontology construction, and ongoing maintenance are significant commitments. It is not a plug-in for a CPG brand on SPINS.
- **They do not produce quantile forecasts trained on your SKU-retailer demand history.** Their strength is reasoning about your business; our strength is *having already learned* your business from your data.

Where Palantir operationalizes LLMs around enterprise knowledge, Aevah trains statistical ensemble models on CPG scan data. Different problem, different architecture, different result. If a prospect is evaluating both, the right question is: *do you need a general enterprise AI platform, or a purpose-built demand intelligence system that is ready to run on your SPINS data today?*

---

### If they push back: "But AI is moving fast — won't this change?"

Acknowledge it: the frontier is moving. What won't change is the data access problem. A public LLM will never be trained on your confidential scan history. It cannot be — that data is proprietary by contract. The only way to get a model that knows your demand is to train one on your demand. That is exactly what we do.

And the more the frontier moves, the more this distinction matters. Better general models make better general answers. They do not make your data less proprietary, your demand patterns less specific, or your need for consistent, auditable, repeatable forecasts less real.

---

*Aevah Platform · Internal use — not for distribution*
