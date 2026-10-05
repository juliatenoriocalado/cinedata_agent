"""Testa o loop do agente, o fallback e o cache com um cliente falso: zero requisições à API."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import openai
import pytest

from cinedata_agent.agent import CineDataAgent
from cinedata_agent.cache import AnswerCache, normalize_question
from cinedata_agent.config import Settings
from cinedata_agent.llm import AllModelsFailed, LLMError, OpenRouterClient, QuotaExceeded, classify_error
from conftest import needs_db


# ------------------------------------------------------------------ helpers
def status_error(cls, status: int, body: dict):
    response = Mock()
    response.status_code = status
    response.headers = {}
    return cls(f"erro {status}", response=response, body=body)


def reply(content=None, sql=None, call_id="call_1", raw_arguments=None):
    """Monta uma resposta no formato do SDK: texto final ou uma chamada à tool run_sql."""
    calls = None
    if sql is not None or raw_arguments is not None:
        arguments = raw_arguments if raw_arguments is not None else json.dumps({"sql": sql})
        calls = [SimpleNamespace(id=call_id, function=SimpleNamespace(name="run_sql", arguments=arguments))]
    message = SimpleNamespace(content=content, tool_calls=calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeSDK:
    """Substitui openai.OpenAI: devolve (ou levanta) o que estiver na fila, na ordem."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))  # o agente muda a lista depois da chamada
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def settings(models=("model-a", "model-b")):
    return Settings(api_key="test", models=tuple(models), max_tool_rounds=4)


# ------------------------------------------------------- classificação de erros
def test_classify_errors():
    assert classify_error(status_error(openai.AuthenticationError, 401, {})) == "fatal_auth"
    assert classify_error(status_error(openai.RateLimitError, 429, {"error": {"metadata": {"provider_name": "X"}}})) == "try_next"
    assert classify_error(status_error(openai.RateLimitError, 429, {"error": {"message": "limit"}})) == "fatal_quota"
    assert classify_error(status_error(openai.APIStatusError, 402, {})) == "fatal_payment"
    assert classify_error(status_error(openai.APIStatusError, 503, {})) == "try_next"
    assert classify_error(RuntimeError("qualquer outro")) == "try_next"


# ------------------------------------------------------------ fallback (llm.py)
def test_fallback_goes_to_next_model_on_provider_429():
    provider_busy = status_error(openai.RateLimitError, 429, {"error": {"metadata": {"provider_name": "X"}}})
    sdk = FakeSDK([provider_busy, reply(content="ok")])
    client = OpenRouterClient(settings(), client=sdk)
    client.complete([{"role": "user", "content": "oi"}])
    assert [c["model"] for c in sdk.calls] == ["model-a", "model-b"]
    assert client.last_model == "model-b" and client.requests_made == 2


def test_next_call_starts_from_the_model_that_worked():
    provider_busy = status_error(openai.RateLimitError, 429, {"error": {"metadata": {"provider_name": "X"}}})
    sdk = FakeSDK([provider_busy, reply(content="1"), reply(content="2")])
    client = OpenRouterClient(settings(), client=sdk)
    client.complete([])
    client.complete([])
    assert [c["model"] for c in sdk.calls] == ["model-a", "model-b", "model-b"]  # 3 requisições, não 4
    assert client.requests_made == 3


def test_daily_quota_stops_without_trying_other_models():
    sdk = FakeSDK([status_error(openai.RateLimitError, 429, {"error": {"message": "limit"}})])
    client = OpenRouterClient(settings(), client=sdk)
    with pytest.raises(QuotaExceeded):
        client.complete([])
    assert len(sdk.calls) == 1  # não queimou mais cota


def test_invalid_key_stops_immediately():
    sdk = FakeSDK([status_error(openai.AuthenticationError, 401, {})])
    with pytest.raises(LLMError, match="401"):
        OpenRouterClient(settings(), client=sdk).complete([])
    assert len(sdk.calls) == 1


def test_all_models_failing_raises():
    sdk = FakeSDK([status_error(openai.APIStatusError, 503, {}), reply_empty()])
    with pytest.raises(AllModelsFailed):
        OpenRouterClient(settings(), client=sdk).complete([])


def reply_empty():
    return SimpleNamespace(choices=[])


# -------------------------------------------------------------- loop do agente
@needs_db
def test_agent_runs_sql_then_answers(conn):
    sdk = FakeSDK([reply(sql="SELECT COUNT(*) AS n FROM v_filmes"), reply(content="Há 95.645 filmes.")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    result = agent.ask("Quantos filmes existem?")
    assert result.answer == "Há 95.645 filmes."
    assert result.used_data and result.last_result.rows == [[95645]]
    assert result.requests_made == 2
    # o resultado do banco voltou ao modelo como mensagem da tool
    tool_msg = [m for m in sdk.calls[1]["messages"] if m["role"] == "tool"][0]
    assert json.loads(tool_msg["content"])["rows"] == [[95645]]


@needs_db
def test_agent_recovers_from_sql_error(conn):
    sdk = FakeSDK(
        [
            reply(sql="SELECT coluna_que_nao_existe FROM v_filmes"),
            reply(sql="SELECT COUNT(*) FROM v_filmes", call_id="call_2"),
            reply(content="Corrigido."),
        ]
    )
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    result = agent.ask("teste")
    assert [q.error is None for q in result.queries] == [False, True]
    assert "no such column" in sdk.calls[1]["messages"][-1]["content"]  # o erro chegou ao modelo
    assert result.answer == "Corrigido."


@needs_db
def test_agent_blocks_destructive_sql_and_database_stays_intact(conn):
    sdk = FakeSDK([reply(sql="DROP TABLE dim_movies"), reply(content="Não posso alterar o banco.")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    result = agent.ask("apague a tabela de filmes")
    assert result.queries[0].error and "UnsafeSQLError" in result.queries[0].error
    assert not result.used_data
    assert conn.execute("SELECT COUNT(*) FROM dim_movies").fetchone()[0] == 95645


@needs_db
def test_agent_handles_malformed_tool_arguments(conn):
    sdk = FakeSDK([reply(raw_arguments="{não é json"), reply(content="ok")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    result = agent.ask("teste")
    assert "Argumentos inválidos" in sdk.calls[1]["messages"][-1]["content"]
    assert result.answer == "ok"


@needs_db
def test_agent_stops_after_max_rounds_and_returns_raw_table(conn):
    script = [reply(sql="SELECT 1 AS x", call_id=f"c{i}") for i in range(4)]
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=FakeSDK(script)), conn=conn)
    result = agent.ask("loop infinito")
    assert "Resultado bruto" in result.answer and result.requests_made == 4


@needs_db
def test_answer_without_query_is_flagged(conn):
    sdk = FakeSDK([reply(content="Só falo de filmes.")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    assert not agent.ask("qual a capital da França?").used_data


# ----------------------------------------------------------------------- cache
@needs_db
def test_cache_avoids_second_api_call(conn, tmp_path):
    cache = AnswerCache(tmp_path / "c.sqlite")
    sdk = FakeSDK([reply(sql="SELECT COUNT(*) FROM v_filmes"), reply(content="95.645")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn, cache=cache)
    first = agent.ask("Quantos filmes existem?")
    second = agent.ask("  quantos FILMES existem ?  ")  # mesma pergunta, outra grafia
    assert not first.from_cache and second.from_cache
    assert second.requests_made == 0 and second.answer == "95.645"
    assert len(sdk.calls) == 2  # só a primeira pergunta chamou a API


@needs_db
def test_cache_is_skipped_when_conversation_has_history(conn, tmp_path):
    cache = AnswerCache(tmp_path / "c.sqlite")
    cache.put("x", {"answer": "velha", "queries": [], "model": "m"})
    sdk = FakeSDK([reply(sql="SELECT 1"), reply(content="nova")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn, cache=cache)
    result = agent.ask("x", history=[{"role": "user", "content": "antes"}, {"role": "assistant", "content": "sim"}])
    assert result.answer == "nova"


def test_normalize_question():
    assert normalize_question("  Top 10   Filmes?? ") == normalize_question("top 10 filmes")


@needs_db
def test_empty_result_gets_a_warning_for_the_model(conn):
    sdk = FakeSDK([reply(sql="SELECT titulo FROM v_filmes WHERE 1 = 0"), reply(content="ok")])
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=sdk), conn=conn)
    agent.ask("teste")
    tool_msg = json.loads(sdk.calls[1]["messages"][-1]["content"])
    assert tool_msg["row_count"] == 0 and "0 linhas" in tool_msg["aviso"]


@needs_db
def test_fallback_with_only_empty_results_is_honest(conn):
    script = [reply(sql="SELECT 1 WHERE 0", call_id=f"c{i}") for i in range(4)]
    agent = CineDataAgent(settings(), llm=OpenRouterClient(settings(), client=FakeSDK(script)), conn=conn)
    result = agent.ask("loop")
    assert "nenhuma retornou linhas" in result.answer and "Resultado bruto" not in result.answer


def test_entity_overlap_compares_only_the_top_returned():
    from evals.run_agent_eval import entity_overlap

    reference = [("Horror", 1), ("Adventure", 2), ("Drama", 3)]
    assert entity_overlap(reference, [["Horror", 1]]) == 1.0  # pergunta singular: 1 linha, e é a 1ª
    assert entity_overlap(reference, [["War", 1]]) == 0.0
    assert entity_overlap(reference, []) == 0.0