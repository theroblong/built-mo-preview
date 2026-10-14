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
