select
    vendor_id,
    max(vendor_name)  as vendor_name,
    min(order_date)   as first_order_date,
    max(order_date)   as last_order_date,
    count(*)          as po_count
from {{ ref('purchase_orders') }}
group by vendor_id
