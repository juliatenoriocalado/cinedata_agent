import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "openrouter/free",
]

@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    models: tuple[str, ...] = tuple(DEFAULT_MODELS)
    db_path: Path = PROJECT_ROOT / "data" / "cinerocket.db"
    cache_path: Path = PROJECT_ROOT / ".cache" / "answers.sqlite"
    cache_ttl_hours: int = 24 * 7
    max_rows: int = 50  # linhas devolvidas ao modelo por consulta
    query_timeout_s: float = 30.0
    max_tool_rounds: int = 5  # idas e voltas modelo <-> banco por pergunta
    request_timeout_s: float = 60.0
    history_turns: int = 6  # memória de conversa no modo chat
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, require_key: bool = True) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if require_key and not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY não encontrada. Copie .env.example para .env e preencha a chave "
                "(crie em https://openrouter.ai/keys)."
            )
        models_env = os.getenv("OPENROUTER_MODELS", "").strip()
        models = tuple(m.strip() for m in models_env.split(",") if m.strip()) or tuple(DEFAULT_MODELS)
        db_path = Path(os.getenv("CINEDATA_DB_PATH", PROJECT_ROOT / "data" / "cinerocket.db"))
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            models=models,
            db_path=db_path,
        )
