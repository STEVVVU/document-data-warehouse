select * from {{ ref('invoice_anomalies') }}
where currency_count <> 1 or supplier_count <> 1 or date_count <> 1
