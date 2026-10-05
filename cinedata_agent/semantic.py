"""Camada semântica: views TEMPORÁRIAS criadas na conexão, sobre a camada Gold.

Por que existe: a Gold tem armadilhas que um modelo pequeno não lembra de tratar a cada
consulta (ver README, seção "Qualidade dos dados"). Em vez de depender do prompt, as regras
ficam aqui, uma vez. O arquivo cinerocket.db NÃO é alterado (views vivem no schema `temp`).

Regras aplicadas:

* lucro_*  só existe quando a receita foi informada. Na Gold, lucro = receita - orçamento
  com NULL tratado como 0, o que gera lucro 0 falso (sem receita e sem orçamento) e
  prejuízo falso (sem receita, com orçamento).
* margem_lucro_pct = (receita - orçamento) / receita * 100, só com receita > 0 e orçamento informado.
* nota_tmdb = 0 significa "sem nota" e vira NULL.
* nota_imdb fora da escala IMDb (< 1, ou com mais de 1 casa decimal) vira NULL.
  São 50 linhas, todas com qtd_imdb nulo.
* popularidade inteira >= 1900 vira NULL (4 linhas com valores 1969, 2018, 2019, 2020, que
  parecem anos, não popularidade). [Provável] artefato de carga; a causa não foi confirmada.
"""

VIEWS_DDL: list[str] = [
    """
    CREATE TEMP VIEW v_filmes AS
    SELECT
        m.sk_movie_id,
        m.id_filme,
        m.titulo,
        m.data_lancamento,
        m.ano_lancamento,
        m.duracao_minutos,
        m.idioma_original,
        m.status_filme,
        m.sinopse,
        f.orcamento_usd,
        f.receita_usd,
        CASE WHEN f.receita_usd IS NOT NULL THEN f.lucro_usd END AS lucro_usd,
        f.orcamento_brl,
        f.receita_brl,
        CASE WHEN f.receita_brl IS NOT NULL THEN f.lucro_brl END AS lucro_brl,
        CASE WHEN f.receita_brl > 0 AND f.orcamento_brl IS NOT NULL
             THEN (f.receita_brl - f.orcamento_brl) * 100.0 / f.receita_brl
        END AS margem_lucro_pct,
        CASE WHEN f.popularidade >= 1900 AND f.popularidade = CAST(f.popularidade AS INTEGER)
             THEN NULL ELSE f.popularidade
        END AS popularidade,
        NULLIF(f.nota_tmdb, 0) AS nota_tmdb,
        f.qtd_tmdb,
        CASE WHEN f.nota_imdb >= 1
                  AND ABS(f.nota_imdb * 10 - ROUND(f.nota_imdb * 10)) < 0.001
             THEN f.nota_imdb
        END AS nota_imdb,
        f.qtd_imdb,
        r.qtd_avaliacoes_usuarios,
        r.nota_media_usuarios
    FROM dim_movies m
    JOIN fact_movies_performance f ON f.sk_movie_id = m.sk_movie_id
    LEFT JOIN dim_reviews r ON r.sk_movie_id = m.sk_movie_id
    """,
    """
    CREATE TEMP VIEW v_filme_generos AS
    SELECT bg.sk_movie_id, g.sk_genre_id, g.nome_genero
    FROM bridge_movie_genre bg
    JOIN dim_genres g ON g.sk_genre_id = bg.sk_genre_id
    """,
    """
    CREATE TEMP VIEW v_filme_produtoras AS
    SELECT bc.sk_movie_id, c.sk_company_id, c.nome_produtora
    FROM bridge_movie_company bc
    JOIN dim_companies c ON c.sk_company_id = bc.sk_company_id
    """,
    """
    CREATE TEMP VIEW v_filme_pessoas AS
    SELECT bp.sk_movie_id, p.sk_person_id, p.nome_pessoa, p.tipo_pessoa AS papel
    FROM bridge_movie_person bp
    JOIN dim_people p ON p.sk_person_id = bp.sk_person_id
    """,
    """
    CREATE TEMP VIEW v_avaliacoes AS
    SELECT sk_movie_review_id, sk_movie_id, name AS autor, rating AS nota, text AS texto, created_at
    FROM movie_reviews
    """,
]

VIEW_NAMES = ["v_filmes", "v_filme_generos", "v_filme_produtoras", "v_filme_pessoas", "v_avaliacoes"]
