# Trust document for Brian: facts to confirm (Rob)

Brian asked for a "trust document" he can share on how Aevah's Mo works: security, top-level architecture,
how it differs from generative AI products, how it uses machine learning, and data sources. Audience: BUILT
leadership and finance. Technologies are described generically (no vendor names) unless you prefer otherwise.

Each item below is something the document would state. Please mark it **Yes**, **No**, or **Correct to: ...**,
or tell us to leave it out. Nothing unconfirmed goes into the version Brian receives.

## Hosting and data storage
1. Where BUILT's data lives in production (cloud provider and region, or on-premises), and whether that is
   dedicated to Aevah/BUILT or shared.
2. Is data encrypted in transit (HTTPS/TLS) between users, the app and the data store?
3. Is data encrypted at rest (data store, backups, stored files)?
4. Backups: how often, where, how long kept.
5. Data retention: how long BUILT's data is kept, and what happens to it if the engagement ends.
6. Model training runs on a GPU cloud service, and BUILT's sales panel is copied to a storage volume in the EU
   for those runs. Is it acceptable to state this? Should the volume move to a US region before Brian shares the
   document?

## Access control
7. How users sign in today: individual accounts, single sign-on through BUILT's identity provider, or both.
   The wiki lists BUILT single sign-on as Phase B.
8. Are role-based access tiers live (for example finance/executive full access, sales own customers only)?
   The wiki lists this as open.
9. Who at Aevah can access BUILT's data, and is that access logged?
10. In production, is the Mo Chat access-token check switched on, and is the app restricted to known web
    addresses? In the code, the token check is bypassed in development mode and the allowed-origins list holds
    only local addresses.

## AI language model (Mo Chat)
11. Which provider handles Mo Chat in production (a commercial provider or the local model)?
12. When the commercial provider is used, what data is sent (question plus the relevant summary numbers), and do
    our terms with the provider exclude training on our data and limit retention? Is it acceptable to say so?
13. Can BUILT opt for the local model so no data leaves Aevah's environment? Is that offered?

## Architecture (top level)
14. Is this flow correct for production?
    - Data sources: SPINS weekly, Circana for Costco, BUILT's own NetSuite shipments and trade promotions, public
      economic data
    - Secure data store
    - Feature tables and machine-learning scoring, run on a schedule as new data arrives
    - Versioned results stored back in the data store
    - Mo app and Mo Chat, served through fixed, predefined data endpoints
15. Anything to add: monitoring, uptime, incident handling, change control.

## Anything else
16. Certifications or audits (for example SOC 2), or security policies we can reference. If there are none,
    we will not imply any.
17. Anything you would rather we not state publicly.

---

# Rob's answers (2026-10-14)

Walked through with Rob item by item. "Leave out" means the document says nothing on that topic, and must not
imply it either way.

**Framing from Rob:** Brian's "trust" is mainly trust in the **accuracy of the outputs**, not traditional IT
data plumbing. Lead the document with how Mo's numbers are produced and checked. Keep the security section,
but as supporting material.

| # | Topic | Answer |
| --- | --- | --- |
| 1 | Where data lives | **Yes, state it:** Mo runs in **BUILT's own Azure subscription**, region West US 3 (United States), operated by Aevah. Naming Azure is fine (item 17). |
| 2 | Encryption in transit | **Leave out.** |
| 3 | Encryption at rest | **Leave out.** |
| 4 | Backups | **Leave out.** |
| 5 | Data retention | **Leave out.** |
| 6 | GPU-cloud training copy (EU volume) | **Remove the mention.** Consequence: the document must make no absolute data-residency claim, such as "BUILT's data never leaves the US" or "never leaves BUILT's environment". |
| 7 | How users sign in | **Leave out.** |
| 8 | Role-based access tiers | **No, leave out.** |
| 9 | Who at Aevah has access, and logging | **Leave out.** |
| 10 | Mo Chat token check and allowed origins | **Leave out, and delete the draft line "Mo Chat requires an authenticated client."** |
| 11 | Language model provider | **Leave out.** Do not name the provider. |
| 12 | What Mo Chat sends, and provider terms | **Leave out entirely.** |
| 13 | Local-model option | **Not offered, leave out.** |
| 14 | Architecture flow | **Flag for review with Jason and Rob.** See the discrepancies below. |
| 15 | Monitoring, uptime, incidents, change control | **Leave out.** |
| 16 | Certifications or audits | **None. Imply nothing:** no "enterprise-grade", "secure by design" or "compliant" wording. |
| 17 | Not to state publicly | **Do not mention unbuilt controls as plans:** no SSO, role tiers, backups or local model described as "coming". Rob did not restrict vendor names or accuracy figures here. The existing rules still apply: `docs/ACCURACY_CLAIMS_REGISTER.md` for any accuracy number, and the aevah-pipeline collateral rule on naming underlying software. Confirm with Rob which rule governs vendor names in this document. |

## Item 14: the three discrepancies to review (Jason and Rob)

The draft's flow, checked against the repo:

1. **Public economic data.** This was tested (MO_76, FRED/EIA), showed no reliable gain, and was archived. As far
   as the repo shows, it does not feed Mo's numbers.
2. **"Run on a schedule as new data arrives".** No scheduler was found. Refreshes are run and checked by hand when
   SPINS data arrives, and "refresh cadence" is an open item for Rob in project memory.
3. **NetSuite shipments and trade promotions.** These may not drive Mo's numbers yet:
   - the shipments forecast (MO_141) was approved on 10-13;
   - whether shipments lead SPINS is an open question;
   - trade promotions were only just loaded.

   NetSuite *item attributes* are in the item master.

Proposed correction, if confirmed:
1. Data sources: SPINS weekly (the core), Circana for Costco, and BUILT's item master including NetSuite
   attributes. Shipments and trade promotions are being added and evaluated.
2. A secure data store in BUILT's environment.
3. Feature tables and ML scoring, refreshed by Aevah when new SPINS data arrives and checked before release.
4. Versioned results stored back in the data store.
5. The Mo app and Mo Chat, served only through fixed, predefined data endpoints.

## What this leaves in the security section

One sentence from item 1, and nothing that implies certifications (item 16). The rest of the document carries
the trust argument:
- how the machine learning works;
- how Mo differs from generative AI;
- the data sources (after item 14);
- "keeping the numbers honest".

## Follow-ups for Rob and Jason (internal; not for the document)

Found while checking, and worth fixing whatever the document says:
- **No user sign-in.** The Mo web app has no login code, so the app may be reachable by anyone who has the
  address, unless something in front of it restricts access.
- **Mo Chat token check is skipped** when `MO_CLIENT_KEY` is unset, and the allowed origins list only local
  addresses.
- **No tested backups.** As of the 28 Sep data-preservation review, no backup had been created and no restore
  tested.
- **BUILT data outside BUILT's subscription.** Copies sit in the built-mo-preview GitHub repo
  (`data/druid_loads/`, `forecasts_registered/`, outputs), on the GPU-cloud volume (EU), and on laptops.
- **HTTPS (item 2) can be checked** with one request to `pilot.builtaevah.com`, if Rob later wants a statement on
  encryption in transit.
