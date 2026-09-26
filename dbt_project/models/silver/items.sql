with source as (

    select * from {{ source('bronze', 'items') }}

),

cleaned as (

    select
        {{ clean_id('item_id') }}              as item_id,
        {{ clean_text('description') }}        as description,
        {{ title_case(clean_text('category')) }}           as category,
        {{ clean_text('unit_of_measure') }}    as unit_of_measure,
        {{ clean_id('manufacturer_id') }}    as manufacturer_id,
        {{ title_case(clean_text('manufacturer_name')) }}  as manufacturer_name

    from source

)

select * from cleaned
