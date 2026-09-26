with source as (

    select * from {{ source('bronze', 'item_pricing') }}

),

cleaned as (

    select
        {{ clean_id('item_id') }}                  as item_id,
        {{ clean_id('vendor_id') }}                as vendor_id,
        {{ parse_date('price_effective_date') }}   as price_effective_date,
        {{ parse_amount('vendor_price') }}         as vendor_price

    from source

)

select * from cleaned
