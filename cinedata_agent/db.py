"""Acesso ao banco: somente leitura, com limite de linhas e de tempo.

Defesa em camadas:
  1. guardrails.validate_sql  -> mensagens claras para o modelo corrigir
  2. mode=ro + PRAGMA query_only -> o SQLite recusa qualquer escrita
  3. set_authorizer -> só SELECT/READ/FUNCTION/RECURSIVE passam, mesmo que 1 e 2 falhem
"""

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .guardrails import validate_sql
from .semantic import VIEWS_DDL

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


def _authorizer(action, arg1, arg2, dbname, source):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Abre o banco só para leitura e cria as views da camada semântica (schema temp)."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em {db_path}. Baixe o cinerocket.db do drive da atividade "
            "e coloque em data/cinerocket.db (ou defina CINEDATA_DB_PATH no .env)."
        )
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    for ddl in VIEWS_DDL:  # antes do authorizer: criar view é uma escrita (no schema temp)
        conn.execute(ddl)
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(_authorizer)
    return conn


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_s: float


class QueryTimeout(RuntimeError):
    pass


def run_query(conn: sqlite3.Connection, sql: str, max_rows: int = 50, timeout_s: float = 30.0) -> QueryResult:
    """Valida e executa uma consulta. Levanta UnsafeSQLError, sqlite3.Error ou QueryTimeout."""
    cleaned = validate_sql(sql)
    deadline = time.monotonic() + timeout_s

    def _check_deadline() -> int:
        return 1 if time.monotonic() > deadline else 0  # != 0 interrompe a consulta

    conn.set_progress_handler(_check_deadline, 100_000)
    started = time.monotonic()
    try:
        cursor = conn.execute(cleaned)
        columns = [d[0] for d in cursor.description or []]
        fetched = cursor.fetchmany(max_rows + 1)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryTimeout(
                f"A consulta passou de {timeout_s:.0f}s. Simplifique: filtre antes de juntar tabelas grandes."
            ) from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)

    truncated = len(fetched) > max_rows
    return QueryResult(
        sql=cleaned,
        columns=columns,
        rows=fetched[:max_rows],
        truncated=truncated,
        elapsed_s=time.monotonic() - started,
    )
