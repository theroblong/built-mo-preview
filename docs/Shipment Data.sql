SELECT
    t.id AS transaction_id,
    t.tranid AS SalesOrdersID,
    CAST(t.actualshipdate AS DATE) AS ship_date,
    t.shippingaddress AS shippingaddressID,
    t.custbody1 AS bars_per_order_qc,
    t.custbody_bb_pallets_shipped AS total_pallets_shipped,
    t.status AS StatusID,
    ts.fullname AS SalesOrderStatus,

    tl.custcolexp_unit,
    tl.custcolexp_qty,
    tl.custcol_sps_uom_qty_converted,
    tl.custcol_sps_tpqty,
    tl.custcol_sps_tp_order_qty,

    c.id AS customer_id,
    c.companyname AS customer_name,

    ABS(tl.quantity) AS TotalCases,

    CASE
        WHEN i.fullname = 'Promotional Allowance' THEN -ABS(tl.netamount)
        ELSE ABS(tl.netamount)
    END AS Amount,

    ABS(tl.quantity * i.custitem_bars) AS TotalBars,

    CASE
        WHEN i.fullname = 'Promotional Allowance' THEN -ABS(tl.netamount)
        ELSE ABS(tl.netamount)
    END
    / NULLIF(
        ABS(tl.quantity * i.custitem_bars),
        0
    ) AS CostPerBar,

    tl.custcol_sps_upccasecode,
    tl.custcol_sps_gtin,
    tl.quantitybilled,
    tl.quantityshiprecv,

    i.id AS item_id,
    i.itemid AS item_code,
    i.fullname AS item_name,
    i.custitem1 AS flavor,

    COALESCE(
        i.displayname,
        i.description,
        i.purchasedescription
    ) AS ItemDescription,

    i.itemtype,

    cc.name AS customer_category,
    cc.id AS customer_category_id,

    s.addr1,
    s.addr2,
    s.addr3,
    s.city,
    s.state,
    s.zip

FROM ns2.transactionLine tl

INNER JOIN ns2.[transaction] t
    ON t.id = tl.[transaction]

LEFT JOIN Source_NetSuite.ns2.Customer c
    ON c.id = t.entity

INNER JOIN ns2.item i
    ON i.id = tl.item

LEFT JOIN Source_NetSuite.ns2.customerCategory cc
    ON cc.id = c.category

INNER JOIN ns2.transactionstatus ts
    ON ts.id = t.status

INNER JOIN ns2.transactionShippingAddress s
    ON s.nkey = t.shippingaddress

WHERE ts.fullname = 'Sales Order : Billed'
  AND c.id IN (
        774062,
        11150382,
        940717,
        14396850
    ) -- Data Dark customers, all historical shipments
 AND tl.netamount IS NOT NULL; -- excludes loose bars, direct labor, inventory parts, boxes, wrappers, etc.