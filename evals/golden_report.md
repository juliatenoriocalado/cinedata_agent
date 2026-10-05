# Relatório das SQLs de referência

Gerado por `python -m evals.check_golden`. Revise cada linha.

## fin_top10_receita
**Bilheteria e Finanças**: Top 10 filmes com maior receita em R$

10 linhas em 0.0s.

| titulo | ano_lancamento | receita_brl |
|---|---|---|
| Avatar: The Way Of Water | 2022 | 12390136500.54 |
| Avengers: Endgame | 2019 | 11094720000 |
| Spider-man: No Way Home | 2021 | 10977782882.74 |
| Avengers: Infinity War | 2018 | 7190430847.63 |
| Top Gun: Maverick | 2022 | 7160804869.01 |
| Barbie | 2023 | 6856159007.38 |
| The Super Mario Bros. Movie | 2023 | 6838413799.1 |
| The Lion King | 2019 | 6227552146.58 |
| Frozen Ii | 2019 | 6094028191.32 |
| Jurassic World: Fallen Kingdom | 2018 | 4934822930.85 |

## fin_lucro_medio_genero
**Bilheteria e Finanças**: Lucro médio por gênero, considerando apenas filmes com receita informada

19 linhas em 0.1s.

| nome_genero | qtd_filmes | lucro_medio_brl |
|---|---|---|
| Science Fiction | 227 | 520783718.33 |
| Adventure | 393 | 514678791.39 |
| Action | 594 | 343223021.87 |
| Fantasy | 255 | 335448446.35 |
| Family | 264 | 324648758.33 |
| Animation | 239 | 303517897.37 |
| War | 91 | 194016703.28 |
| History | 171 | 146826836.61 |
| Comedy | 813 | 143589472.55 |
| Mystery | 246 | 119462433.49 |

> Nota: Segue o enunciado literal (só receita informada). Quando o orçamento é NULL, lucro = receita (orçamento tratado como 0), o que infla a média (1.743 filmes).

## fin_maior_margem
**Bilheteria e Finanças**: Filmes com maior margem de lucro, entre os que possuem receita e orçamento informados

10 linhas em 0.0s.

| titulo | ano_lancamento | orcamento_brl | receita_brl | margem_pct |
|---|---|---|---|---|
| Dad, I'm Sorry | 2021 | 712.12 | 95303762.5 | 100.0 |
| Etlb | 2017 | 161.29 | 3225800 | 100.0 |
| Jailbait | 2017 | 1688.44 | 23778840.8 | 99.99 |
| Trivikrama | 2022 | 20.93 | 52328 | 99.96 |
| The Good Neighbor | 2022 | 538.72 | 486949.61 | 99.89 |
| New York Masalı | 2017 | 3.29 | 1643.6 | 99.8 |
| Secret Superstar | 2017 | 908293.25 | 435981992.64 | 99.79 |
| Alive | 2022 | 5.01 | 2003.48 | 99.75 |
| Bad Ben: The Mandela Effect | 2018 | 1126.11 | 412907 | 99.73 |
| Bad Ben | 2016 | 970.59 | 355883 | 99.73 |

> Nota: Orçamentos de R$ 3 a R$ 1.700 (placeholders) dominam o topo: a margem fica ~100%.

## pop_top5
**Popularidade e Engajamento**: Os 5 filmes mais populares

5 linhas em 0.1s.

| titulo | ano_lancamento | popularidade |
|---|---|---|
| Blue Beetle | 2023 | 2994.357 |
| Gran Turismo | 2023 | 2680.593 |
| The Nun Ii | 2023 | 1692.778 |
| Meg 2: The Trench | 2023 | 1567.273 |
| Retribution | 2023 | 1547.22 |

> Nota: A view descarta 4 valores inteiros que parecem anos (2020.0, 2019.0, 2018.0, 1969.0).

## pop_divergencia_tmdb_imdb
**Popularidade e Engajamento**: Filmes com maior divergência entre a nota TMDB e a nota IMDb

10 linhas em 0.1s.

| titulo | ano_lancamento | nota_tmdb | qtd_tmdb | nota_imdb | qtd_imdb | divergencia |
|---|---|---|---|---|---|---|
| Alfredo | 2020 | 1.0 | 1 | 10.0 | 7 | 9.0 |
| The Farmer | 2016 | 0.5 | 1 | 9.0 | 7 | 8.5 |
| Coming Out: A 50 Year History | 2017 | 0.8 | None | 9.3 | None | 8.5 |
| Behave, Kid | 2019 | 1.0 | None | 9.4 | 7 | 8.4 |
| Sketchy Times With Lilly Singh | 2020 | 10.0 | 1 | 1.7 | 174 | 8.3 |
| Afraid Of The Night | 2016 | 1.0 | 1 | 9.3 | 49 | 8.3 |
| Fan Club | 2016 | 1.0 | 1 | 9.3 | 44 | 8.3 |
| Night At The Ark Encounter | 2021 | 10.0 | 1 | 1.8 | 38 | 8.2 |
| Ali | 2021 | 1.0 | 1 | 9.2 | 12 | 8.2 |
| The Devil's Tail | 2020 | 1.0 | 1 | 9.2 | None | 8.2 |

> Nota: Sem mínimo de votos: o topo vem de filmes com 1 voto no TMDB.

## pop_imdb_por_ano
**Popularidade e Engajamento**: Nota média IMDb por ano de lançamento

13 linhas em 0.3s.

| ano_lancamento | nota_imdb_media | qtd_filmes |
|---|---|---|
| 2016 | 6.342 | 10372 |
| 2017 | 6.344 | 11179 |
| 2018 | 6.273 | 11323 |
| 2019 | 6.263 | 11628 |
| 2020 | 6.247 | 9528 |
| 2021 | 6.232 | 9572 |
| 2022 | 6.233 | 9881 |
| 2023 | 6.227 | 7807 |
| 2024 | 6.155 | 1621 |
| 2025 | 6.575 | 4 |

## elenco_ator_5anos
**Elenco e Equipe**: Ator com mais participações em filmes lançados nos últimos 5 anos

10 linhas em 4.3s.

| ator | qtd_filmes |
|---|---|
| Eric Roberts | 71 |
| Vennela Kishore | 42 |
| Yogi Babu | 39 |
| Ahomas Hailwuttem | 37 |
| Anton Pelizzari | 37 |
| Cameron Nichols | 37 |
| David Love | 37 |
| Jazzyjoeyjr | 37 |
| John Whinfield | 37 |
| Michael Paré | 31 |

## elenco_diretores_nota
**Elenco e Equipe**: Diretores com maior nota média (mínimo de 5 filmes)

10 linhas em 1.5s.

| diretor | qtd_filmes | nota_imdb_media |
|---|---|---|
| Scott Wozniak | 5 | 9.34 |
| Jun Shishido | 8 | 9.188 |
| Yūichirō Hayashi | 8 | 9.188 |
| Trevor L. Allen | 6 | 9.15 |
| Alonso O. Lara | 14 | 9.093 |
| Tokio Igarashi | 5 | 9.0 |
| Erlik | 6 | 8.95 |
| Stuart Webster | 5 | 8.88 |
| Mark Fischbach | 6 | 8.833 |
| John D. Boswell | 8 | 8.7 |

> Nota: 'Nota média' interpretada como IMDb; o mínimo de 5 conta só filmes com nota IMDb.

## elenco_dupla_ator_diretor
**Elenco e Equipe**: Dupla ator–diretor que mais trabalhou junta

10 linhas em 5.6s.

| ator | diretor | qtd_filmes |
|---|---|---|
| Joe Anoa'i | Kevin Dunn | 37 |
| Colby Lopez | Kevin Dunn | 32 |
| Ahomas Hailwuttem | Chad Payne | 31 |
| Anton Pelizzari | Chad Payne | 31 |
| Cameron Nichols | Chad Payne | 31 |
| David Love | Chad Payne | 31 |
| Jazzyjoeyjr | Chad Payne | 31 |
| John Whinfield | Chad Payne | 31 |
| Jeff Kirkendall | Mark Polonia | 25 |
| Vivica A. Fox | David Decoteau | 25 |

> Nota: Parte do topo vem de filmes duplicados no catálogo (mesmo título, dezenas de id_filme).

## gen_qtd_por_genero
**Gêneros e Produtoras**: Quantidade de filmes por gênero

19 linhas em 0.2s.

| nome_genero | qtd_filmes |
|---|---|
| Drama | 28086 |
| Documentary | 18082 |
| Comedy | 16048 |
| Horror | 8674 |
| Thriller | 8540 |
| Romance | 6209 |
| Action | 5028 |
| Animation | 3911 |
| Crime | 3902 |
| Tv Movie | 3336 |

> Nota: Filme com vários gêneros conta em cada um. 20.037 filmes não têm gênero.

## gen_produtora_lucro_total
**Gêneros e Produtoras**: Produtora com maior lucro total

10 linhas em 0.5s.

| nome_produtora | qtd_filmes | lucro_total_brl |
|---|---|---|
| Marvel Studios | 19 | 66534521937.88 |
| Universal Pictures | 101 | 63940587138.21 |
| Walt Disney Pictures | 37 | 44264683968.06 |
| Columbia Pictures | 59 | 43624937070.78 |
| Warner Bros. Pictures | 68 | 38516333904.02 |
| Paramount | 56 | 27514224400.78 |
| Pascal Pictures | 10 | 25370400587.15 |
| 20th Century Fox | 40 | 23491890182.49 |
| Illumination | 6 | 20543211073.41 |
| New Line Cinema | 34 | 17905924643.53 |

## gen_genero_margem_media
**Gêneros e Produtoras**: Gênero com maior margem de lucro média

19 linhas em 0.1s.

| nome_genero | qtd_filmes | media_das_margens_pct | margem_agregada_pct |
|---|---|---|---|
| Horror | 168 | -1426.08 | 74.67 |
| Adventure | 246 | -1313.41 | 68.71 |
| Animation | 97 | -845.31 | 68.29 |
| Science Fiction | 134 | -3380.72 | 68.17 |
| Family | 142 | -1335.65 | 67.65 |
| War | 57 | -534.88 | 66.89 |
| Action | 379 | -1233.02 | 65.48 |
| Music | 45 | -640.95 | 64.14 |
| Fantasy | 134 | -1616.99 | 64.13 |
| Comedy | 403 | -14844.58 | 63.48 |

> Nota: A média simples das margens por filme é negativa em todos os gêneros (outliers até -5.409.086%). A margem agregada (soma do lucro / soma da receita) é a métrica robusta.

## aval_mais_avaliados
**Avaliações dos Usuários**: Filmes mais avaliados pelos usuários

10 linhas em 0.3s.

| titulo | ano_lancamento | id_filme | qtd_avaliacoes_usuarios | nota_media_usuarios |
|---|---|---|---|---|
| Die Hart 2: Die Harter | 2024 | 1391481 | 13 | 4.99 |
| Die Hart 2: Die Harter | 2024 | 1376602 | 12 | 6.49 |
| Die Hart: Die Harter | 2024 | 1556716 | 11 | 5.56 |
| Die Hart: Die Harter | 2024 | 1474469 | 10 | 5.97 |
| Die Hart 2: Die Harter | 2024 | 1734206 | 10 | 5.42 |
| Die Hart: Die Harter | 2024 | 1336604 | 10 | 4.45 |
| Die Hart: Die Harter | 2024 | 1586934 | 10 | 4.04 |
| Die Hart: Die Harter | 2024 | 1700078 | 9 | 6.49 |
| Die Hart 2: Die Harter | 2024 | 1463021 | 9 | 6.43 |
| Duro De Atuar 2 | 2024 | 1569781 | 9 | 6.11 |

> Nota: Máximo de 13 avaliações por filme: muitos empates. O topo tem títulos repetidos.

## aval_divergencia_usuarios_imdb
**Avaliações dos Usuários**: Filmes em que a nota média dos usuários mais diverge da nota IMDb

10 linhas em 0.2s.

| titulo | ano_lancamento | nota_media_usuarios | nota_imdb | qtd_avaliacoes_usuarios | divergencia |
|---|---|---|---|---|---|
| The Moon Child | 2021 | 0.0 | 9.8 | 1 | 9.8 |
| Nathan For You: Finding Frances | 2017 | 0.1 | 9.5 | 1 | 9.4 |
| Opus Cope: An Algorithmic Opera | 2022 | 0.0 | 9.3 | 1 | 9.3 |
| Butterfly | 2019 | 0.4 | 9.6 | 1 | 9.2 |
| Venatio | 2016 | 0.1 | 9.3 | 1 | 9.2 |
| 702 | 2016 | 0.55 | 9.7 | 2 | 9.15 |
| Ivy | 2017 | 0.3 | 9.4 | 1 | 9.1 |
| Jaimen Hudson: From Sky To Sea | 2021 | 0.2 | 9.3 | 1 | 9.1 |
| Mired | 2016 | 0.0 | 9.1 | 1 | 9.1 |
| Red Dead Redemption 2 | 2018 | 0.7 | 9.8 | 1 | 9.1 |

> Nota: A nota de usuário vem de 1 a 13 avaliações; divergências extremas são ruído amostral.
