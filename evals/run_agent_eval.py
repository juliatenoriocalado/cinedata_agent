"""Avalia o agente contra as SQLs de referência. GASTA REQUISIÇÕES da cota diária.

Cada pergunta custa de 2 a 4 requisições. Por isso o padrão é rodar só 3 perguntas.
    python -m evals.run_agent_eval                    # 3 primeiras
    python -m evals.run_agent_eval --ids pop_top5 fin_top10_receita
    python -m evals.run_agent_eval --all              # as 14 (pode passar de 40 requisições)

Critério (automático e propositalmente simples): as entidades da 1ª coluna da referência
(títulos, gêneros, nomes, anos) aparecem entre os valores devolvidos pelo agente.
  OK      >= 80% das entidades presentes
  REVISAR menos que isso. Pode ser erro do agente OU interpretação diferente: leia a SQL.
O resultado é um apoio para a revisão humana, não uma nota.
"""

import argparse
import sys
import time
from pathlib import Path

from cinedata_agent.agent import CineDataAgent
from cinedata_agent.cache import AnswerCache
from cinedata_agent.config import PROJECT_ROOT, Settings
from cinedata_agent.db import connect_readonly, run_query
from cinedata_agent.llm import LLMError, QuotaExceeded
from evals.golden import GOLDEN

THRESHOLD = 0.8


def _norm(value) -> str:
    if isinstance(value, float):
        value = round(value, 2)
    return str(value).strip().lower()


def entity_overlap(reference_rows: list[tuple], agent_rows: list[list]) -> float:
    if not reference_rows or not agent_rows:
        return 0.0
    k = min(len(reference_rows), len(agent_rows))  # compara só o topo que o agente devolveu
    wanted = [_norm(row[0]) for row in reference_rows[:k]]
    got = {_norm(cell) for row in agent_rows for cell in row}
    return sum(1 for w in wanted if w in got) / k


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", help="ids de evals/golden.py")
    parser.add_argument("--all", action="store_true", help="roda todas as perguntas")
    parser.add_argument("--limit", type=int, default=3, help="quantas perguntas rodar (padrão 3)")
    args = parser.parse_args()

    settings = Settings.from_env()
    conn = connect_readonly(settings.db_path)
    agent = CineDataAgent(settings, conn=conn, cache=AnswerCache(settings.cache_path, settings.cache_ttl_hours))

    selected = [g for g in GOLDEN if g.id in args.ids] if args.ids else (GOLDEN if args.all else GOLDEN[: args.limit])
    rows_out = ["# Avaliação do agente", "", "| id | resultado | sobreposição | requisições | modelo |", "|---|---|---|---|---|"]
    details = []
    total_requests = 0

    for g in selected:
        reference = run_query(conn, g.sql, max_rows=50, timeout_s=120)
        try:
            response = agent.ask(g.question, use_cache=False)
        except QuotaExceeded as exc:
            print(f"\nCota esgotada, parando: {exc}")
            break
        except LLMError as exc:
            rows_out.append(f"| {g.id} | ERRO | - | - | - |")
            details.append(f"## {g.id}\nErro: {exc}\n")
            print(f"ERRO    {g.id}: {exc}")
            continue

        last = response.last_result
        overlap = entity_overlap(reference.rows, last.rows if last else [])
        verdict = "OK" if overlap >= THRESHOLD else "REVISAR"
        total_requests += response.requests_made
        rows_out.append(f"| {g.id} | {verdict} | {overlap:.0%} | {response.requests_made} | {response.model} |")
        details.append(
            f"## {g.id} ({verdict})\n**Pergunta:** {g.question}\n\n**Resposta do agente:**\n\n{response.answer}\n\n"
            f"**SQL do agente:**\n```sql\n{last.sql if last else '(nenhuma)'}\n```\n"
            f"**SQL de referência:**\n```sql\n{g.sql.strip()}\n```\n"
        )
        print(f"{verdict:8}{g.id:34} {overlap:4.0%}  {response.requests_made} req")
        time.sleep(3)  # limite de 20 requisições/minuto

    out = Path(PROJECT_ROOT) / "evals" / "agent_report.md"
    out.write_text("\n".join(rows_out + ["", f"Total de requisições: {total_requests}", ""] + details), encoding="utf-8")
    print(f"\nTotal de requisições: {total_requests}. Relatório em {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())