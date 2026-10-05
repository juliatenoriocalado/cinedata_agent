"""Roda as SQLs de referência direto no banco (SEM LLM, zero requisições) e gera evals/golden_report.md.

Use para revisar à mão cada resposta esperada antes de comparar o agente com elas.
    python -m evals.check_golden
"""

import sys
from pathlib import Path

from cinedata_agent.agent import ExecutedQuery, format_markdown_table
from cinedata_agent.config import PROJECT_ROOT, Settings
from cinedata_agent.db import connect_readonly, run_query
from evals.golden import GOLDEN


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = Settings.from_env(require_key=False)
    conn = connect_readonly(settings.db_path)

    lines = ["# Relatório das SQLs de referência", "", "Gerado por `python -m evals.check_golden`. Revise cada linha.", ""]
    failures = 0
    for g in GOLDEN:
        lines += [f"## {g.id}", f"**{g.category}**: {g.question}", ""]
        try:
            result = run_query(conn, g.sql, max_rows=50, timeout_s=120)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines += [f"ERRO: `{type(exc).__name__}: {exc}`", ""]
            print(f"FALHOU  {g.id}: {exc}")
            continue
        table = format_markdown_table(
            ExecutedQuery(sql=g.sql, columns=result.columns, rows=[list(r) for r in result.rows]), limit=10
        )
        lines += [f"{len(result.rows)} linhas em {result.elapsed_s:.1f}s.", "", table, ""]
        if g.notes:
            lines += [f"> Nota: {g.notes}", ""]
        print(f"ok      {g.id:34} {len(result.rows):3} linhas  {result.elapsed_s:4.1f}s")

    out = Path(PROJECT_ROOT) / "evals" / "golden_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRelatório salvo em {out.relative_to(PROJECT_ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
