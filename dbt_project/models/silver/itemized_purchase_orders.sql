with source as (

    select * from {{ source('bronze', 'itemized_purchase_orders') }}

),

cleaned as (

    select
        {{ clean_id('po_number') }}             as po_number,
        {{ clean_id('customer_id') }}           as customer_id,
        {{ clean_id('item_id') }}               as item_id,
        try_cast(trim(quantity_ordered) as integer) as quantity_ordered,
        {{ parse_amount('unit_price_paid') }}   as unit_price_paid

    from source

)

select * from cleaned
