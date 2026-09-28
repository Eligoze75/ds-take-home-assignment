select
    po_number,
    item_id,
    category,
    unit_of_measure,
    manufacturer_name,
    order_date,
    customer_id,
    vendor_id,
    quantity_ordered,
    unit_price_paid,
    total_amount,
    status
from {{ ref('fct_purchase_line') }}
where customer_id = 'CUST-A'
