-- models/gold/item_popularity.sql
WITH recent_orders AS (
    SELECT
        ipo.item_id,
        SUM(ipo.quantity_ordered) quantity_60d
    FROM {{ ref('itemized_purchase_orders') }} ipo
    LEFT JOIN {{ ref('purchase_orders') }} po
        ON ipo.po_number = po.po_number
    WHERE po.order_date >= (
        SELECT MAX(order_date)
        FROM {{ ref('purchase_orders') }}
    ) - INTERVAL '60 days'
    GROUP BY 1
)

SELECT
    i.item_id,
    i.category,
    i.manufacturer_name,
    COALESCE(r.quantity_60d, 0) quantity_60d
FROM {{ ref('dim_item') }} i
LEFT JOIN recent_orders r 
    ON i.item_id = r.item_id