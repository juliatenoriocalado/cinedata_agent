"""Interface de linha de comando: ask, chat e quota."""

import argparse
import json
import sys
import urllib.error
import urllib.request

from .agent import AgentResponse, CineDataAgent
from .cache import AnswerCache
from .config import Settings
from .llm import LLMError


def _find_key(data, wanted: str):
    """Procura recursivamente uma chave no JSON (o aninhamento exato da resposta não foi verificado)."""
    if isinstance(data, dict):
        if wanted in data:
            return data[wanted]
        for value in data.values():
            found = _find_key(value, wanted)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_key(value, wanted)
            if found is not None:
                return found
    return None


def cmd_quota(settings: Settings) -> int:
    request = urllib.request.Request(
        f"{settings.base_url}/key", headers={"Authorization": f"Bearer {settings.api_key}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"Erro HTTP {exc.code} ao consultar a cota. Se for 401, confira a chave no .env.")
        return 1
    except urllib.error.URLError as exc:
        print(f"Não consegui falar com a OpenRouter: {exc.reason}")
        return 1

    usage = _find_key(payload, "free_model_daily_requests")
    if isinstance(usage, dict):
        print(
            f"Requisições gratuitas hoje: {usage.get('used')} usadas, "
            f"{usage.get('remaining')} restantes (limite {usage.get('limit')}). Zera às 21h (Brasília)."
        )
    else:
        print("Campo free_model_daily_requests não encontrado. Resposta bruta da API:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_models(settings: Settings) -> int:
    """Lista modelos gratuitos com suporte a tools (endpoint público /models, não exige chave)."""
    try:
        with urllib.request.urlopen(f"{settings.base_url}/models", timeout=30) as resp:
            models = json.load(resp).get("data", [])
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"Não consegui listar os modelos: {exc}")
        return 1

    by_id = {m.get("id"): m for m in models}
    print("Modelos configurados (OPENROUTER_MODELS ou padrão):")
    for model_id in settings.models:
        info = by_id.get(model_id)
        if info is None:
            print(f"  [nao listado] {model_id}")
        else:
            tools = "tools" in (info.get("supported_parameters") or [])
            print(f"  [{'tools ok' if tools else 'SEM tools'}] {model_id}")

    free_tools = sorted(
        m["id"]
        for m in models
        if str(m.get("id", "")).endswith(":free") and "tools" in (m.get("supported_parameters") or [])
    )
    print(f"\nModelos :free com suporte a tools ({len(free_tools)}):")
    for model_id in free_tools:
        print(f"  {model_id}")
    print("\nPara usar outros: OPENROUTER_MODELS=modelo1,modelo2 no .env (a ordem é a do fallback).")
    return 0


def _print_response(response: AgentResponse, show_sql: bool) -> None:
    print()
    print(response.answer)
    if show_sql:
        for i, query in enumerate(response.queries, 1):
            status = f"ERRO: {query.error}" if query.error else f"{len(query.rows)} linhas"
            print(f"\n-- consulta {i} ({status})\n{query.sql}")
    if not response.used_data:
        print("\n[aviso] Esta resposta não veio de uma consulta ao banco. Não confie em números nela.")
    origem = "cache" if response.from_cache else f"modelo {response.model}"
    print(f"\n[{origem} | requisições gastas nesta pergunta: {response.requests_made}]")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # evita erro de acentuação no console do Windows
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="cinedata_agent", description="Agente Text-to-SQL da CineData Analytics")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="faz uma pergunta e sai")
    ask.add_argument("question")
    ask.add_argument("--show-sql", action="store_true", help="mostra a SQL executada")
    ask.add_argument("--no-cache", action="store_true", help="ignora o cache de respostas")

    chat = sub.add_parser("chat", help="conversa com memória (várias perguntas)")
    chat.add_argument("--show-sql", action="store_true")

    sub.add_parser("quota", help="mostra quantas requisições gratuitas restam hoje")
    sub.add_parser("models", help="lista modelos :free que suportam tool calling")

    args = parser.parse_args(argv)

    try:
        if args.command == "models":
            return cmd_models(Settings.from_env(require_key=False))
        settings = Settings.from_env()
        if args.command == "quota":
            return cmd_quota(settings)

        cache = AnswerCache(settings.cache_path, settings.cache_ttl_hours)
        agent = CineDataAgent(settings, cache=cache)

        if args.command == "ask":
            _print_response(agent.ask(args.question, use_cache=not args.no_cache), args.show_sql)
            return 0

        print("Modo chat. Digite sua pergunta (vazio ou 'sair' encerra).")
        history: list[dict] = []
        while True:
            try:
                question = input("\nvocê> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if question.lower() in {"", "sair", "exit", "quit"}:
                break
            response = agent.ask(question, history=history)
            _print_response(response, args.show_sql)
            history += [{"role": "user", "content": question}, {"role": "assistant", "content": response.answer}]
        return 0
    except (LLMError, RuntimeError, FileNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
