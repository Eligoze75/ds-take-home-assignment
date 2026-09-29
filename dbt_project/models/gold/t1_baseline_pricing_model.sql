-- Baseline pricing model for Task 1b ("what unit price to expect").
--
-- Grain: one row per (customer_id, item_id, vendor_id, order_date) that appears in
-- gold.fct_purchase_line. For each row, rolling_median_price_60d is the median unit
-- price paid on that customer/item/vendor combination over the strictly preceding
-- 60 calendar days (day [-60, -1]; the row's own order_date is never in its own
-- window, so there is no future leakage).
--
-- 60 days (not 15) because at this (customer, item, vendor) grain, purchases are
-- often more than 15 days apart: a 15-day window left ~89% of rows with no prior
-- history to draw on. 60 days trades a bit of recency for far fewer null predictions.
--
-- To get "what price to expect" for a new PO at date X, look up the row with the
-- largest order_date <= X for that customer/item/vendor and read rolling_median_price_60d.
-- n_prior_days_with_price tells you how many days of history that estimate rests on;
-- it is 0 (and the median is null) the first time a combination is ever seen.

with lines as (

    select
        customer_id,
        item_id,
        vendor_id,
        order_date,
        unit_price_paid
    from {{ ref('fct_purchase_line') }}
    where status <> 'Cancelled'

),

-- Collapse same-day lines to a single price per day, so a busy day doesn't
-- outweigh a quiet one in the rolling median.
daily_prices as (

    select
        customer_id,
        item_id,
        vendor_id,
        order_date,
        median(unit_price_paid) as daily_price
    from lines
    group by customer_id, item_id, vendor_id, order_date

),

rolling as (

    select
        customer_id,
        item_id,
        vendor_id,
        order_date,
        daily_price,
        median(daily_price) over (
            partition by customer_id, item_id, vendor_id
            order by order_date
            range between interval 60 days preceding and interval 1 day preceding
        ) as rolling_median_price_60d,
        count(daily_price) over (
            partition by customer_id, item_id, vendor_id
            order by order_date
            range between interval 60 days preceding and interval 1 day preceding
        ) as n_prior_days_with_price
    from daily_prices

)

select
    customer_id,
    item_id,
    vendor_id,
    order_date,
    daily_price,
    rolling_median_price_60d,
    n_prior_days_with_price
from rolling
order by customer_id, item_id, vendor_id, order_date
