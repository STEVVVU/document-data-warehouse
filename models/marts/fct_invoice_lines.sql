with active as (
    select * from {{ ref('int_lines') }} where not deleted
)
select record_key, invoice_key, supplier_key, product_key, line_id, invoice_id,
       supplier_id, supplier_name, invoice_date, sku, description, category, country,
       currency, quantity, unit_price_cents, quantity * unit_price_cents as line_total_cents,
       _data_source, revision
from active
