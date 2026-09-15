<img src="costco_faq_media/media/image1.jpeg" style="width:0.95208in;height:0.92986in" alt="A shopping cart with a box on top Description automatically generated with low confidence" />

## Circana Costco FAQs and Data Nuances

Version Number 6

Date (June 17, 2025)

# Contents

[Circana Costco FAQs and Data Nuances [1](#circana-costco-faqs-and-data-nuances)](#circana-costco-faqs-and-data-nuances)

[Data Refresh: [6](#data-refresh)](#data-refresh)

[When is daily data updated? [6](#when-is-daily-data-updated)](#when-is-daily-data-updated)

[Are there scheduling capabilities available within Unify Costco Portal? [6](#are-there-scheduling-capabilities-available-within-unify-costco-portal)](#are-there-scheduling-capabilities-available-within-unify-costco-portal)

[Can we use our internal Robotic Process Automation system/internal ”bot” to automate our regularly run (e.g., weekly, monthly) reports? [6](#can-we-use-our-internal-robotic-process-automation-systeminternal-bot-to-automate-our-regularly-run-e.g.-weekly-monthly-reports)](#can-we-use-our-internal-robotic-process-automation-systeminternal-bot-to-automate-our-regularly-run-e.g.-weekly-monthly-reports)

[Item: [8](#item)](#item)

[Why can’t I see my item in the database? [8](#why-cant-i-see-my-item-in-the-database)](#why-cant-i-see-my-item-in-the-database)

[Which Item Dimension hierarchy should I use when selecting my items? [9](#which-item-dimension-hierarchy-should-i-use-when-selecting-my-items)](#which-item-dimension-hierarchy-should-i-use-when-selecting-my-items)

[Point of Sale Data Hierarchy Overview [9](#point-of-sale-data-hierarchy-overview)](#point-of-sale-data-hierarchy-overview)

[All Items by Parent Hierarchy Overview [10](#all-items-by-parent-hierarchy-overview)](#all-items-by-parent-hierarchy-overview)

[All Items by Department-Parent Hierarchy Overview: What does “Closed Subcategories or Segments” mean? [12](#all-items-by-department-parent-hierarchy-overview-what-does-closed-subcategories-or-segments-mean)](#all-items-by-department-parent-hierarchy-overview-what-does-closed-subcategories-or-segments-mean)

[How does the Category Restrictions nesting work? [12](#how-does-the-category-restrictions-nesting-work)](#how-does-the-category-restrictions-nesting-work)

[All Items by Department-Parent Hierarchy: Data-Pull Example [13](#all-items-by-department-parent-hierarchy-data-pull-example)](#all-items-by-department-parent-hierarchy-data-pull-example)

[Shopper Basket (FSP) Data Hierarchies Overview [13](#shopper-basket-fsp-data-hierarchies-overview)](#shopper-basket-fsp-data-hierarchies-overview)

[Why do we have POS data reported under UPC Codes “99999” and “00000”? [14](#why-do-we-have-pos-data-reported-under-upc-codes-99999-and-00000)](#why-do-we-have-pos-data-reported-under-upc-codes-99999-and-00000)

[Time: [17](#time)](#time)

[What is the Costco selling-week timeframe? [17](#what-is-the-costco-selling-week-timeframe)](#what-is-the-costco-selling-week-timeframe)

[What is the fiscal year-to-date that is used within the Costco database? [17](#what-is-the-fiscal-year-to-date-that-is-used-within-the-costco-database)](#what-is-the-fiscal-year-to-date-that-is-used-within-the-costco-database)

[How are the comparison time periods determined? [17](#how-are-the-comparison-time-periods-determined)](#how-are-the-comparison-time-periods-determined)

[**Example 1 – Current YTD and Calendar Month Hierarchies:** [18](#example-1-current-ytd-and-calendar-month-hierarchies)](#example-1-current-ytd-and-calendar-month-hierarchies)

[Example 2 – Week Time Hierarchy: [19](#example-2-week-time-hierarchy)](#example-2-week-time-hierarchy)

[Launch Weeks Hierarchy: [20](#launch-weeks-hierarchy)](#launch-weeks-hierarchy)

[Venue – Warehouses: [22](#venue-warehouses)](#venue-warehouses)

[Do you have a warehouse list? Are we able to see sales by region filtered down by state, and then [22](#do-you-have-a-warehouse-list-are-we-able-to-see-sales-by-region-filtered-down-by-state-and-then)](#do-you-have-a-warehouse-list-are-we-able-to-see-sales-by-region-filtered-down-by-state-and-then)

[filtered to the warehouse number? [22](#filtered-to-the-warehouse-number)](#filtered-to-the-warehouse-number)

[Why isn’t this warehouse reporting sales? My product is supposed to be in every warehouse. [23](#why-isnt-this-warehouse-reporting-sales-my-product-is-supposed-to-be-in-every-warehouse.)](#why-isnt-this-warehouse-reporting-sales-my-product-is-supposed-to-be-in-every-warehouse.)

[What is the meaning behind 1-3 in the status_attr column? [23](#what-is-the-meaning-behind-1-3-in-the-status_attr-column)](#what-is-the-meaning-behind-1-3-in-the-status_attr-column)

[I see two Warehouses, both listed as Selling Warehouses, in the same city, just a few miles apart. One returns null results for all measures, the other returns data. What’s going on here? [23](#i-see-two-warehouses-both-listed-as-selling-warehouses-in-the-same-city-just-a-few-miles-apart.-one-returns-null-results-for-all-measures-the-other-returns-data.-whats-going-on-here)](#i-see-two-warehouses-both-listed-as-selling-warehouses-in-the-same-city-just-a-few-miles-apart.-one-returns-null-results-for-all-measures-the-other-returns-data.-whats-going-on-here)

[Venue – Depots: [24](#venue-depots)](#venue-depots)

[Do we have list of which depots service which warehouse stores? [24](#do-we-have-list-of-which-depots-service-which-warehouse-stores)](#do-we-have-list-of-which-depots-service-which-warehouse-stores)

[What does “RCTR” signify in the Warehouse Name? Should these locations be counted towards [24](#what-does-rctr-signify-in-the-warehouse-name-should-these-locations-be-counted-towards)](#what-does-rctr-signify-in-the-warehouse-name-should-these-locations-be-counted-towards)

[inventory? [24](#inventory)](#inventory)

[What do “INN” and “DDC” signify in the Warehouse Name? [25](#what-do-inn-and-ddc-signify-in-the-warehouse-name)](#what-do-inn-and-ddc-signify-in-the-warehouse-name)

[What does “MDO” signify in the Warehouse Name? [25](#what-does-mdo-signify-in-the-warehouse-name)](#what-does-mdo-signify-in-the-warehouse-name)

[At what level can the depot number be pulled? [26](#at-what-level-can-the-depot-number-be-pulled)](#at-what-level-can-the-depot-number-be-pulled)

[Why do I see Depot Numbers reporting blank or zero? [26](#why-do-i-see-depot-numbers-reporting-blank-or-zero)](#why-do-i-see-depot-numbers-reporting-blank-or-zero)

[Venue – e-Commerce: [27](#venue-e-commerce)](#venue-e-commerce)

[Are e-Commerce locations included in Total US/Total Canada venues? [27](#are-e-commerce-locations-included-in-total-ustotal-canada-venues)](#are-e-commerce-locations-included-in-total-ustotal-canada-venues)

[Are Instacart sales reflected under e-Commerce? [29](#are-instacart-sales-reflected-under-e-commerce)](#are-instacart-sales-reflected-under-e-commerce)

[What about “Powered through Instacart” sales, e.g., sameday.costco.com? [30](#what-about-powered-through-instacart-sales-e.g.-sameday.costco.com)](#what-about-powered-through-instacart-sales-e.g.-sameday.costco.com)

[Does e-Commerce reporting depend on where the item ships from? [30](#does-e-commerce-reporting-depend-on-where-the-item-ships-from)](#does-e-commerce-reporting-depend-on-where-the-item-ships-from)

[When do e-Commerce sales report in the database? [30](#when-do-e-commerce-sales-report-in-the-database)](#when-do-e-commerce-sales-report-in-the-database)

[Why don’t our E-Commerce Sales numbers match those provided to us by our buyer(s)? [30](#why-dont-our-e-commerce-sales-numbers-match-those-provided-to-us-by-our-buyers)](#why-dont-our-e-commerce-sales-numbers-match-those-provided-to-us-by-our-buyers)

[There are sales reporting under Warehouse 847 but no inventory on hand (IOH). Why? [30](#there-are-sales-reporting-under-warehouse-847-but-no-inventory-on-hand-ioh.-why)](#there-are-sales-reporting-under-warehouse-847-but-no-inventory-on-hand-ioh.-why)

[Why aren’t we seeing our inventory in the E-commerce locations? [30](#why-arent-we-seeing-our-inventory-in-the-e-commerce-locations)](#why-arent-we-seeing-our-inventory-in-the-e-commerce-locations)

[Why don’t our E-Commerce inventory numbers look right? [30](#why-dont-our-e-commerce-inventory-numbers-look-right)](#why-dont-our-e-commerce-inventory-numbers-look-right)

[My product sells online. Why are the sales different from e-Commerce and Total Country? [31](#my-product-sells-online.-why-are-the-sales-different-from-e-commerce-and-total-country)](#my-product-sells-online.-why-are-the-sales-different-from-e-commerce-and-total-country)

[Why don’t I see my new item in the e-Commerce venues? [31](#why-dont-i-see-my-new-item-in-the-e-commerce-venues)](#why-dont-i-see-my-new-item-in-the-e-commerce-venues)

[Venue – Business Centers: [33](#venue-business-centers)](#venue-business-centers)

[Where are www.costcobusinessdelivery.com and https://www.costcobusinessdelivery.com/ [33](#where-are-www.costcobusinessdelivery.com-and-httpswww.costcobusinessdelivery.com)](#where-are-www.costcobusinessdelivery.com-and-httpswww.costcobusinessdelivery.com)

[https://www.costcobusinesscentre.ca/ sales tracked? [33](#httpswww.costcobusinesscentre.ca-sales-tracked)](#httpswww.costcobusinesscentre.ca-sales-tracked)

[Measures: [34](#measures)](#measures)

[Do you have a Measures Guide? [34](#do-you-have-a-measures-guide)](#do-you-have-a-measures-guide)

[Sales Measures Nuances: Unexpected Results [37](#sales-measures-nuances-unexpected-results)](#sales-measures-nuances-unexpected-results)

[How Costco Expresses Sales Measures [37](#how-costco-expresses-sales-measures)](#how-costco-expresses-sales-measures)

[I’m trying to look at promotions from a Unit perspective: Why don’t I find Net Units? [38](#im-trying-to-look-at-promotions-from-a-unit-perspective-why-dont-i-find-net-units)](#im-trying-to-look-at-promotions-from-a-unit-perspective-why-dont-i-find-net-units)

[Sales: Off vs. On Promo [38](#sales-off-vs.-on-promo)](#sales-off-vs.-on-promo)

[Post-Promotion Example [39](#post-promotion-example)](#post-promotion-example)

[What are rules for the Inventory On Hand measure to populate? [39](#what-are-rules-for-the-inventory-on-hand-measure-to-populate)](#what-are-rules-for-the-inventory-on-hand-measure-to-populate)

[What does “On Order” mean? [40](#what-does-on-order-mean)](#what-does-on-order-mean)

[Is “On Order” an additive number? [40](#is-on-order-an-additive-number)](#is-on-order-an-additive-number)

[What does “In Transit” reflect? [40](#what-does-in-transit-reflect)](#what-does-in-transit-reflect)

[What does “Quantity Received” reflect? [40](#what-does-quantity-received-reflect)](#what-does-quantity-received-reflect)

[Why isn’t OOS (Out of Stock) populating? [40](#why-isnt-oos-out-of-stock-populating)](#why-isnt-oos-out-of-stock-populating)

[Why is there no average promotion price at the SUBCATEGORY LEVEL? [41](#why-is-there-no-average-promotion-price-at-the-subcategory-level)](#why-is-there-no-average-promotion-price-at-the-subcategory-level)

[Does Costco have a Volume Sales measure available? [41](#does-costco-have-a-volume-sales-measure-available)](#does-costco-have-a-volume-sales-measure-available)

[Does Costco CRX sales data for deli show in pounds or units? [41](#does-costco-crx-sales-data-for-deli-show-in-pounds-or-units)](#does-costco-crx-sales-data-for-deli-show-in-pounds-or-units)

[What is Weeks of Supply (WOS)? [41](#what-is-weeks-of-supply-wos)](#what-is-weeks-of-supply-wos)

[How is the Weeks of Supply (WOS) measure calculated? [41](#how-is-the-weeks-of-supply-wos-measure-calculated)](#how-is-the-weeks-of-supply-wos-measure-calculated)

[Why isn’t the “Days Of Supply” (DOS) measure rendering in my report? [42](#why-isnt-the-days-of-supply-dos-measure-rendering-in-my-report)](#why-isnt-the-days-of-supply-dos-measure-rendering-in-my-report)

[What is the “Average Days of Supply” (ADOS) measure? How does it accurately populate with their requested time hierarchy? [42](#what-is-the-average-days-of-supply-ados-measure-how-does-it-accurately-populate-with-their-requested-time-hierarchy)](#what-is-the-average-days-of-supply-ados-measure-how-does-it-accurately-populate-with-their-requested-time-hierarchy)

[How can the system show positive Dollar Sales but negatives Unit Sales? [42](#how-can-the-system-show-positive-dollar-sales-but-negatives-unit-sales)](#how-can-the-system-show-positive-dollar-sales-but-negatives-unit-sales)

[Do we have visibility to Unit Returns from the Costco warehouse back to our DCs? [42](#do-we-have-visibility-to-unit-returns-from-the-costco-warehouse-back-to-our-dcs)](#do-we-have-visibility-to-unit-returns-from-the-costco-warehouse-back-to-our-dcs)

[For Unit Sales, some buildings return a null (blank) value, while other buildings return a 0 value. What is the difference between null versus 0? [43](#for-unit-sales-some-buildings-return-a-null-blank-value-while-other-buildings-return-a-0-value.-what-is-the-difference-between-null-versus-0)](#for-unit-sales-some-buildings-return-a-null-blank-value-while-other-buildings-return-a-0-value.-what-is-the-difference-between-null-versus-0)

[I can’t figure out which Dollars Per Warehouse measure is the right one to pick. What do they mean/how are they calculated? [43](#i-cant-figure-out-which-dollars-per-warehouse-measure-is-the-right-one-to-pick.-what-do-they-meanhow-are-they-calculated)](#i-cant-figure-out-which-dollars-per-warehouse-measure-is-the-right-one-to-pick.-what-do-they-meanhow-are-they-calculated)

[Dollars Per Warehouse Per Week (DPWPW): [45](#dollars-per-warehouse-per-week-dpwpw)](#dollars-per-warehouse-per-week-dpwpw)

[Why don’t my numbers POS-model sales match those in the Shopper Basket model? [46](#why-dont-my-numbers-pos-model-sales-match-those-in-the-shopper-basket-model)](#why-dont-my-numbers-pos-model-sales-match-those-in-the-shopper-basket-model)

[How are Membership Types broken out? [46](#how-are-membership-types-broken-out)](#how-are-membership-types-broken-out)

[Why doesn’t the Retailer Shopper measure vary by time or by Costco Member Tenure? [46](#why-doesnt-the-retailer-shopper-measure-vary-by-time-or-by-costco-member-tenure)](#why-doesnt-the-retailer-shopper-measure-vary-by-time-or-by-costco-member-tenure)

[Please note Promotions operate differently in US vs. Canada [47](#please-note-promotions-operate-differently-in-us-vs.-canada)](#please-note-promotions-operate-differently-in-us-vs.-canada)

[Key Promotions Abbreviations: [47](#key-promotions-abbreviations)](#key-promotions-abbreviations)

[What is an MVM? [47](#what-is-an-mvm)](#what-is-an-mvm)

[To what time period does MVM apply? [47](#to-what-time-period-does-mvm-apply)](#to-what-time-period-does-mvm-apply)

[What do they include? [48](#what-do-they-include)](#what-do-they-include)

[Where do they come from? [48](#where-do-they-come-from)](#where-do-they-come-from)

[What about Lift? [48](#what-about-lift)](#what-about-lift)

[What exactly is – and is not – included in the US Promotions data? [49](#what-exactly-is-and-is-not-included-in-the-us-promotions-data)](#what-exactly-is-and-is-not-included-in-the-us-promotions-data)

[What exactly is – and is not – included in the Canada Promotions data? [49](#what-exactly-is-and-is-not-included-in-the-canada-promotions-data)](#what-exactly-is-and-is-not-included-in-the-canada-promotions-data)

[How does the system set the MVM periods? Do we have to do it manually according to our promotional calendar? [50](#how-does-the-system-set-the-mvm-periods-do-we-have-to-do-it-manually-according-to-our-promotional-calendar)](#how-does-the-system-set-the-mvm-periods-do-we-have-to-do-it-manually-according-to-our-promotional-calendar)

[Does MVM period to date factor in holidays (when Costco is closed)? [51](#does-mvm-period-to-date-factor-in-holidays-when-costco-is-closed)](#does-mvm-period-to-date-factor-in-holidays-when-costco-is-closed)

[Does Dollar Sales (which equals gross sales before discounts) consider COMPS : [51](#does-dollar-sales-which-equals-gross-sales-before-discounts-consider-comps)](#does-dollar-sales-which-equals-gross-sales-before-discounts-consider-comps)

[Does promoted sales treat COMPS like it does TPDs/IRCs? [51](#does-promoted-sales-treat-comps-like-it-does-tpdsircs)](#does-promoted-sales-treat-comps-like-it-does-tpdsircs)

[How is Average Price Per Unit calculated? [51](#how-is-average-price-per-unit-calculated)](#how-is-average-price-per-unit-calculated)

[Does average price per unit account for COMPs (when the store matches another retailer’s pricing)? [51](#does-average-price-per-unit-account-for-comps-when-the-store-matches-another-retailers-pricing)](#does-average-price-per-unit-account-for-comps-when-the-store-matches-another-retailers-pricing)

[How are COMPS accounted for across all measures? (i.e. comparison between how TPDs/ IRCs are accounted for vs. COMPs) [51](#how-are-comps-accounted-for-across-all-measures-i.e.-comparison-between-how-tpds-ircs-are-accounted-for-vs.-comps)](#how-are-comps-accounted-for-across-all-measures-i.e.-comparison-between-how-tpds-ircs-are-accounted-for-vs.-comps)

[Are coupons Costco’s only promotion types in the US? Or are there other promotions besides coupons? [52](#are-coupons-costcos-only-promotion-types-in-the-us-or-are-there-other-promotions-besides-coupons)](#are-coupons-costcos-only-promotion-types-in-the-us-or-are-there-other-promotions-besides-coupons)

[Our APU Doesn’t Reflect our MVM! [52](#our-apu-doesnt-reflect-our-mvm)](#our-apu-doesnt-reflect-our-mvm)

[Use Promotions Measures to Analyze Programs [53](#use-promotions-measures-to-analyze-programs)](#use-promotions-measures-to-analyze-programs)

[Key Takeaways –INCLUDED in Promotions Data [53](#key-takeaways-included-in-promotions-data)](#key-takeaways-included-in-promotions-data)

[Key Takeaways –NOT INCLUDED in Promotions Data [53](#key-takeaways-not-included-in-promotions-data)](#key-takeaways-not-included-in-promotions-data)

[Does the data in the Canada database reflect Canadian currency or U.S. dollars? [54](#does-the-data-in-the-canada-database-reflect-canadian-currency-or-u.s.-dollars)](#does-the-data-in-the-canada-database-reflect-canadian-currency-or-u.s.-dollars)

[Data Security: [55](#data-security)](#data-security)

[What steps does Circana take to protect the privacy of its data? [55](#what-steps-does-circana-take-to-protect-the-privacy-of-its-data)](#what-steps-does-circana-take-to-protect-the-privacy-of-its-data)

[Assistance: [55](#assistance)](#assistance)

[Database usage help: [55](#database-usage-help)](#database-usage-help)

[Standard-format Ticket Topics enable efficient ticketing system volume management: [56](#standard-format-ticket-topics-enable-efficient-ticketing-system-volume-management)](#standard-format-ticket-topics-enable-efficient-ticketing-system-volume-management)

[Provide all relevant information up front (in the Ticket Description): [56](#provide-all-relevant-information-up-front-in-the-ticket-description)](#provide-all-relevant-information-up-front-in-the-ticket-description)

[Access: [57](#access)](#access)

[Can we get additional User Licenses? [57](#can-we-get-additional-user-licenses)](#can-we-get-additional-user-licenses)

[ID Assignment help: [57](#id-assignment-help)](#id-assignment-help)

[Contract-related help: [57](#contract-related-help)](#contract-related-help)

## Data Refresh:

## When is daily data updated? 

For Point-of-Sale data, Costco has 7 daily updates and 2 weekly updates for every country. By midafternoon local time (~2PM Central time for North America), each data refresh is usually loaded (though it does sometimes deliver earlier). We will post communications if we believe there will be a delay beyond 2PM.

- Daily data updates every day, with the one-day lag.

- Weekly time (i.e., for time periods like 1 week ending) is on Tuesday.

- Weekly VENUE is also on Tuesday local time for each country (e.g., 2 PM Central Time for North America).

- ITEM changes (i.e., new items are added, item mapping requests are processed) load on Saturday for each country.

For Shopper Data (FSP)-Level subscription clients, the Shopper Basket model loads should be refreshed by 10 AM the next morning Central time for North America. We will post communications if we believe there will be a delay beyond 3 PM.

## Are there scheduling capabilities available within Unify Costco Portal?

Yes, this is available under the Advanced Technology Package. Please open an “Other” type ticket for additional information and pricing.

## Can we use our internal Robotic Process Automation system/internal ”bot” to automate our regularly run (e.g., weekly, monthly) reports?

No, “bots” and automation of this kind are not permitted. To meet this automation requirement, we recommend upgrading your subscription to include the Advanced Technology Package. If interested in upgrading, please open an “Other” type ticket for additional information and pricing.

## Item:

## Why can’t I see my item in the database?

Three considerations must be met for the client to see the item(s):

- Item must be actively reporting in the database. Circana processes what Costco sends us. Until the item has orders, and that data is included in what’s transmitted by Costco to Circana, it won’t be visible.

- Item must be mapped to client’s IRI Parent Name and Master Vendor. Costco controls the Costco Vendor Name and Vendor Number. Circana controls the IRI parent and master.

- Item placed in a category to which your client subscribes.

<!-- -->

- Circana has no authority over where an item is placed.

- With Costco’s approval, clients can subscribe to an additional category (with a minimum fee).

First, please use the search function to find the item (under the All Items by Parent hierarchy) to confirm you have no visibility to the item. After confirming the item is missing, contact your Costco Champ(s) (dedicated account, first-level support team), providing the Costco item number only (we cannot research an item using its UPC). Once we’ve investigated, we will be able to advise you regarding next steps.

## Which Item Dimension hierarchy should I use when selecting my items?

Some background: Vendors contract by Costco category by program offering.

<img src="costco_faq_media/media/image2.png" style="width:4.36776in;height:1.63459in" />

## Point of Sale Data Hierarchy Overview

There are three different types of Item Hierarchy. Each type serves a purpose and each has its nuances.

<img src="costco_faq_media/media/image3.png" style="width:7.4in;height:3.41529in" />

There are two Point of Sale Item Hierarchies: All Items by Parent and All Items by Department-Parent.

<img src="costco_faq_media/media/image4.png" style="width:4.68203in;height:4.4375in" />

## All Items by Parent Hierarchy Overview

All Items by Parent Hierarchy: Client View vs. Total View:

<img src="costco_faq_media/media/image5.png" style="width:7.3in;height:2.53056in" />

All Items by Parent Hierarchy: Data-Pull Example

<img src="costco_faq_media/media/image6.png" style="width:7.3in;height:2.96042in" />

If your Parent-level total (pulled from this hierarchy) doesn’t match the sum of the items you have visibility to, the reason is generally that the Parent-level total includes categories not currently purchased.

## All Items by Department-Parent Hierarchy Overview: What does “Closed Subcategories or Segments” mean? 

Category Restrictions overview:

<img src="costco_faq_media/media/image7.png" style="width:7.36867in;height:3.60723in" />

## How does the Category Restrictions nesting work? 

Each level’s status determines the releasability of the levels beneath it. So…

<img src="costco_faq_media/media/image8.png" style="width:7.1in;height:2.79758in" />

## All Items by Department-Parent Hierarchy: Data-Pull Example

From the Department-Parent hierarchy, CLIENTS WILL NOT SEE items in closed subcategories or segments.

<img src="costco_faq_media/media/image9.png" style="width:7.3in;height:2.11458in" />

If you are not seeing an item you know you have visibility to, the likelihood is you pulled your item selections from the Department-Parent Hierarchy. On the left side of the example above, the red items are those you would not see, if you pulled items from the Department-Parent hierarchy.

## Shopper Basket (FSP) Data Hierarchies Overview

There are three additional Item hierarchies for Shopper Basket-level subscribers, which show include items.

<img src="costco_faq_media/media/image10.png" style="width:7.53111in;height:2.89583in" />

<img src="costco_faq_media/media/image11.png" style="width:7.4in;height:3.14126in" />

Unlike the All Items by Department-Parent hierarchy, these are <u>not</u> restricted based on open/closed status.

## Why do we have POS data reported under UPC Codes “99999” and “00000”? 

Background: Costco links each UPC to an item number in their system. Once the UPC scans at a warehouse location, the UPC will then show up in the data feed from Costco. It can take up to two weeks from its initial scan before a UPC shows up on the client's end.

UPC records report point-of-sale fact data (e.g., Dollar Sales, Unit Sales, and derived measures). The total (sum) value for each measure at the UPC level MUST match the data we receive from Costco at the ITEM level.

Conceptualization: The 0000s, 9999s, and 13000s are placeholders for data not sent to Circana, either because it’s not available at the UPC level, or because in the data Costco provides for us, it’s not tied to a specific UPC number.

Placeholder UPC Meanings: Inventory data is not available from Costco at the UPC level. The **UPC ‘999999999999999’** reports all inventory information as an aggregated total at the UPC level. For any additional measures not adding up exactly, those differences will also be corrected in the ‘9’ UPC.

The **UPC ‘000000000000000’** will be used when Circana does not receive a specific UPC record from Costco. The zero record will be used in the following cases:

- When the cashier manually keys the item number at the register instead of scanning the item.

- When a product is returned to a building not selling that item.

- When a product sells ONLY in e-Commerce. Sales via e-Commerce are not scanned at a register. As such, UPCs sold online but not in brick-and-mortar Warehouses are also represented by the 0000s UPC.

The **UPC ‘00130000000’**: in the event a cashier enters a department code (e.g., when the item can’t be scanned), this serves as a generic code/UPC.

Example 1:

- Inventory for Item number 54321 is 200 units.

- There are two “real” UPC numbers under item 54321.

<!-- -->

- 1234567890

- 1234567891

<!-- -->

- Since inventory data isn’t available at the UPC level, instead of the inventory data being allocated to 1234567890 and/or 1234567891, it gets assigned to UPC 9999999999.

Example 2:

- At the item level, we’re seeing \$100 of sales.

- \$80 of those sales tied to the actual UPC number (let’s call it UPC 1234567890)

- \$10 of those sales were keyed in by the cashier. That \$10 would show up against 0000000000

- There’s a remaining \$10 in sales, tied neither to UPC 1234567890 or 0000000000. Since the summed UPC level data must match the Item level data, that remaining \$10 in sales would get assigned to UPC 9999999999.

## Time:

## What is the Costco selling-week timeframe?

Monday – Sunday

## What is the fiscal year-to-date that is used within the Costco database?

It is based on Costco’s fiscal year, which begins on September 1st. The first week of each fiscal year

typically contains September 1st.

Periodicity:

## How are the comparison time periods determined?

> <img src="costco_faq_media/media/image12.png" style="width:4in;height:1.7907in" />

Comparison example: Four quarters in each year.

Comparison Year Ago calc: Current Quarter MINUS 4 Quarters (Q3, 2023) – (4 QUARTERS) = Q3, 2022

- Year Ago periodicity compares back one year.

- 2 Years Ago periodicity compares back two years.

- Example comparison time periods:

<!-- -->

- 2022 vs.

- Year Ago = 2021

- 2 Years Ago = 2020

Results vary by hierarchy used.

## **Example 1 – Current YTD and Calendar Month Hierarchies:**

Year-over-year, **Month** compares to prior year’s Month, and **Day** compares to prior year’s Day.

<img src="costco_faq_media/media/image13.png" style="width:6in;height:1.35569in" />

<img src="costco_faq_media/media/image14.png" style="width:4.1in;height:1.09049in" />

Example comparison time periods:

- July vs.

- Prior July

- Day 112 vs.

- Prior Day 112

- April 22 vs.

- Prior April 22

**Note**: Leap days compare to prior February 28th:

- February 29th 2020 vs.

- February 28th 2019

## Example 2 – Week Time Hierarchy:

Week hierarchies compare to-year, and then Day of Week year-to-year.

<img src="costco_faq_media/media/image15.png" style="width:6in;height:1.11739in" />

<img src="costco_faq_media/media/image16.png" style="width:4in;height:1.47222in" />

Week compares to prior weeks. Example comparison time periods:

- Week Ending 07-03-2022 vs.

- Week Ending 07-04-2021

Day of a week compares to prior day of the week. Example comparison time periods:

- The Tuesday of Week Ending 07-03-2022 vs.

- The Tuesday of Week Ending 07-04-2021

**Note**: some years will have a 53rd week. In those cases, the comparison week may not be the dates expected.

**Additional Nuance**: With the “latest weeks” time hierarchy, Prior Period periodicity measures (change and % change) do not populate because there is not a prior period in that time hierarchy, it is just the last x weeks. This is opposed to the “regular” time hierarchies (e.g., calendar month or calendar year), where there is a direct prior month or prior week or prior day.

## Launch Weeks Hierarchy:

Used in conjunction with New Item Launch Measures, this Time hierarchy equalizes time, allowing you to compare the launch performance of items launched at different times.

New Item Launch Measures:

- Week First Moved

- Item Launch Year

- Dollar Sales and Unit Sales\*

- Cum Dollar Sales and Cum Unit Sales\*

<img src="costco_faq_media/media/image17.png" style="width:2.20088in;height:1.73234in" />

**\*Nuances:**

- Launch Weeks and Launch Time must use Periodicity “Relative Time.”

- The New Item Launch Measures folder has its own set of Sales and Cum Sales because once any report uses New Item Launch Measures and/or Relative Time, only measures from the New Item Launch folder will work in the report.

## Venue – Warehouses:

## Do you have a warehouse list? Are we able to see sales by region filtered down by state, and then 

## filtered to the warehouse number?

WHs open and close with regularity. With that in mind, we created a dynamic report for each country, which you can run anytime for the most up-to-date information on demand.

<img src="costco_faq_media/media/image18.png" style="width:7.5in;height:1.58063in" />

<img src="costco_faq_media/media/image19.png" style="width:7.5in;height:2.6876in" />

For a personalized list (e.g., with fewer measures, or re-ordering member selections), “Save As” with a different name and edit your personal copy.

<img src="costco_faq_media/media/image20.png" style="width:1.86667in;height:1.87986in" />

## Why isn’t this warehouse reporting sales? My product is supposed to be in every warehouse.

The warehouse may have closed or may not be a selling location. We keep closed warehouses in the database for the data history.

## What is the meaning behind 1-3 in the status_attr column?

> 1 = no sales or inventory
>
> 2 = non-selling locations - inventory only
>
> 3 = selling physical locations

## I see two Warehouses, both listed as Selling Warehouses, in the same city, just a few miles apart. One returns null results for all measures, the other returns data. What’s going on here?

In Costco world, there is no such thing as a "close date." Usually we see the higher-number WH replacing the lower-number WH. When one WH replaces another, they will reflect the same 'open' date, so even when one store has replaced another, it will still list with a WH Status of 3, aka a Selling WH.

## Venue – Depots:

## Do we have list of which depots service which warehouse stores?

No. This information can change, and in addition, a WH can be serviced by multiple Depots.

For a simple list of Depots, you can run “(CRX 10) Costco Warehouse List.” Filter/create a rule as possible, e.g.: keep only non-selling WHs (where available, Status 2) or keep only WHs where name includes “depot.”

## What does “RCTR” signify in the Warehouse Name? Should these locations be counted towards 

## inventory?

These are return centers that Costco uses to send items back to manufacturers. Return Centers are like “reverse depots” – each warehouse location funnels to a specific return center. From those return centers, the items ship back to the manufacturer.

- They will report a status value of ‘2,’ indicating they are not selling locations.

- They can and do have inventory, but that inventory will not be sold – it will only be returned to the vendor of record.

> <img src="costco_faq_media/media/image21.png" style="width:2.4in;height:2.47742in" />

## What do “INN” and “DDC” signify in the Warehouse Name?

“INN” indicates an Innovel location; “DDC” indicates a Distribution Center.

- In 2020, Costco acquired a company called Innovel, whose locations supplemented Costco’s original depots for faster shipping.

- Costco will be changing all warehouse names from INN to DDC.

- Because they are distribution centers, these locations will not have sales – only quick ship inventory

> <img src="costco_faq_media/media/image22.png" style="width:2.1in;height:1.87772in" />

## What does “MDO” signify in the Warehouse Name?

MDO is a Costco internal acronym, standing for Market Delivery Operations, or the delivery of big and bulky items to customers’ homes. They are likely to be non-selling locations (Status = 2).

> <img src="costco_faq_media/media/image23.png" style="width:2.3in;height:2.22901in" />

## At what level can the depot number be pulled?

Depot number can be pulled at the item, day and warehouse level.

## Why do I see Depot Numbers reporting blank or zero?

The depot reports a blank or zero when item goes straight from manufacturer to the warehouse. The item may also be supplied by multiple depots for the specified time period.

## Venue – e-Commerce:

## Are e-Commerce locations included in Total US/Total Canada venues?

Yes, they are. The US and UK each have dedicated e-Commerce Regions.

In the US,

- All e-Commerce **sales** (Costco.com) are under WH 847.

- All other e-Comm locations have **inventory only**

> <img src="costco_faq_media/media/image24.png" style="width:4.64722in;height:2.2in" />

In the US, some e-Commerce sales will be delivered from Business Centers where available.

In the UK,

- All e-Comm **sales** (costco.co.uk) are under ECOMM WAREHOUSE.

- All other e-Comm locations have **inventory only**

> <img src="costco_faq_media/media/image25.png" style="width:4.86042in;height:2.04653in" />

Mexico and Canada do not have dedicated e-Commerce Regions.

In Mexico, e-Commerce (costco.com.mx) locations are within **Central Mexi**.

- All e-Comm **sales** are under WH 5305 BODEGA ECOM.

- All other e-Commerce locations have **inventory only**.

> <img src="costco_faq_media/media/image26.png" style="width:3.9in;height:2.06667in" />

In Canada, e-Commerce (costco.ca) locations are within the **Other Canada** Region.

- All e-Comm **sales** are under WH 894 CANADA ECOMMERCE.

- The remaining e-Comm locations have **inventory only**.

> <img src="costco_faq_media/media/image27.png" style="width:3.84028in;height:1.14653in" />

In Australia/New Zealand, e-Commerce is split across **two Regions**.

- In the Australia Region, the ECOMMERCE WAREHOUSE reports **sales**.

- In the Head Office Region, the remaining e-Comm WHs are depots with **inventory** only.

> <img src="costco_faq_media/media/image28.png" style="width:3.92708in;height:2.44028in" />

## Are Instacart sales reflected under e-Commerce?

There is no way to break out Instacart sales:

- The customer selects the items on the Instacart website.

- Instacart “shoppers” pick up the items in-store, so the purchase looks like any other in-store purchase.

## What about “Powered through Instacart” sales, e.g., sameday.costco.com?

As long as the website ends in “costco.com” or its equivalent in other countries, activity will be included in the e-Commerce numbers.

## Does e-Commerce reporting depend on where the item ships from?

When a vendor sells items on Costco.com, the inventory comes from Costco’s Distribution Center (DC) or is drop shipped (shipped directly to the end user). Both sales types are captured in the CRX database as E-Commerce sales.

## When do e-Commerce sales report in the database?

Sales are reported on the day the product ships, not the day the order is placed.

## Why don’t our E-Commerce Sales numbers match those provided to us by our buyer(s)?

Costco HQ can see when an item is ordered/requested by a shopper and likely is providing you that number. However, if they don't provide you with the numbers for orders canceled/not fulfilled, Circana numbers won’t match the buyer’s. An item is recorded in our data as sold when it ships, not when it is ordered.

## There are sales reporting under Warehouse 847 but no inventory on hand (IOH). Why? 

## Why aren’t we seeing our inventory in the E-commerce locations? 

## Why don’t our E-Commerce inventory numbers look right?

The E-Commerce Warehouse shows ALL sales based on online order fulfilment – that is how the data comes from Costco. E-Comm typically gets inventory allocated at the time it is shipped, so for this reason, you will probably not see large IOH amounts in E-Commerce.

- Products are shipped from all the locations shown under that region.

- All other locations in the e-Commerce region will only show Inventory.

- The inventory levels will change based on the shipment.

- IOH will go down based on order fulfillment.

- Quantity received will go up at each depot as more product arrives.

- To see sales and IOH together, it is best to run your report using the e-Commerce region level.

## My product sells online. Why are the sales different from e-Commerce and Total Country?

Returns could be responsible for the difference in unit sales between e-Commerce and Total Country. Items that were purchased online can be returned to a warehouse despite only being available online to purchase. The sales in the system are net sales.

## Why don’t I see my new item in the e-Commerce venues?

There are a couple of reasons you may not see your item yet:

> Reason 1: It could be a new item.
>
> There are three main criteria for clients to have visibility to items, regardless of which Venue the
>
> items sell from:

- The item must be actively reporting in the database.

- The item must be mapped to the client’s IRI Parent Name.

- The item must be reporting under a category for which the client is contracted.

> Reason 2: Items are set up differently In-Warehouse vs. E-commerce.

- **In-Warehouse:** Many items purchased in warehouses have a single Costco item number with multiple variants/UPCs nested underneath. See Scenarios 1A and 1B, below, for two examples.

- E-Commerce: For online items, there must be a unique item number for each variant (color/ size/ style combination), so the Costco Order Management (OMS) and Warehouse Management (WMS) Systems can pick up and ship by item number. See Scenario 2, below, for an example.

**Illustration Example: One Jacket (Jacket A), which comes in 30 Size/Color Variations**

<img src="costco_faq_media/media/image29.png" style="width:7.5in;height:3.36698in" />

## Venue – Business Centers:

## Where are www.costcobusinessdelivery.com and https://www.costcobusinessdelivery.com/

## https://www.costcobusinesscentre.ca/ sales tracked? 

The sales sold online from the **Business Center URLs** will be reporting under the Business Center Venue, and not under e-Commerce.

- All Business Center Sales are tracked at the Business Center locations.

- These sales are NOT considered e-Commerce sales.

- Business used to use fax machines in the old days to put in their order for pick-up or delivery from Costco Business Centers. Now that is done through their business center website, which is why it is tracked there and not under E-Comm.

- Some Business Centers help deliver Costco’s 2-day grocery business. If the order was placed on Costco.com for 2-day grocery those sales will be included in Costco’s E-Comm sales. So, the nuance is it is based on **where** the order is placed not where the inventory was delivered from.

## Measures:

## Do you have a Measures Guide? 

Yes. For Point of Sale data (subscription levels: Items Only and Category Totals), there is a single Measures Guide, with one tab per country, which is located in the file cabinet. It is an excel file, filterable by:

- Measure Folder

- Measure Name

- Measure Type

- Definition

- Calculation

- Display Level

- Nuances

Always note the “Display Level” and “Nuances” columns. Any time a measure doesn't behave as you’d expect, check there, as these columns often provide the “why.”<img src="costco_faq_media/media/image30.png" style="width:5.27556in;height:2.3in" />

Additionally, it contains a few tabs on select topics, which go into more granular detail than the main tabs would allow.

<img src="costco_faq_media/media/image31.png" style="width:5.8in;height:0.21215in" />

We also have a separate Measures Guide for Shopper Basket data. Because of the additional level of complexity, this Measures Guide has more columns, broken down into sections:

- Level of Visibility: Competitive Visibility or Category Only/Own Items Only?

- Foldering

<!-- -->

- Measure Folder

- Sub Folder – Lvl 1

- Sup Folder – Lvl 2

<!-- -->

- Measure Name & Description

<!-- -->

- Measure Name

- Description

<!-- -->

- Dimension Requirements

<!-- -->

- Buyer Related

- Trip Related

- Cust Aggs Allowed

- Periodicity Allowed

- Requires Offset Time/ Pre Period Offset

- Requires Product 2 Dimension

- Requires Product 3 Dimension

- Requires Product 4 Dimension

- Requires New To Lost To

- Audience Measure

- Requires Causal Dimension

- Format Mask

<img src="costco_faq_media/media/image32.emf" style="width:7.3in;height:3.09583in" />

<img src="costco_faq_media/media/image33.emf" style="width:6.46944in;height:3.4in" />

<img src="costco_faq_media/media/image34.emf" style="width:7.3in;height:2.74167in" />

## Sales Measures Nuances: Unexpected Results

“If Net Dollars is net of Coupons and Returns, how are my Net Dollars higher than my Dollar Sales?”

“I thought Coupon Dollars are expressed as a negative. How can my Coupon Dollars be positive?”

Sales Measures Don’t Always Add Up as One Intuitively Expects. Always refer to the Measures Guide for their definitions and calculations, as it’s imperative to understand how Costco expresses their measures.

## How Costco Expresses Sales Measures

**Dollar** Sales is usually:

1 positive (Gross Dollars) +

1 negative (Refund Dollars, usually reflected as negative).

**Net Dollars** is usually:

1 positive (Gross Dollars) +

2 negatives (Coupon Dollars and Refund Dollars, both usually reflected as negative).

<img src="costco_faq_media/media/image35.png" style="width:4.1in;height:1.37143in" />

<img src="costco_faq_media/media/image36.png" style="width:7.4in;height:0.80919in" />

Therefore, in usual circumstances:

**Net Dollars** (1 positive + 2 negatives) is lower than **Dollar Sales** (1 positive + only 1 negative).

## I’m trying to look at promotions from a Unit perspective: Why don’t I find Net Units?

The grids above outlines Dollar Sales vs. Net Dollars. The difference between the two measures is the Discount. While Net Dollars reflect the discount <u>rate</u>, Units are not expressed with a discount rate per se, Net Dollars does not have a Unit measure equivalent. Use Unit Sales.

## Sales: Off vs. On Promo

During a promo, Sales generally spike. After the promotion, Returns often spike. Sometimes, returns exceed new purchases post-promo:

- When people BUY an item on promo,

  - Gross Dollars are a positive.

  - Coupon dollars are a negative.

- When people <u>RETURN</u> an item purchased on promo,

  - Gross Dollars for a return are negative.

  - Coupon dollars for a return are a positive.

## Post-Promotion Example

<img src="costco_faq_media/media/image37.png" style="width:6.3in;height:1.31529in" />

<img src="costco_faq_media/media/image38.png" style="width:7in;height:1.13992in" />

This is how we can end up with a Net Dollars higher than the Dollar Sales.

## What are rules for the Inventory On Hand measure to populate? 

When reporting above day level, Inventory On Hand reports the value for the last day of the selected time period.

IOH will not populate for the time period Current Week to Date if the last day of the Current Week to Date time period (always a Sunday) has not loaded yet.

When the last day of that time period has not loaded, the measure will not return data because Inventory On Hand is a non-additive measure.

## What does “On Order” mean?

On Order reflects product at the supplier (not received at the depot or location).

## Is “On Order” an additive number? 

On order refers to quantity that Costco has on order to either the warehouse or depot. It is a static number that reflects the quantity that is on order for that day at each location. Do not add quantities for week to get “on order.” It’s a static daily number.

## What does “In Transit” reflect? 

In Transit reflects quantity received at the depot and shipped to location (moving from the depot to the warehouse).

## What does “Quantity Received” reflect? 

Quantity Received reflects product that has been received at the depot or location.

## Why isn’t OOS (Out of Stock) populating? 

OOS doesn't work for custom aggregates. The measure is primarily meant to be used on an item basis.

## Why is there no average promotion price at the SUBCATEGORY LEVEL?

Coupon Value, Average Promoted Price, and Percent Discount only populate at the ITEM level. All other coupon measures populate at all levels above UPC.

## Does Costco have a Volume Sales measure available?

No, Costco does not measure/track volume data – it isn’t coded in their system – so Volume Sales is not available.

## Does Costco CRX sales data for deli show in pounds or units? 

Random weight products are usually measured pounds, but it is best to verify for each product.

## What is Weeks of Supply (WOS)?

It’s a calculation of how long current inventory levels will last.

## How is the Weeks of Supply (WOS) measure calculated? 

**Calculations vary based on the** time **hierarchy used**. Please see the “WOS Details” tab in the Measures Guide, or the separate file titled “Costco WOS Overview” for a more detailed explanation.

<img src="costco_faq_media/media/image39.png" style="width:6.7in;height:2.40708in" />

## Why isn’t the “Days Of Supply” (DOS) measure rendering in my report?

Previous week and latest 1-week periods cannot be used to pull the DOS. To properly pull DOS, select the calendar week time hierarchy, where the previous days are visible when you drill into the time hierarchy. They DO NOT need to be selected in the report for the measure to work, but must be within the hierarchy.

<img src="costco_faq_media/media/image40.png" style="width:4.50069in;height:1.66042in" />

## What is the “Average Days of Supply” (ADOS) measure? How does it accurately populate with their requested time hierarchy?

ADOS is calculated using the current day’s inventory divided by the average sales over the previous 6 days. To run this properly, use a time hierarchy that includes more than 7 days, such as time calendar week or latest 4 weeks. Do not use latest 1 week – this time period will not work.

## How can the system show positive Dollar Sales but negatives Unit Sales?

The unit sales measure is unit sales net of returns, meaning that returned items are part of the calculation.

## Do we have visibility to Unit Returns from the Costco warehouse back to our DCs?

No. The system captures what is scanned out, but we cannot determine if the item is returned to the DC or destroyed. It depends only on the snapshot of the EOD inventory return.

We cannot tell how many of the returns were re-stocked versus returned to the vendor.

The purpose of the non-sellable inventory (NSI) measure is for companies with high cost/limited items. Example: where a Displayed TV is NSI, but they have no boxed TVs on the floor.

## For Unit Sales, some buildings return a null (blank) value, while other buildings return a 0 value. What is the difference between null versus 0? 

These indicators are based on Costco’s transmission file.

- For product considered active but reporting no Unit Sales within the given time period: the system returns a 0.

- For product considered inactive during given time period: no data will be included in the transmission file received from Costco, so the system returns a null.

## I can’t figure out which Dollars Per Warehouse measure is the right one to pick. What do they mean/how are they calculated? 

First, an overview of the two measures:

<img src="costco_faq_media/media/image41.png" style="width:5.1in;height:3.48299in" />

**Some further** explanation**:**

Average Dollar Sales Per Warehouse Selling

In the below example, for the time period L52 Weeks

- Take the \$ Sales for that time period (\$1,803,092,972.68),

- and divide it by the number of warehouses selling the item during that time period (501).

- The measure yields a value of **\$3,598,987.97**.

**Please note:** as time periods get larger (i.e., including more weeks vs. fewer), the Warehouses Selling

during the time period usually grows, becoming less representative of what the weekly WH Selling number

is. In the below example, the item is selling in 33 WHs for the L52. It is possible that one week, the item

sold in 16 WHs, and another week, the item sold in 17 entirely different WHs. Thus, the total number of

WHs selling over the course of a full year would be 33, but the weekly WHs selling was 16.5.

<img src="costco_faq_media/media/image42.png" style="width:7.1in;height:3.59624in" />

## Dollars Per Warehouse Per Week (DPWPW):

In the below example, for the time period L52 Weeks

- Take the \$ Sales for that time period (\$1,803,092,972.68)

- Sum up the WHs selling for each of the individual 52 weeks (see magenta highlighted: it sums to 20,698).

- Divide that \$ Sales by the number of warehouses selling the item during that time period.

- The measure yields a value of **\$87,114.36**.

View the DPWPW for each individual week. The resulting number of this measure (\$87K) is far more representative of what dollar sales is for this item on a weekly basis that the prior measure, which yielded an Average Dollar Sales Per Warehouse Selling of nearly \$3.5 Million.

<img src="costco_faq_media/media/image43.png" style="width:6.5in;height:3.34666in" />

## Why don’t my numbers POS-model sales match those in the Shopper Basket model?

The POS model includes returns, while the Shopper Basket model does not.

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 22%" />
<col style="width: 56%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Model</strong></th>
<th style="text-align: center;"><strong>Measure</strong></th>
<th style="text-align: center;"><strong>Definition</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>POS Model</strong></td>
<td style="text-align: center;">Net Dollars</td>
<td style="text-align: center;"><p>Gross Dollar Sales,</p>
<p><u>Net</u> Coupons (Discounts) <strong>and Returns</strong></p></td>
</tr>
<tr>
<td style="text-align: center;"><strong>SB Model</strong></td>
<td style="text-align: center;">Dollar Sales</td>
<td style="text-align: center;"><p>Gross (all) Dollar Sales,</p>
<p><u>Net</u> Discounts</p></td>
</tr>
<tr>
<td><strong>POS Model</strong></td>
<td style="text-align: center;">Gross Dollars</td>
<td style="text-align: center;"><p>All Dollar Sales,</p>
<p><u>Including</u> Discounts <strong>and Returns</strong></p></td>
</tr>
<tr>
<td style="text-align: center;"><strong>SB Model</strong></td>
<td style="text-align: center;">Gross Dollars</td>
<td style="text-align: center;"><p>All Dollar Sales,</p>
<p><u>Including</u> Discounts</p></td>
</tr>
</tbody>
</table>

## How are Membership Types broken out?

There are three types of accounts.

1.  Goldstar, which is comprised of two tiers:

<!-- -->

1)  Business – Regular

2)  Business – Executive

<!-- -->

2.  Business, which is comprised of two tiers:

<!-- -->

3)  Business – Regular

4)  Business – Executive

<!-- -->

3.  Employee

We receive the data for Goldstar and Business Accounts only as aggregated numbers; we cannot break out data by the Regular vs. Executive tiers as they are split across the account types.

## Why doesn’t the Retailer Shopper measure vary by time or by Costco Member Tenure? 

The Retailer Shopper Measure is not dynamic by member tenure. The measure is simply not designed to work that way -- it does only one thing: reporting total shoppers in universe.

<img src="costco_faq_media/media/image44.png" style="width:7.3in;height:1.92778in" />

Promotions/Coupons:

## <u>Please note Promotions operate differently in US vs. Canada</u>

## Key Promotions Abbreviations:

- MVM = Multi-Vendor Mailer

- IRCs = Instant Rebate Coupon

- TPRs= Temporary Price Reductions

## What is an MVM?

MVMs are Multi-Vendor Mailers: the monthly coupon book sent to U.S.-based Costco members. MVMs are in the US only.

## To what time period does MVM apply?

Each MVM time period in the U.S. database correspond to dates during which Costco is running the promotion. MVM promotional period dates are provided by Costco, and are applicable only within the United States. The dates are automatically populated into the Costco CRX database.

<img src="costco_faq_media/media/image45.png" style="width:3.72986in;height:3.66736in" />

## What do they include? 

The full MVM date range, whether or not:

- Costco was open (e.g., closed for holiday).

- Your product was on promo for full MVM time period.

## Where do they come from? 

Costco provides dates, which are automatically populated in the Costco CRX database.

## What about Lift? 

CRX database does not include baseline non-promoted measures. To proxy lift, compare sales for one MVM period versus the prior period or year ago (depending on your promotional calendar).

## What exactly is – and is not – included in the US Promotions data?

The US only has Instant Redeemable Coupons (IRCs) (the physical coupon is not required and the price reduction is automatically taken off at the register).

**Included:**

- MVMs, which are IRCs (the physical coupon is not required, and the price reduction is automatically

- taken off at the register).

- Both National IRCs and Regional IRCs.

- Items can be linked to a National MVM but not pictured in the mailer.

\* Note: MVM Promotions data is only available for brick-and-mortar warehouses. We do not receive the coupon data for Costco.com.

**Not Included:**

- Price changes from markdowns, buyers covering costs, or matching competitive price:

- Temporary Price Reductions (TPRs) and Comps are not considered to be IRCs and therefore not included in the Promotions data.

- Non-IRC-related Price changes shown at the shelf are reflected in the current “Average Price per Unit;” differences in pricing can be seen at the warehouse level.

## What exactly is – and is not – included in the Canada Promotions data?

Costco Canada has 3 different types of coupons:

- Executive Mailers: these go out to Executive members only. In order for the discount to be taken off, the physical coupon must be presented to the cashier.

- Any regular, printed coupons (e.g., Summer Savings booklet): the coupon discount is set up to automatically deduct without the shopper presenting the physical coupon.

- Costco Canada Temporary Price Reductions (TPDs): these are not printed coupons; they are automatically deducted at the register.

**Included:**

- Any regular, printed coupons (e.g., Summer Savings booklet): The coupon discount is set up to automatically deduct without shopper presenting the physical coupon. Includes Regional IRCs

- Costco Canada TPDs (temporary price discount): These are not printed coupons; they are automatically deducted at the register.

**Not Included:**

- Executive Mailers: Sent to Executive members only. For the discount to be taken off, the physical coupon must be presented to the cashier.

- Price changes from the buyer to cover costs or to match competitive pricing.

- Price changes shown at the shelf. These are reflected in the current ‘Average Price per Unit;’ differences in pricing can be seen at the warehouse level.

## How does the system set the MVM periods? Do we have to do it manually according to our promotional calendar?

MVM promotional period dates are provided by Costco, and are applicable only within the United States. The dates are automatically populated into the Costco CRX database and include the full MVM period, whether or not your product was on promotion for the full MVM time period.

## Does MVM period to date factor in holidays (when Costco is closed)?

The period includes the full date range of the MVM, whether Costco was open or closed.

## Does Dollar Sales (which equals gross sales before discounts) consider COMPS :

Yes.

## Does promoted sales treat COMPS like it does TPDs/IRCs? 

No.

## How is Average Price Per Unit calculated? 

Average price per unit = dollar sales divided by unit sales.

## Does average price per unit account for COMPs (when the store matches another retailer’s pricing)?

Yes. Reports built to include the Average Price measure will reflect a decline in the price offering if a price match were granted.

## How are COMPS accounted for across all measures? (i.e. comparison between how TPDs/ IRCs are accounted for vs. COMPs)

The TPDs/IRCs are only included in the Promotion Measures and the COMPs are not included in the Promotion Measures (because it was not a promotion, just a price reduction).

## Are coupons Costco’s only promotion types in the US? Or are there other promotions besides coupons?

Costco U.S. only has IRC coupons, meaning the price reduction is automatically taken off at the register without requiring the physical coupon. IRC coupon data IS included.

- Both national and regional IRCs are included.

- Items can be linked to a national MVM but not pictured in the MVM. This data IS included.

- Price changes from the buyer to cover costs or to match competitive pricing are not considered to be IRCs and therefore not included in the coupon data.

- Price changes shown at the shelf are reflected in the current average price per unit and differences in pricing can be seen at the warehouse level.

## Our APU Doesn’t Reflect our MVM! 

“We ran an MVM promotion (\$3.50 discount) at Costco during the weeks ending 6/25 through 7/23, but we’re not seeing them reflected in the Average Price per Unit. Why not?”

<img src="costco_faq_media/media/image46.png" style="width:2.8691in;height:2.33333in" />

The answer goes back to the importance of understanding how Costco expresses their measures

## Use Promotions Measures to Analyze Programs

<img src="costco_faq_media/media/image47.png" style="width:2.59973in;height:2.11458in" /> <img src="costco_faq_media/media/image48.png" style="width:4in;height:2.33345in" />

The discount is reflected in the Average Coupon Value and Average Promoted Price, which is why the APU measure does <u>not</u> reflect it.

## Key Takeaways –INCLUDED in Promotions Data

<img src="costco_faq_media/media/image49.png" style="width:7in;height:2.5532in" />

## Key Takeaways –NOT INCLUDED in Promotions Data

<img src="costco_faq_media/media/image50.png" style="width:7in;height:2.30254in" />

**ALSO: USE** PROMOTIONS **MEASURES** when analyzing your promos.

Currency:

## Does the data in the Canada database reflect Canadian currency or U.S. dollars?

The Canada database reflects the Canadian currency. Should you wish to see US dollars, add in the Currency dimension, which will allow you to select USD currency.

## Data Security:

## What steps does Circana take to protect the privacy of its data?

We take privacy extremely seriously. For more than 35 years, we’ve built a culture that’s focused on continuously transforming our data into usable and timely information for our customers while upholding stringent policies and procedures to protect the privacy of our data. We have strong controls in place to ensure our data — which is anonymized — is secure, and we review our controls regularly.

## Assistance:

## Database usage help: 

Circana's Retail Gateways service model is that clients should always begin with their dedicated account team (except for ID/PW requests and Item inquiries). They assist with things like first-level investigations and report building. Starting with them will ensure the fastest routing and resolution of your issues. They will be able to:

- Answer questions about the CostcoCRX database and reporting.

- Help you investigate missing items/item mapping, diagnose data issues.

If you don’t know who your account service representative is, open a support ticket (“Other” category) and we will connect you.

When indicated, your client team will escalate your issue to the Ticketing System located within Unify+. From the Global Navigation Menu, under Help, click [Support Ticket](https://advantage.iriworldwide.com/unify-CRX/support/ticket-create), then click Create New Ticket.

<img src="costco_faq_media/media/image51.png" style="width:2.5in;height:1.625in" />

## Standard-format Ticket Topics enable efficient ticketing system volume management: 

COUNTRY \> CLIENT \> ISSUE. Examples are:

<img src="costco_faq_media/media/image52.jpeg" style="width:2.79861in;height:0.25in" />

<img src="costco_faq_media/media/image53.jpeg" style="width:4.34722in;height:0.24306in" />

<img src="costco_faq_media/media/image54.jpeg" style="width:3.04861in;height:0.24306in" />

Titling tickets this way helps us identify the client/topic, prioritize, and route to the right person to handle. Our records and models are country-specific (US/Canada/Mexico/UK/Australia and New Zealand), so indicating these up front helps us quickly determine where to look up further information if required.

## Provide all relevant information up front (in the Ticket Description): 

Reducing time spent per inquiry enables faster resolutions, allowing maximum responsiveness and minimum frustration.

By providing all the requisite information up front you help eliminate time spent looking up additional information needed to diagnose an issue, messaging back and forth with follow-up questions, etc.

## Access:

## Can we get additional User Licenses?

IDs are not shareable per Costco policy but are easily transferable and assignable. Incremental IDs are also available for purchase. Note: Violation of ID sharing policy can result in Costco Database access contract cancellation.

## ID Assignment help: 

For issues like ID assignments/reassignments submit an “Access” type ticket within Unify+.

## Contract-related help: 

Please open an “Other” type ticket for:

- Contract-related issues (including renewals, invoices, and PO requirements).

- Mergers and acquisitions.

- Suspensions and cancellations.

Copyright© 2023 Circana, Inc. and Circana Group, L.P. (“Circana”). All rights reserved. Circana, the Circana logo, and the names of Circana products and services referenced herein are either trademarks or registered trademarks of Circana. All other trademarks are the property of their respective owners.
