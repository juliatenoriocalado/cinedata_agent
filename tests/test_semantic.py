"""Confere as views contra as tabelas originais e testa as defesas do banco (precisa do .db)."""

import sqlite3

import pytest

from cinedata_agent.db import QueryTimeout, run_query
from cinedata_agent.guardrails import UnsafeSQLError
from conftest import needs_db

pytestmark = needs_db


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_v_filmes_keeps_one_row_per_movie(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM v_filmes") == scalar(conn, "SELECT COUNT(*) FROM dim_movies")
    assert scalar(conn, "SELECT COUNT(DISTINCT sk_movie_id) FROM v_filmes") == scalar(
        conn, "SELECT COUNT(*) FROM dim_movies"
    )


def test_lucro_only_exists_when_receita_informada(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM v_filmes WHERE lucro_brl IS NOT NULL AND receita_brl IS NULL") == 0
    assert scalar(conn, "SELECT COUNT(lucro_brl) FROM v_filmes") == scalar(
        conn, "SELECT COUNT(receita_brl) FROM fact_movies_performance"
    )


def test_margem_matches_formula_and_requires_both(conn):
    both = scalar(
        conn,
        "SELECT COUNT(*) FROM fact_movies_performance WHERE receita_brl > 0 AND orcamento_brl IS NOT NULL",
    )
    assert scalar(conn, "SELECT COUNT(margem_lucro_pct) FROM v_filmes") == both
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM v_filmes WHERE margem_lucro_pct IS NOT NULL "
        "AND ABS(margem_lucro_pct - (receita_brl - orcamento_brl) * 100.0 / receita_brl) > 1e-6",
    )
    assert bad == 0


def test_invalid_notes_are_nulled(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM v_filmes WHERE nota_tmdb = 0") == 0
    assert scalar(conn, "SELECT COUNT(*) FROM v_filmes WHERE nota_imdb < 1") == 0
    # 50 linhas fora da escala IMDb (23 < 1 e 34 com >1 casa decimal; 7 nos dois grupos).
    positivas = scalar(conn, "SELECT COUNT(*) FROM fact_movies_performance WHERE nota_imdb > 0")
    assert positivas - scalar(conn, "SELECT COUNT(nota_imdb) FROM v_filmes") == 50


def test_year_like_popularity_is_nulled(conn):
    assert scalar(conn, "SELECT MAX(popularidade) FROM v_filmes") == pytest.approx(2994.357)
    assert scalar(conn, "SELECT COUNT(*) FROM v_filmes WHERE popularidade IN (1969, 2018, 2019, 2020)") == 0


def test_people_view_exposes_role(conn):
    papeis = {r[0] for r in conn.execute("SELECT DISTINCT papel FROM v_filme_pessoas")}
    assert papeis == {"Ator", "Diretor", "Roteirista"}


# ----------------------------------------------------------- defesas do banco
@pytest.mark.parametrize("sql", ["DELETE FROM dim_genres", "CREATE TABLE t (x)", "PRAGMA writable_schema = ON"])
def test_authorizer_blocks_writes_even_without_guardrail(conn, sql):
    with pytest.raises(sqlite3.Error):
        conn.execute(sql)  # chamada direta: ignora validate_sql de propósito


def test_run_query_rejects_unsafe_sql(conn):
    with pytest.raises(UnsafeSQLError):
        run_query(conn, "DROP TABLE dim_movies")


def test_run_query_truncates_rows(conn):
    result = run_query(conn, "SELECT titulo FROM v_filmes", max_rows=5)
    assert len(result.rows) == 5 and result.truncated


def test_run_query_times_out(conn):
    slow = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 500000000) SELECT COUNT(*) FROM c"
    with pytest.raises(QueryTimeout):
        run_query(conn, slow, timeout_s=1)
    assert scalar(conn, "SELECT COUNT(*) FROM dim_genres") == 19  # conexão continua utilizável


def test_every_golden_query_runs(conn):
    from evals.golden import GOLDEN

    for g in GOLDEN:
        result = run_query(conn, g.sql, max_rows=50, timeout_s=60)
        assert result.rows, f"{g.id} não retornou linhas"
