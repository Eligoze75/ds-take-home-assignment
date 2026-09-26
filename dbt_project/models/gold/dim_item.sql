SELECT
    item_id,
    description,
    category,
    unit_of_measure,
    manufacturer_id,
    manufacturer_name,
    COALESCE(description, '') || ' ' ||
    COALESCE(category, '') || ' ' ||
    COALESCE(manufacturer_name, '') AS search_text
FROM {{ ref('items') }}
