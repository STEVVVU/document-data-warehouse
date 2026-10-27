with deliveries as (
    select _data_source, record_key, revision, count(*) as delivery_count
    from {{ ref('stg_lines') }} group by _data_source, record_key, revision
), raw as (
    select _data_source, count(*) as raw_revisions, sum(delivery_count) as raw_deliveries
    from deliveries group by _data_source
), current as (
    select _data_source, count(*) as current_lines,
           sum(case when deleted then 1 else 0 end) as deleted_lines
    from {{ ref('int_lines') }} group by _data_source
)
select r._data_source, raw_revisions, raw_deliveries, current_lines, deleted_lines
from raw r join current c on r._data_source = c._data_source
