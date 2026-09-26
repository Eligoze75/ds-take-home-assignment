with lines as (

    select * from {{ ref('itemized_purchase_orders') }}

),

pos as (

    select * from {{ ref('purchase_orders') }}

),

items as (

    select * from {{ ref('items') }}

),

joined as (

    select
        lines.item_id,
        lines.unit_price_paid,
        pos.order_date
    from lines
    inner join pos   on lines.po_number = pos.po_number
    inner join items on lines.item_id   = items.item_id

),

aggregated as (

    select
        item_id,
        count(*)                                                       as purchase_frequency,
        min(order_date)                                                as earliest_purchase_date,
        max(order_date)                                                as latest_purchase_date,
        percentile_cont(0.25) within group (order by unit_price_paid)  as price_p25,
        percentile_cont(0.50) within group (order by unit_price_paid)  as price_p50,
        percentile_cont(0.75) within group (order by unit_price_paid)  as price_p75,
        percentile_cont(0.90) within group (order by unit_price_paid)  as price_p90
    from joined
    group by item_id

)

select * from aggregated
order by item_id
