with raw as (
    select * from {{ source('raw', 'raw_lines') }}
)
select * from raw
