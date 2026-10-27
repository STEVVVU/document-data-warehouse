with ranked as (
    select supplier_key, supplier_id, supplier_name, country, _data_source,
           row_number() over (partition by supplier_key order by revision desc,
                               invoice_date desc, record_key) as name_rank
    from {{ ref('fct_invoice_lines') }}
)
select supplier_key, supplier_id, supplier_name, country, _data_source
from ranked where name_rank = 1
