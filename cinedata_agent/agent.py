"""Loop do agente: pergunta -> (modelo chama run_sql -> banco responde)* -> resposta final.

Python puro, sem framework de agentes: o fluxo tem uma única ferramenta e poucas regras, e cada
camada extra de abstração custaria requisições da cota diária (50/dia) ao depurar."""

import json
import sqlite3
from dataclasses import asdict, dataclass, field

from .cache import AnswerCache
from .config import Settings
from .db import QueryTimeout, connect_readonly, run_query
from .guardrails import UnsafeSQLError
from .llm import OpenRouterClient
from .prompts import SYSTEM_PROMPT, TOOLS


@dataclass
class ExecutedQuery:
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None


@dataclass
class AgentResponse:
    answer: str
    queries: list[ExecutedQuery]
    model: str | None
    requests_made: int
    from_cache: bool = False

    @property
    def used_data(self) -> bool:
        """False = a resposta não veio de nenhuma consulta bem-sucedida (não confie em números)."""
        return any(q.error is None for q in self.queries)

    @property
    def last_result(self) -> ExecutedQuery | None:
        ok = [q for q in self.queries if q.error is None]
        return ok[-1] if ok else None


def _round(value):
    return round(value, 4) if isinstance(value, float) else value


def format_markdown_table(query: ExecutedQuery, limit: int = 20) -> str:
    """Tabela de apoio, usada quando o modelo não entrega uma resposta final utilizável."""
    header = "| " + " | ".join(query.columns) + " |"
    sep = "|" + "---|" * len(query.columns)
    lines = [header, sep]
    for row in query.rows[:limit]:
        lines.append("| " + " | ".join(str(_round(v)) for v in row) + " |")
    return "\n".join(lines)


class CineDataAgent:
    def __init__(
        self,
        settings: Settings,
        llm: OpenRouterClient | None = None,
        conn: sqlite3.Connection | None = None,
        cache: AnswerCache | None = None,
    ):
        self._settings = settings
        self._llm = llm or OpenRouterClient(settings)
        self._conn = conn or connect_readonly(settings.db_path)
        self._cache = cache

    # ------------------------------------------------------------------ API
    def ask(self, question: str, history: list[dict] | None = None, use_cache: bool = True) -> AgentResponse:
        history = history or []
        cacheable = use_cache and self._cache is not None and not history

        if cacheable:
            hit = self._cache.get(question)
            if hit:
                queries = [ExecutedQuery(**q) for q in hit["queries"]]
                return AgentResponse(hit["answer"], queries, hit["model"], 0, from_cache=True)

        before = self._llm.requests_made
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-self._settings.history_turns * 2 :]
        messages.append({"role": "user", "content": question})
        queries: list[ExecutedQuery] = []
        answer = ""

        for _ in range(self._settings.max_tool_rounds):
            response = self._llm.complete(messages, tools=TOOLS)
            message = response.choices[0].message
            tool_calls = list(message.tool_calls or [])
            if not tool_calls:
                answer = (message.content or "").strip()
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments},
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": self._execute_tool(call, queries)}
                )

        result = AgentResponse(
            answer=answer or self._fallback_answer(queries),
            queries=queries,
            model=self._llm.last_model,
            requests_made=self._llm.requests_made - before,
        )
        if cacheable and result.used_data and answer:
            self._cache.put(
                question,
                {"answer": result.answer, "queries": [asdict(q) for q in queries], "model": result.model},
            )
        return result

    # ------------------------------------------------------------- internals
    def _execute_tool(self, call, queries: list[ExecutedQuery]) -> str:
        if call.function.name != "run_sql":
            return json.dumps({"error": f"Ferramenta desconhecida: {call.function.name}. Use run_sql."}, ensure_ascii=False)
        try:
            args = json.loads(call.function.arguments or "{}")
            sql = args["sql"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return json.dumps(
                {"error": 'Argumentos inválidos. Envie JSON no formato {"sql": "SELECT ..."}.'}, ensure_ascii=False
            )

        executed = ExecutedQuery(sql=str(sql))
        queries.append(executed)
        try:
            result = run_query(
                self._conn, sql, max_rows=self._settings.max_rows, timeout_s=self._settings.query_timeout_s
            )
        except (UnsafeSQLError, QueryTimeout, sqlite3.Error) as exc:
            executed.error = f"{type(exc).__name__}: {exc}"
            return json.dumps({"error": executed.error}, ensure_ascii=False)

        executed.sql = result.sql
        executed.columns = result.columns
        executed.rows = [[_round(v) for v in row] for row in result.rows]
        executed.truncated = result.truncated
        payload = {
            "columns": executed.columns,
            "rows": executed.rows,
            "row_count": len(executed.rows),
            "truncated": executed.truncated,
        }
        if not executed.rows:
            payload["aviso"] = (
                "A consulta rodou mas retornou 0 linhas. Provável erro de filtro ou junção: "
                "revise a SQL antes de concluir que não existem dados."
            )
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _fallback_answer(queries: list[ExecutedQuery]) -> str:
        ok = [q for q in queries if q.error is None]
        if not ok:
            return "Não consegui montar uma consulta válida para essa pergunta. Tente reformular."
        if not ok[-1].rows:
            return (
                "As consultas rodaram, mas nenhuma retornou linhas, e o modelo não conseguiu uma resposta. "
                "Isso costuma indicar uma SQL com filtro errado. Use --show-sql para ver o que foi tentado."
            )
        return (
            "O modelo não gerou um texto final, mas a consulta rodou. Resultado bruto:\n\n"
            + format_markdown_table(ok[-1])
        )