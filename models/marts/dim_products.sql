with ranked as (
    select product_key, sku, description, category, _data_source,
           row_number() over (partition by product_key order by revision desc,
                               invoice_date desc, record_key) as name_rank
    from {{ ref('fct_invoice_lines') }}
)
select product_key, sku, description, category, _data_source
from ranked where name_rank = 1
