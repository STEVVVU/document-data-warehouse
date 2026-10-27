with invoices as (
    select * from {{ ref('fct_invoices') }}
)
select supplier_key, currency, count(*) as invoice_count, sum(total_cents) as total_cents
from invoices group by supplier_key, currency
