from pathlib import Path

import duckdb


def test_delivery_count_does_not_inflate_revision_count():
    sql = (Path(__file__).parents[1] / "models/marts/source_quality.sql").read_text()
    sql = sql.replace("{{ ref('stg_lines') }}", "raw_test").replace(
        "{{ ref('int_lines') }}", "current_test")
    with duckdb.connect() as con:
        con.execute("create table raw_test "
                    "(_data_source varchar, record_key varchar, revision int)")
        con.execute("insert into raw_test values ('a','x',1),('a','x',1),('a','x',2)")
        con.execute("create table current_test (_data_source varchar, deleted boolean)")
        con.execute("insert into current_test values ('a',false)")
        assert con.execute(sql).fetchall() == [("a", 2, 3, 1, 0)]
