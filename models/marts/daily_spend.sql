with invoices as (
    select * from {{ ref('fct_invoices') }}
)
select invoice_date, currency, count(*) as invoice_count, sum(total_cents) as total_cents
from invoices group by invoice_date, currency
