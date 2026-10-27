with lines as (
    select * from {{ ref('fct_invoice_lines') }}
)
select invoice_key, min(invoice_id) as invoice_id, min(supplier_key) as supplier_key,
       min(invoice_date) as invoice_date, min(currency) as currency,
       count(*) as line_count, sum(line_total_cents) as total_cents
from lines group by invoice_key
