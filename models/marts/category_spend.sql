with lines as (
    select * from {{ ref('fct_invoice_lines') }}
)
select category, currency, sum(quantity) as units, sum(line_total_cents) as total_cents
from lines group by category, currency
