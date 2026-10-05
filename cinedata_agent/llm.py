"""Cliente OpenRouter com fallback entre modelos gratuitos e contagem de requisições.

Regras do Guia OpenRouter (Rocket Lab) que moldam este módulo:
  * Limite gratuito: 50 requisições/dia. Requisições que FALHAM também contam.
    => max_retries=0 no SDK (ele reenviaria sozinho em 429) e nenhum retry imediato.
  * 429 com provider = pool do provider lotado (não é a sua cota) => tentar outro modelo.
  * 429 sem provider = cota do dia acabou => parar; trocar de modelo só gasta mais cota.
  * 401 = chave inválida. 402 = saldo negativo. Ambos: parar.
"""

import json
from collections.abc import Sequence

import openai
from openai import OpenAI

from .config import Settings


class LLMError(RuntimeError):
    """Erro irrecuperável: parar e mostrar a mensagem ao usuário."""


class QuotaExceeded(LLMError):
    pass


class AllModelsFailed(LLMError):
    pass


def _body_text(exc: openai.APIStatusError) -> str:
    body = getattr(exc, "body", None)
    try:
        return json.dumps(body, ensure_ascii=False) if body is not None else str(exc)
    except TypeError:
        return str(exc)


def classify_error(exc: Exception) -> str:
    """Devolve 'fatal_auth' | 'fatal_payment' | 'fatal_quota' | 'try_next'.

    [Suposição] A distinção de 429 por provider é heurística (procura 'provider' no corpo do erro,
    como descreve o guia). Não foi testada contra a API real.
    """
    if isinstance(exc, openai.AuthenticationError):
        return "fatal_auth"
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code == 402:
            return "fatal_payment"
        if exc.status_code == 429:
            return "try_next" if "provider" in _body_text(exc).lower() else "fatal_quota"
    return "try_next"  # 5xx, timeout, conexão, modelo sem suporte a tools (400/404)


class OpenRouterClient:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self._models: Sequence[str] = settings.models
        self._client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout_s,
            max_retries=0,
        )
        self.requests_made = 0  # inclui tentativas que falharam
        self.last_model: str | None = None
        self._preferred = 0  # índice do último modelo que respondeu: as próximas chamadas começam nele

    def complete(self, messages: list[dict], tools: list[dict] | None = None):
        """Uma chamada de chat, com fallback. Tenta cada modelo uma única vez.

        Começa pelo último modelo que funcionou: se o 1º está lotado, não vale gastar uma
        requisição da cota em cada rodada só para descobrir isso de novo.
        """
        errors: list[str] = []
        total = len(self._models)
        for offset in range(total):
            index = (self._preferred + offset) % total
            model = self._models[index]
            self.requests_made += 1
            try:
                response = self._client.chat.completions.create(
                    model=model, messages=messages, tools=tools, temperature=0
                )
            except Exception as exc:  # noqa: BLE001 - classificado abaixo
                kind = classify_error(exc)
                if kind == "fatal_auth":
                    raise LLMError(
                        "Chave da OpenRouter inválida (401). Confira OPENROUTER_API_KEY no .env."
                    ) from exc
                if kind == "fatal_payment":
                    raise LLMError("OpenRouter retornou 402: verifique o saldo da conta.") from exc
                if kind == "fatal_quota":
                    raise QuotaExceeded(
                        "Cota diária de 50 requisições gratuitas atingida (429 sem provider). "
                        "O contador zera às 21h (horário de Brasília). Veja: python -m cinedata_agent quota"
                    ) from exc
                errors.append(f"{model}: {type(exc).__name__}")
                continue
            if not response.choices:  # alguns modelos free devolvem corpo vazio sem erro HTTP
                errors.append(f"{model}: resposta vazia")
                continue
            self.last_model = model
            self._preferred = index
            return response
        raise AllModelsFailed("Nenhum modelo respondeu. Tentativas: " + "; ".join(errors))
