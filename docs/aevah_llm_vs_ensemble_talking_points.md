# Talking Points: Why a Frontier LLM Will Never Do What Our Ensemble Model Does

---

**Q: We need to help the CFO understand why a frontier LLM isn't going to ever produce what our ensemble model does.**

---

**A:**

### The one-sentence answer

A frontier LLM predicts the next word in a text sequence. We predict next quarter's demand for a specific SKU at a specific retailer — using signals that have never been published anywhere on the internet.

---

### If they say "can't ChatGPT just do this?"

Start here: GPT-4, Gemini, Claude — these are trained on public text. They have never seen your scan data, your TDP trajectory, your promotional cadence, or the relationship between a $0.05 price move and unit velocity in your specific channel. Asking a frontier LLM to forecast your demand is the right question aimed at the wrong tool. It's like hiring a world-class copywriter to run your supply chain.

---

### Three things a frontier LLM structurally cannot do

**1. See your data.**
It has no access to your weekly POS actuals, distribution points, average retail price, or promo history. It would be constructing a guess from general category knowledge, not from what actually happened in your stores last week.

**2. Explain *why* demand is changing.**
A CFO's question is never just *what* — it's *why*, and *what to do about it*. Our model's output says: "This forecast is driven by +4 TDP points and a widening competitor price gap." A frontier LLM says: "Sales may increase." Those are not the same thing.

**3. Give calibrated uncertainty.**
Finance needs low / base / high scenario bands with defined confidence. LLMs generate prose. They do not produce quantile distributions, and they cannot tell you the 90th percentile demand case for your Q3 planning cycle.

---

### "What about AI models built specifically for forecasting?"

Good instinct — and we tested those too. Chronos, TimesFM, Moirai, Granite TTM: foundation models purpose-built for time-series forecasting, trained on millions of series. Our ensemble model beat the average of all four by **5.1×** on error rate. The reason: they are general-purpose. We are not. Every signal in our model — distribution momentum, price elasticity, cannibalization pressure, promotional lift — was engineered specifically for CPG sell-through at retail, and learned from your own scan history, not the public internet.

---

### The moat argument (for the CFO who asks about build vs. buy)

A frontier LLM API call costs the same for every company in your category. Our model is trained on your data, with signals derived from your retail relationships. That proprietary fit is the edge. Every quarter it retrains on new actuals — compounding accuracy over time. An LLM stays static between public training runs, with no knowledge of what happened at any retailer last Tuesday.

The question is not "LLM or model?" The question is: do you want a generic answer available to every competitor, or a model that knows your business specifically and gets smarter every time you get new data?

---

### If they push back: "But AI is moving fast — won't this change?"

Acknowledge it: the frontier is moving. What won't change is the data access problem. A public LLM will never be trained on your confidential SPINS scan history. It cannot be — that data is proprietary by contract. The only way to get a model that knows your demand is to train one on your demand. That is exactly what we do.

---

*Aevah Platform · Internal use — not for distribution*
