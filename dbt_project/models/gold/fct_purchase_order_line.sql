with raw_lines as (

    select distinct
        po_number,
        item_id,
        quantity_ordered,
        unit_price_paid
    from {{ ref('itemized_purchase_orders') }}

),

line_totals as (

    select
        po_number,
        sum(quantity_ordered * unit_price_paid) as lines_total_amount
    from raw_lines
    where unit_price_paid is not null
    group by po_number

),

gaps as (

    select
        purchase_orders.po_number,
        line_totals.lines_total_amount - purchase_orders.total_amount as gap
    from {{ ref('purchase_orders') }} as purchase_orders
    inner join line_totals
        on purchase_orders.po_number = line_totals.po_number
    where abs(line_totals.lines_total_amount - purchase_orders.total_amount) > 0.02

),

seen_once as (

    select item_id
    from raw_lines
    group by item_id
    having count(*) = 1

),

-- A line that accounts for the whole header gap, appears once, and has no list price.
excluded_lines as (

    select
        raw_lines.po_number,
        raw_lines.item_id,
        raw_lines.quantity_ordered,
        raw_lines.unit_price_paid
    from gaps
    inner join raw_lines
        on gaps.po_number = raw_lines.po_number
        and abs(raw_lines.quantity_ordered * raw_lines.unit_price_paid - gaps.gap) <= 0.02
    inner join seen_once
        on raw_lines.item_id = seen_once.item_id
    where not exists (
        select 1
        from {{ ref('item_pricing') }} as item_pricing
        where item_pricing.item_id = raw_lines.item_id
    )

),

lines as (

    select
        raw_lines.po_number,
        raw_lines.item_id,
        raw_lines.quantity_ordered,
        raw_lines.unit_price_paid
    from raw_lines
    where not exists (
        select 1
        from excluded_lines
        where excluded_lines.po_number = raw_lines.po_number
            and excluded_lines.item_id = raw_lines.item_id
            and excluded_lines.quantity_ordered = raw_lines.quantity_ordered
            and excluded_lines.unit_price_paid = raw_lines.unit_price_paid
    )

),

purchase_orders as (

    select * from {{ ref('purchase_orders') }}

),

joined as (

    select
        lines.po_number,
        purchase_orders.customer_id,
        purchase_orders.vendor_id,
        purchase_orders.order_date,
        purchase_orders.status,
        lines.item_id,
        lines.quantity_ordered,
        lines.unit_price_paid,
        lines.quantity_ordered * lines.unit_price_paid as extended_amount
    from lines
    inner join purchase_orders
        on lines.po_number = purchase_orders.po_number

)

select * from joined
