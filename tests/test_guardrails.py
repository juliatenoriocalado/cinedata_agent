import pytest

from cinedata_agent.guardrails import UnsafeSQLError, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from v_filmes limit 5;",
        "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
        "SELECT replace(titulo, 'a', 'b') FROM v_filmes",  # replace() é função, não REPLACE INTO
        "SELECT titulo FROM v_filmes WHERE titulo LIKE '%;drop table x%'",  # texto, não comando
        "SELECT 1 -- comentário\n",
        "/* cabeçalho */ SELECT 1",
    ],
)
def test_allows_read_queries(sql):
    assert validate_sql(sql).lower().startswith(("select", "with"))


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "DROP TABLE dim_movies",
        "DELETE FROM dim_movies",
        "UPDATE dim_genres SET nome_genero = 'x'",
        "INSERT INTO dim_genres VALUES ('a', 'b')",
        "SELECT 1; DROP TABLE dim_movies",
        "/* x */ DELETE FROM dim_movies -- y",
        "PRAGMA table_info(dim_movies)",
        "ATTACH DATABASE 'x.db' AS x",
        "WITH x AS (SELECT 1) DELETE FROM dim_movies",
        "REPLACE INTO dim_genres VALUES ('a', 'b')",
        "CREATE TABLE t (x)",
    ],
)
def test_blocks_non_read_queries(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)
