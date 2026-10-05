"""Cache de respostas em SQLite local (não confundir com o banco da CineData, que é só leitura).

Perguntas repetidas não gastam requisições da cota diária da API. Só respostas bem-sucedidas
e baseadas em consulta ao banco são guardadas."""

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

# Mude ao alterar prompt, views ou regras: invalida respostas antigas.
CACHE_VERSION = "1"


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower()).rstrip("?!. ")


class AnswerCache:
    def __init__(self, path: Path, ttl_hours: int = 24 * 7):
        self._path = Path(path)
        self._ttl_s = ttl_hours * 3600
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS answers ("
            " key TEXT PRIMARY KEY, question TEXT, payload TEXT, created_at REAL)"
        )

    @staticmethod
    def _key(question: str) -> str:
        return hashlib.sha256(f"{CACHE_VERSION}|{normalize_question(question)}".encode()).hexdigest()

    def get(self, question: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload, created_at FROM answers WHERE key = ?", (self._key(question),)
        ).fetchone()
        if row is None or time.time() - row[1] > self._ttl_s:
            return None
        return json.loads(row[0])

    def put(self, question: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO answers (key, question, payload, created_at) VALUES (?, ?, ?, ?)",
            (self._key(question), question, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
