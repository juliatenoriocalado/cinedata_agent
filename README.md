# CineData Agent

Agente de **Text-to-SQL** para a camada Gold da CineData Analytics. Quem não sabe SQL pergunta em português
("Top 10 filmes com maior receita em R$") e o agente consulta o banco, em modo somente leitura, e responde
com os dados.

Atividade GenAI do Visagio Rocket Lab 2026.

- **Linguagem:** Python 3.10+
- **Modelo:** modelos `:free` da OpenRouter, com tool calling e fallback automático entre eles
- **Framework de agentes:** nenhum (Python puro + SDK `openai`). Justificativa na seção [Decisões](#decisões-de-projeto)
- **Interface:** linha de comando (`ask` para uma pergunta, `chat` para conversa com memória)

---

## Como executar

Os comandos abaixo funcionam no PowerShell ou no Git Bash do VS Code. Onde muda, está indicado.

### 1. Clonar e criar o ambiente virtual

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd cinedata-agent
python -m venv .venv
```

Ativar o ambiente:

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1
```
```bash
# Git Bash
source .venv/Scripts/activate
```

> Se o PowerShell bloquear o script de ativação, rode uma vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 3. Colocar o banco de dados

Baixe o `cinerocket.db` da pasta do drive da atividade e coloque em **`data/cinerocket.db`**.
O arquivo tem 581 MB e não está no repositório (o GitHub recusa arquivos acima de 100 MB; ele está no `.gitignore`).

### 4. Configurar a chave da OpenRouter

1. Crie uma conta em <https://openrouter.ai> e gere uma chave em <https://openrouter.ai/keys> (começa com `sk-or-v1-`).
2. Copie o arquivo de exemplo e cole a chave:

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Edite o `.env` e preencha `OPENROUTER_API_KEY`. O `.env` está no `.gitignore` e nunca deve ir para o GitHub.

### 5. Conferir a cota e os modelos (não gasta requisições do agente)

```bash
python -m cinedata_agent quota     # quantas das 50 requisições gratuitas ainda restam hoje
python -m cinedata_agent models     # quais modelos :free aceitam tool calling
```

### 6. Fazer perguntas

```bash
python -m cinedata_agent ask "Top 10 filmes com maior receita em R$"
python -m cinedata_agent ask "Quantidade de filmes por gênero" --show-sql
python -m cinedata_agent chat       # conversa com memória; 'sair' encerra
```

`--show-sql` imprime a SQL que o agente executou, para conferência. `--no-cache` ignora o cache de respostas.

---

## Como funciona

```
pergunta ──► CineDataAgent ──► OpenRouterClient ──► modelo :free (com fallback)
                 │   ▲                                   │
                 │   └───────── resultado da tool ◄──────┘  (tool call: run_sql)
                 ▼
           guardrails ──► conexão somente leitura ──► views semânticas ──► cinerocket.db
```

1. O prompt de sistema já traz o esquema, as regras de negócio e 3 exemplos. Não existe tool `get_schema`: isso
   economiza uma requisição por pergunta.
2. O modelo chama a ferramenta `run_sql(sql)`. O agente valida, executa e devolve colunas e linhas (JSON).
3. Se a SQL falhar, o erro volta ao modelo, que corrige e tenta de novo (até 5 rodadas).
4. O modelo escreve a resposta final em português, informando o critério usado.

**Custo típico:** 2 requisições por pergunta (1 para gerar a SQL, 1 para a resposta), mais 1 por correção de SQL
e 1 por modelo que falhar. Com 50 requisições por dia, são cerca de 20 perguntas novas.

### Guardrails (somente leitura)

Três camadas independentes. Qualquer uma sozinha já impede escrita:

| Camada | O que faz |
|---|---|
| `guardrails.py` | Aceita só `SELECT` ou `WITH ... SELECT`, uma instrução, sem `DROP`, `DELETE`, `PRAGMA`, `ATTACH` etc. Devolve mensagem clara para o modelo corrigir. |
| `db.py` (conexão) | Abre com `mode=ro` e `PRAGMA query_only = ON`. O SQLite recusa qualquer escrita. |
| `db.py` (authorizer) | `set_authorizer` só permite `SELECT`, `READ`, `FUNCTION` e `RECURSIVE`. |

Além disso: máximo de 50 linhas por consulta e timeout de 30 s (uma consulta lenta é interrompida, a conexão continua usável).
O conteúdo vindo do banco (títulos, sinopses) é tratado como dado, não como instrução.

### Cache e fallback

- **Cache** (`.cache/answers.sqlite`, local): pergunta repetida, mesmo com outra grafia, não gasta requisição.
  Só guarda respostas que vieram de uma consulta bem-sucedida. Validade de 7 dias.
- **Fallback:** se um modelo falha (provider lotado, 5xx, sem suporte a tools), tenta o próximo da lista e continua nele
  nas rodadas seguintes. Erros que **não** adiantam trocar de modelo param na hora: chave inválida (401),
  saldo (402) e cota diária esgotada (429 sem provider). O SDK é configurado com `max_retries=0`, porque
  requisições que falham também contam na cota e o SDK reenviaria sozinho.

---

## Qualidade dos dados e camada semântica

A camada Gold tem problemas que levam a respostas erradas se o agente consultar as tabelas cruas. Em vez de depender
de o modelo lembrar de todos eles, as regras ficam em **views temporárias** criadas na conexão
(`cinedata_agent/semantic.py`). O arquivo `.db` não é alterado. O agente consulta as views `v_filmes`,
`v_filme_generos`, `v_filme_produtoras`, `v_filme_pessoas` e `v_avaliacoes`.

| Problema encontrado | Evidência | Tratamento na view |
|---|---|---|
| `lucro_*` calculado com NULL como 0 | 85.976 filmes sem receita e sem orçamento têm lucro 0; 6.296 sem receita têm "prejuízo" igual ao orçamento; 1.743 sem orçamento têm lucro = receita | `lucro_*` só existe quando a receita foi informada |
| Margem média por filme explode | Mínimo de −5.409.086% (receita de R$ 3 com orçamento de milhões); todos os 19 gêneros ficam com média negativa | `margem_lucro_pct` exige receita > 0 e orçamento; o agente mostra também a **margem agregada** (soma do lucro ÷ soma da receita) |
| `nota_tmdb = 0` significa "sem nota" | 36.185 filmes | Vira NULL |
| `nota_imdb` fora da escala do IMDb | 50 linhas (23 abaixo de 1; 34 com mais de 1 casa decimal; 7 nos dois grupos), todas com `qtd_imdb` nulo | Vira NULL |
| `popularidade` com valor parecido com ano | 4 filmes: 1969.0, 2018.0, 2019.0, 2020.0 (entram no top 5 se não tratados) | Inteiro ≥ 1900 vira NULL. **[Provável]** artefato de carga; a causa não foi confirmada |
| Filmes duplicados no catálogo | Mesmo título e ano com dezenas de `id_filme` (ex.: 36 registros de um mesmo filme de 2023) | **Não tratado.** Distorce parte dos rankings de elenco e de "mais avaliados". O agente é instruído a avisar |
| Datas até 2029 | Filmes planejados; quase nada de 2025 em diante | Não tratado; só aviso no prompt |
| Notas com poucos votos | 29.456 filmes com nota TMDB de menos de 5 votos; nota de usuário vem de 1 a 13 avaliações | Não tratado: a pergunta é respondida literalmente, com aviso |

### Interpretações adotadas onde o enunciado é ambíguo

| Termo | Interpretação |
|---|---|
| Receita informada | `receita IS NOT NULL` |
| Lucro médio / total | Só filmes com receita informada (como diz o enunciado). Se o orçamento é NULL, o lucro é igual à receita |
| Margem de lucro | `(receita − orçamento) / receita`, só com receita e orçamento informados |
| "Nota média" de diretores e por ano | Nota IMDb |
| "Últimos 5 anos" | `data_lancamento` entre `hoje − 5 anos` e `hoje` |
| "Mais avaliados pelos usuários" | `qtd_avaliacoes_usuarios` (máx. 13, com muitos empates: desempate por nota e título) |
| Pessoas | Agrupadas por `sk_person_id`; o papel (`Ator`, `Diretor`, `Roteirista`) vem de `dim_people.tipo_pessoa` |

---

## Avaliação

O projeto tem 14 perguntas do enunciado com **SQL de referência escrita à mão** (`evals/golden.py`).

```bash
python -m evals.check_golden          # roda as 14 SQLs de referência direto no banco. NÃO usa a API
python -m evals.run_agent_eval        # compara o agente com a referência. GASTA requisições (padrão: 3 perguntas)
python -m evals.run_agent_eval --ids pop_top5 fin_top10_receita
python -m evals.run_agent_eval --all  # as 14; pode passar de 40 requisições
```

`check_golden` gera `evals/golden_report.md` com o resultado esperado de cada pergunta, para revisão humana.
`run_agent_eval` marca `OK` quando ≥ 80% das entidades da referência aparecem na resposta do agente e `REVISAR` caso
contrário. É um apoio, não uma nota: `REVISAR` pode ser erro do agente ou só uma interpretação diferente.

## Testes

```bash
python -m pytest -q
```

Cobrem: guardrails (aceita e bloqueia), as views contra as tabelas originais, as defesas do banco (escrita bloqueada
mesmo sem o guardrail, truncamento, timeout), o loop do agente com cliente falso (recuperação de erro de SQL,
tentativa de `DROP`, argumentos malformados, limite de rodadas), o fallback entre modelos, a parada em cota esgotada
e o cache. Os testes **não fazem chamadas à API**. Os que dependem do banco são pulados se `data/cinerocket.db` não existir.

---

## Decisões de projeto

**Python puro, sem LangChain/CrewAI.** O fluxo tem uma ferramenta e poucas regras. Um framework adiciona abstração
para depurar, e cada depuração às cegas gasta requisições de uma cota de 50 por dia.

**Camada semântica em vez de regras só no prompt.** Modelos gratuitos pequenos esquecem regras em prompts longos. Nas
views a regra é aplicada sempre e é testável (`tests/test_semantic.py`).

**Esquema no prompt, sem `get_schema`.** Uma requisição a menos por pergunta.

**Temperatura 0.** Mesma pergunta, mesma SQL, o que ajuda a comparar execuções.

## Limitações conhecidas

- A qualidade das respostas depende do modelo gratuito que a OpenRouter entregar. Modelos pequenos podem errar
  SQL de várias junções (dupla ator–diretor, por exemplo). O agente corrige erros de execução, mas **não detecta SQL
  que roda e responde a coisa errada**. Por isso `--show-sql` existe: confira a SQL nas respostas importantes.
- A distinção entre os dois tipos de erro 429 (provider lotado × cota do dia) é uma heurística baseada no guia do
  Rocket Lab (procura `provider` no corpo do erro).
- Filmes duplicados no catálogo não são removidos (ver tabela de qualidade dos dados).
- Sem interface web nem gráficos. O enunciado não exige interface de chat.

## Estrutura

```
cinedata_agent/
  agent.py        loop do agente (tool calling)
  llm.py          cliente OpenRouter, fallback, contagem de requisições
  db.py           conexão somente leitura, limite de linhas e tempo
  guardrails.py   validação da SQL
  semantic.py     views com as regras de qualidade de dados
  prompts.py      prompt de sistema e definição da tool
  cache.py        cache de respostas
  config.py       configuração (.env)
  cli.py          comandos ask, chat, quota, models
evals/            perguntas com SQL de referência e scripts de avaliação
tests/            testes automatizados
data/             coloque aqui o cinerocket.db
```
