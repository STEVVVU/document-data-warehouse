{{ config(materialized='incremental', unique_key='record_key',
          incremental_strategy='merge' if target.type == 'bigquery' else 'delete+insert') }}

with ranked as (
    select *, row_number() over (
        partition by record_key order by revision desc, _load_time desc, _content_hash desc
    ) as version_rank
    from {{ ref('stg_lines') }}
), latest as (
    select * from ranked where version_rank = 1
)
select l.* from latest l
{% if is_incremental() %}
left join {{ this }} old on l.record_key = old.record_key
where old.record_key is null or l.revision > old.revision
{% endif %}
