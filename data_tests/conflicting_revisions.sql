select record_key, revision from {{ ref('stg_lines') }}
group by record_key, revision having count(distinct _content_hash) > 1
