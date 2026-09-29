-- Company A items for the timing question.
-- Frequent: on more orders than 90% of the catalog.
-- Eligible: bought in at least 8 distinct months, spanning at least a year.
-- Spend: total dollars above the median item. The expensive tail does not set this bar.
-- Cancelled orders are excluded. Both cutoffs are computed on every remaining item, then the three rules are applied.

with lines as (

    select
        po_number,
        item_id,
        category,
        unit_of_measure,
        order_date,
        quantity_ordered,
        unit_price_paid
    from {{ ref('fct_company_a_purchase_line') }}
    where status <> 'Cancelled'

),

company_orders as (

    select count(distinct po_number) as n_company_orders
    from lines

),

items as (

    select
        item_id,
        any_value(category) as category,
        any_value(unit_of_measure) as unit_of_measure,
        count(distinct po_number) as n_orders,
        count(distinct date_trunc('month', order_date)) as n_months,
        min(order_date) as first_order,
        max(order_date) as last_order,
        sum(quantity_ordered * unit_price_paid) as total_spend
    from lines
    group by item_id

),

scored as (

    select
        items.item_id,
        items.category,
        items.unit_of_measure,
        items.n_orders,
        cast(items.n_orders as double) / company_orders.n_company_orders as attachment,
        items.n_months,
        items.first_order,
        items.last_order,
        date_diff('day', items.first_order, items.last_order) as span_days,
        items.total_spend
    from items
    cross join company_orders

),

cutoffs as (

    select
        quantile_cont(attachment, 0.9) as frequent_cutoff,
        quantile_cont(total_spend, 0.5) as spend_cutoff
    from scored

)

select
    scored.item_id,
    scored.category,
    scored.unit_of_measure,
    scored.n_orders,
    scored.attachment,
    scored.n_months,
    scored.span_days,
    scored.first_order,
    scored.last_order,
    scored.total_spend,
    scored.total_spend / 100 as value_of_1pct_price_change
from scored
cross join cutoffs
where scored.attachment > cutoffs.frequent_cutoff
    and scored.n_months >= 8
    and scored.span_days >= 365
    and scored.total_spend > cutoffs.spend_cutoff
order by scored.n_orders desc
