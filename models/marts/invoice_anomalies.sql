with lines as (
    select * from {{ ref('fct_invoice_lines') }}
)
select invoice_key, count(*) as line_count,
       sum(case when unit_price_cents = 0 then 1 else 0 end) as free_lines,
       count(distinct currency) as currency_count,
       count(distinct supplier_key) as supplier_count,
       count(distinct invoice_date) as date_count
from lines group by invoice_key
