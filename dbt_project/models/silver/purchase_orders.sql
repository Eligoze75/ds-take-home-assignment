with source as (

    select * from {{ source('bronze', 'purchase_orders') }}

),

cleaned as (

    select
        {{ clean_id('po_number') }}        as po_number,
        {{ clean_id('customer_id') }}      as customer_id,
        {{ clean_id('vendor_id') }}        as vendor_id,
        {{ clean_text('vendor_name') }}    as vendor_name,
        {{ parse_date('order_date') }}     as order_date,
        {{ title_case('status') }}         as status,
        {{ parse_amount('total_amount') }} as total_amount

    from source

)

select * from cleaned
