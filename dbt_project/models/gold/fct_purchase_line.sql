select
    lines.po_number,
    lines.item_id,
    items.category,
    items.unit_of_measure,
    items.manufacturer_name,
    lines.order_date,
    lines.customer_id,
    lines.vendor_id,
    lines.quantity_ordered,
    lines.unit_price_paid,
    purchase_orders.total_amount,
    lines.status
from {{ ref('fct_purchase_order_line') }} as lines
inner join {{ ref('purchase_orders') }} as purchase_orders
    on lines.po_number = purchase_orders.po_number
left join {{ ref('dim_item') }} as items
    on lines.item_id = items.item_id
