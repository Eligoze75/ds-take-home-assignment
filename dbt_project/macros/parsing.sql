{# Bronze arrives as raw text. These macros normalise the formats the source systems emit. #}

{% macro clean_id(col) -%}
    upper(trim({{ col }}))
{%- endmacro %}

{% macro parse_date(col) -%}
    coalesce(
        try_strptime(trim({{ col }}), '%Y-%m-%d'),
        try_strptime(trim({{ col }}), '%m/%d/%Y')
    )::date
{%- endmacro %}

{% macro parse_amount(col) -%}
    try_cast(replace(replace(trim({{ col }}), '$', ''), ',', '') as decimal(12, 2))
{%- endmacro %}

{% macro clean_text(col) -%}
    nullif(trim({{ col }}), '')
{%- endmacro %}

{# 'received' / 'RECEIVED' / 'Received' -> 'Received' #}
{% macro title_case(col) -%}
    upper(substr(trim({{ col }}), 1, 1)) || lower(substr(trim({{ col }}), 2))
{%- endmacro %}
