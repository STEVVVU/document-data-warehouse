with line_totals as (
    select currency, sum(line_total_cents) as total from {{ ref('fct_invoice_lines') }}
    group by currency
), invoice_totals as (
    select currency, sum(total_cents) as total from {{ ref('fct_invoices') }} group by currency
)
select l.currency from line_totals l full join invoice_totals i on l.currency = i.currency
where l.total is null or i.total is null or l.total <> i.total
