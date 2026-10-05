"""Perguntas do enunciado com SQL de referência escrita à mão (revisar antes de confiar).

Usam as mesmas views do agente (cinedata_agent/semantic.py), então as regras de qualidade de
dados são as mesmas. A corretude das views é conferida contra as tabelas originais em
tests/test_semantic.py.

Interpretações adotadas onde o enunciado é ambíguo (confirme que concordam com o seu critério):
  * "Receita informada" = receita IS NOT NULL. lucro só existe com receita informada.
  * "Margem de lucro" = (receita - orçamento) / receita, exigindo receita e orçamento.
  * "Nota média" (diretores, por ano) = nota IMDb.
  * "Últimos 5 anos" = data_lancamento entre hoje - 5 anos e hoje.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    category: str
    question: str
    sql: str
    notes: str = ""


GOLDEN: list[GoldenQuestion] = [
    # ---------------------------------------------------------------- Finanças
    GoldenQuestion(
        id="fin_top10_receita",
        category="Bilheteria e Finanças",
        question="Top 10 filmes com maior receita em R$",
        sql="""
            SELECT titulo, ano_lancamento, receita_brl
            FROM v_filmes
            WHERE receita_brl IS NOT NULL
            ORDER BY receita_brl DESC
            LIMIT 10
        """,
    ),
    GoldenQuestion(
        id="fin_lucro_medio_genero",
        category="Bilheteria e Finanças",
        question="Lucro médio por gênero, considerando apenas filmes com receita informada",
        sql="""
            SELECT g.nome_genero,
                   COUNT(DISTINCT f.sk_movie_id) AS qtd_filmes,
                   ROUND(AVG(f.lucro_brl), 2) AS lucro_medio_brl
            FROM v_filmes f
            JOIN v_filme_generos g USING (sk_movie_id)
            WHERE f.receita_brl IS NOT NULL
            GROUP BY g.sk_genre_id, g.nome_genero
            ORDER BY lucro_medio_brl DESC
        """,
        notes="Segue o enunciado literal (só receita informada). Quando o orçamento é NULL, "
        "lucro = receita (orçamento tratado como 0), o que infla a média (1.743 filmes).",
    ),
    GoldenQuestion(
        id="fin_maior_margem",
        category="Bilheteria e Finanças",
        question="Filmes com maior margem de lucro, entre os que possuem receita e orçamento informados",
        sql="""
            SELECT titulo, ano_lancamento, orcamento_brl, receita_brl,
                   ROUND(margem_lucro_pct, 2) AS margem_pct
            FROM v_filmes
            WHERE margem_lucro_pct IS NOT NULL
            ORDER BY margem_lucro_pct DESC, receita_brl DESC
            LIMIT 10
        """,
        notes="Orçamentos de R$ 3 a R$ 1.700 (placeholders) dominam o topo: a margem fica ~100%.",
    ),
    # ----------------------------------------------------------- Popularidade
    GoldenQuestion(
        id="pop_top5",
        category="Popularidade e Engajamento",
        question="Os 5 filmes mais populares",
        sql="""
            SELECT titulo, ano_lancamento, popularidade
            FROM v_filmes
            WHERE popularidade IS NOT NULL
            ORDER BY popularidade DESC
            LIMIT 5
        """,
        notes="A view descarta 4 valores inteiros que parecem anos (2020.0, 2019.0, 2018.0, 1969.0).",
    ),
    GoldenQuestion(
        id="pop_divergencia_tmdb_imdb",
        category="Popularidade e Engajamento",
        question="Filmes com maior divergência entre a nota TMDB e a nota IMDb",
        sql="""
            SELECT titulo, ano_lancamento, nota_tmdb, qtd_tmdb, nota_imdb, qtd_imdb,
                   ROUND(ABS(nota_tmdb - nota_imdb), 2) AS divergencia
            FROM v_filmes
            WHERE nota_tmdb IS NOT NULL AND nota_imdb IS NOT NULL
            ORDER BY divergencia DESC, qtd_imdb DESC, titulo
            LIMIT 10
        """,
        notes="Sem mínimo de votos: o topo vem de filmes com 1 voto no TMDB.",
    ),
    GoldenQuestion(
        id="pop_imdb_por_ano",
        category="Popularidade e Engajamento",
        question="Nota média IMDb por ano de lançamento",
        sql="""
            SELECT ano_lancamento, ROUND(AVG(nota_imdb), 3) AS nota_imdb_media,
                   COUNT(*) AS qtd_filmes
            FROM v_filmes
            WHERE nota_imdb IS NOT NULL
            GROUP BY ano_lancamento
            ORDER BY ano_lancamento
        """,
    ),
    # ----------------------------------------------------------------- Elenco
    GoldenQuestion(
        id="elenco_ator_5anos",
        category="Elenco e Equipe",
        question="Ator com mais participações em filmes lançados nos últimos 5 anos",
        sql="""
            SELECT p.nome_pessoa AS ator, COUNT(DISTINCT f.sk_movie_id) AS qtd_filmes
            FROM v_filme_pessoas p
            JOIN v_filmes f USING (sk_movie_id)
            WHERE p.papel = 'Ator'
              AND f.data_lancamento BETWEEN date('now', '-5 years') AND date('now')
            GROUP BY p.sk_person_id, p.nome_pessoa
            ORDER BY qtd_filmes DESC, ator
            LIMIT 10
        """,
    ),
    GoldenQuestion(
        id="elenco_diretores_nota",
        category="Elenco e Equipe",
        question="Diretores com maior nota média (mínimo de 5 filmes)",
        sql="""
            SELECT p.nome_pessoa AS diretor,
                   COUNT(DISTINCT f.sk_movie_id) AS qtd_filmes,
                   ROUND(AVG(f.nota_imdb), 3) AS nota_imdb_media
            FROM v_filme_pessoas p
            JOIN v_filmes f USING (sk_movie_id)
            WHERE p.papel = 'Diretor' AND f.nota_imdb IS NOT NULL
            GROUP BY p.sk_person_id, p.nome_pessoa
            HAVING COUNT(DISTINCT f.sk_movie_id) >= 5
            ORDER BY nota_imdb_media DESC, qtd_filmes DESC, diretor
            LIMIT 10
        """,
        notes="'Nota média' interpretada como IMDb; o mínimo de 5 conta só filmes com nota IMDb.",
    ),
    GoldenQuestion(
        id="elenco_dupla_ator_diretor",
        category="Elenco e Equipe",
        question="Dupla ator–diretor que mais trabalhou junta",
        sql="""
            SELECT a.nome_pessoa AS ator, d.nome_pessoa AS diretor,
                   COUNT(DISTINCT a.sk_movie_id) AS qtd_filmes
            FROM v_filme_pessoas a
            JOIN v_filme_pessoas d ON d.sk_movie_id = a.sk_movie_id AND d.papel = 'Diretor'
            WHERE a.papel = 'Ator'
            GROUP BY a.sk_person_id, d.sk_person_id, a.nome_pessoa, d.nome_pessoa
            ORDER BY qtd_filmes DESC, ator, diretor
            LIMIT 10
        """,
        notes="Parte do topo vem de filmes duplicados no catálogo (mesmo título, dezenas de id_filme).",
    ),
    # ------------------------------------------------------ Gêneros e produtoras
    GoldenQuestion(
        id="gen_qtd_por_genero",
        category="Gêneros e Produtoras",
        question="Quantidade de filmes por gênero",
        sql="""
            SELECT nome_genero, COUNT(DISTINCT sk_movie_id) AS qtd_filmes
            FROM v_filme_generos
            GROUP BY sk_genre_id, nome_genero
            ORDER BY qtd_filmes DESC, nome_genero
        """,
        notes="Filme com vários gêneros conta em cada um. 20.037 filmes não têm gênero.",
    ),
    GoldenQuestion(
        id="gen_produtora_lucro_total",
        category="Gêneros e Produtoras",
        question="Produtora com maior lucro total",
        sql="""
            SELECT p.nome_produtora,
                   COUNT(DISTINCT f.sk_movie_id) AS qtd_filmes,
                   ROUND(SUM(f.lucro_brl), 2) AS lucro_total_brl
            FROM v_filme_produtoras p
            JOIN v_filmes f USING (sk_movie_id)
            WHERE f.receita_brl IS NOT NULL
            GROUP BY p.sk_company_id, p.nome_produtora
            ORDER BY lucro_total_brl DESC
            LIMIT 10
        """,
    ),
    GoldenQuestion(
        id="gen_genero_margem_media",
        category="Gêneros e Produtoras",
        question="Gênero com maior margem de lucro média",
        sql="""
            SELECT g.nome_genero,
                   COUNT(DISTINCT f.sk_movie_id) AS qtd_filmes,
                   ROUND(AVG(f.margem_lucro_pct), 2) AS media_das_margens_pct,
                   ROUND(SUM(f.receita_brl - f.orcamento_brl) * 100.0 / SUM(f.receita_brl), 2)
                       AS margem_agregada_pct
            FROM v_filmes f
            JOIN v_filme_generos g USING (sk_movie_id)
            WHERE f.margem_lucro_pct IS NOT NULL
            GROUP BY g.sk_genre_id, g.nome_genero
            ORDER BY margem_agregada_pct DESC
        """,
        notes="A média simples das margens por filme é negativa em todos os gêneros (outliers até "
        "-5.409.086%). A margem agregada (soma do lucro / soma da receita) é a métrica robusta.",
    ),
    # ------------------------------------------------------------- Avaliações
    GoldenQuestion(
        id="aval_mais_avaliados",
        category="Avaliações dos Usuários",
        question="Filmes mais avaliados pelos usuários",
        sql="""
            SELECT titulo, ano_lancamento, id_filme,
                   qtd_avaliacoes_usuarios, nota_media_usuarios
            FROM v_filmes
            WHERE qtd_avaliacoes_usuarios IS NOT NULL
            ORDER BY qtd_avaliacoes_usuarios DESC, nota_media_usuarios DESC, titulo
            LIMIT 10
        """,
        notes="Máximo de 13 avaliações por filme: muitos empates. O topo tem títulos repetidos.",
    ),
    GoldenQuestion(
        id="aval_divergencia_usuarios_imdb",
        category="Avaliações dos Usuários",
        question="Filmes em que a nota média dos usuários mais diverge da nota IMDb",
        sql="""
            SELECT titulo, ano_lancamento, nota_media_usuarios, nota_imdb,
                   qtd_avaliacoes_usuarios,
                   ROUND(ABS(nota_media_usuarios - nota_imdb), 2) AS divergencia
            FROM v_filmes
            WHERE nota_media_usuarios IS NOT NULL AND nota_imdb IS NOT NULL
            ORDER BY divergencia DESC, qtd_avaliacoes_usuarios DESC, titulo
            LIMIT 10
        """,
        notes="A nota de usuário vem de 1 a 13 avaliações; divergências extremas são ruído amostral.",
    ),
]
