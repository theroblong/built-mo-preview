# Aevah planning inputs: two templates (DRAFT for Connor and the sales team)

**Status:** starting draft from Aevah, 2026-10-09, after the "Financial Questions for Aevah
Forecast" meeting. Connor and the sales team are expected to reshape it. The column list is a
proposal, not a requirement.

**Why these two tables:** sales history (SPINS / Circana) tells Aevah what already happened.
These two tables tell it what is *planned*: promotions and distribution changes. Today that
knowledge lives in many spreadsheets and in people's heads. One promotions table and one
forward-plan table let the forecast use it, and let Aevah show "forecast with plans" next to
"forecast from sales history alone".

Files: `templates/promotions_table_TEMPLATE.csv`, `templates/forward_plan_TEMPLATE.csv`.
One file each; a tab per retailer is fine if that is easier, as long as the columns match.

## Ground rules (both tables)

1. **Never overwrite a row; add a new one.** When a plan changes, add a row with a new
   `as_of_date` and keep the old one. This gives two things: honest testing (Aevah can check
   how the forecast would have done using only what was known at the time) and forecast
   versions over time (budget vs latest estimate vs actuals), which Clark asked for.
2. **Weeks end on Sunday**, matching SPINS.
3. **Retailer names as they appear in SPINS**, so rows match the sales data. Aevah can provide
   the list.
4. **Blank is fine.** Fill in what you know; Aevah treats blanks as unknown, never as zero.

## Table 1: promotions (one row per promotion, per retailer, per item or item group)

| Column | What it means | Notes |
|---|---|---|
| promo_id | Your reference for this promotion | Any unique text |
| as_of_date | When this row was entered or last changed | Required (see rule 1) |
| status | planned / confirmed / executed / cancelled | Planned trade deals are not yet confirmed shelf promotions |
| retailer, banner_or_region, channel | Where it runs | |
| item_upc or item_or_group | What is promoted | A group like "all PUFF 4-packs" is fine |
| start_week_ending, end_week_ending | When it runs at shelf | Sundays |
| mechanic | TPR $ off, % off, BOGO, B2G1, coupon book, digital coupon, club MVM, display only | Different mechanics lift very differently (the Publix BOGO lift was 1,000% vs 400% assumed) |
| regular_shelf_price, promo_shelf_price, discount_per_unit | Price before and during | Lets Aevah measure lift per dollar of discount |
| trade_type | scan, club scan, bill back, off invoice, depletion, processing fee, fixed | The seven types in the current promotion file |
| planned_trade_spend | Planned spend | Optional |
| display_or_feature_committed, displays_committed_count | What the retailer promised | Execution often falls short; this lets Aevah learn the gap |
| expected_lift_pct_sales_assumption | The sales team's expected lift | Aevah will show measured lift next to it |
| owner, notes | Who maintains the row; anything else | |

## Table 2: forward plan (one row per retailer, item and change)

| Column | What it means | Notes |
|---|---|---|
| plan_id, as_of_date | Reference; when entered or changed | |
| confidence | committed / likely / possible | Aevah can show scenarios by confidence level |
| retailer, banner_or_region, channel | Where | |
| event_type | new item, distribution gain, distribution loss, delist, new retailer, reset, item swap | |
| item_upc / planned_item_name | The item; a name is fine before a UPC exists (e.g. Dreamwich) | |
| effective_week_ending | When the change happens at shelf | Sunday |
| store_count_after / store_count_change | Stores carrying the item after the change | This is the biggest driver of growth, and history alone cannot predict it |
| assumed_starting_velocity_units_per_store_week | Optional starting sales rate for a new item | Leave blank and Aevah will propose one from similar items |
| similar_item_upc_or_name | A comparable item to borrow history from | Helps with brand-new items |
| shelf_placement | Next to existing items, new section, checkout, other | Drives cannibalization |
| replaces_item | The item being replaced, for swaps | e.g. salted caramel to Dreamwich |
| owner, notes | | |

## Open questions for Connor and the sales team
1. Which columns are hard to fill, and which are missing?
2. Who maintains each table, and how often (weekly, monthly, at each plan cycle)?
3. Can the existing 50–100 promotion files feed this table automatically, or does it replace them?
4. Should planned promotions and new items be in Aevah's forecast at all, or only in the sales
   forecast? (Scope question Brian is taking to Megan and Bracken.)
