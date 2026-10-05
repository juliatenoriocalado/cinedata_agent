"""Validação de SQL antes de executar. Primeira camada de defesa (mensagens claras para o modelo).

A defesa real é dupla e fica em db.py: conexão aberta com mode=ro + sqlite authorizer que
só permite leitura. Esta validação existe para devolver erros que o modelo consiga corrigir.
"""

import re


class UnsafeSQLError(ValueError):
    """SQL recusada pelos guardrails."""


_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_STRINGS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|reindex|"
    r"analyze|begin|commit|rollback|savepoint|release|load_extension)\b"
    r"|\breplace\s+into\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> str:
    """Devolve a SQL limpa (sem comentários e sem ';' final) ou levanta UnsafeSQLError."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("SQL vazia.")

    cleaned = _COMMENTS.sub(" ", sql).strip().rstrip(";").strip()
    # Literais são removidos só para inspeção: um ';' ou 'drop' dentro de texto é inofensivo.
    inspected = _STRINGS.sub("''", cleaned)

    if ";" in inspected:
        raise UnsafeSQLError("Envie apenas uma instrução SQL por chamada (sem ';' no meio).")
    if not re.match(r"(select|with)\b", inspected, re.IGNORECASE):
        raise UnsafeSQLError("Somente consultas de leitura (SELECT ou WITH ... SELECT) são permitidas.")
    forbidden = _FORBIDDEN.search(inspected)
    if forbidden:
        raise UnsafeSQLError(f"Comando não permitido (somente leitura): {forbidden.group(0).upper()}.")
    return cleaned
