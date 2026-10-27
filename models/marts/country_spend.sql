with lines as (
    select * from {{ ref('fct_invoice_lines') }}
)
select country, currency, count(*) as line_count, sum(line_total_cents) as total_cents
from lines group by country, currency
