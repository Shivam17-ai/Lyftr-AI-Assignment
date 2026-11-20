import os
from pathlib import Path
from typing import List, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_sqlite_path(database_url: str) -> str:
    """Extract filesystem path from SQLite connection string."""
    url = database_url.strip()
    prefix = "sqlite:///"
    if url.startswith(prefix):
        path_part = url[len(prefix):]
        # In sqlite:////data/app.db, path_part is "/data/app.db"
        # On Windows, path_part might be "D:/app.db" or "./app.db"
        if not path_part:
            path_part = "app.db"
    else:
        path_part = url or "app.db"

    # Convert to Path object
    db_path = Path(path_part)
    # Ensure parent directory exists if a parent is specified
    if db_path.parent and str(db_path.parent) not in (".", ""):
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return str(db_path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    LLM_API_KEYS: str = ""
    LLM_MODELS: str = "groq/llama-3.3-70b-versatile"
    DATABASE_URL: str = "sqlite:////data/app.db"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
    ENABLE_FAILURE_SIMULATION: str = "false"
    DEFAULT_SYSTEM_PROMPT: str = "You are a helpful, concise assistant."
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: float = 30.0
    CACHE_TYPE: str = "local"
    CACHE_DIR: str = "/data/cache"

    @property
    def api_keys(self) -> List[str]:
        raw = self.LLM_API_KEYS.split(",")
        return [k.strip() for k in raw if k.strip()]

    @property
    def models(self) -> List[str]:
        raw = self.LLM_MODELS.split(",")
        parsed = [m.strip() for m in raw if m.strip()]
        if not parsed:
            return ["groq/llama-3.3-70b-versatile"]
        return parsed

    @property
    def primary_model(self) -> str:
        return self.models[0]

    @property
    def key_pool(self) -> List[Tuple[str, str, str]]:
        """
        Returns list of tuples: (key_id, api_key, model_name).
        key_id is assigned by 1-based position: key_1, key_2, ...
        If only one model is given, it applies to all keys.
        If fewer models than keys, reuse the last model for remaining keys.
        """
        keys = self.api_keys
        model_list = self.models
        pool = []
        for idx, key in enumerate(keys, start=1):
            key_id = f"key_{idx}"
            if idx - 1 < len(model_list):
                model = model_list[idx - 1]
            else:
                model = model_list[-1]
            pool.append((key_id, key, model))
        return pool

    @property
    def cors_origins(self) -> List[str]:
        raw = self.ALLOWED_ORIGINS.split(",")
        origins = [o.strip() for o in raw if o.strip()]
        return origins or ["*"]

    @property
    def is_failure_simulation_enabled(self) -> bool:
        return self.ENABLE_FAILURE_SIMULATION.strip().lower() == "true"

    @property
    def sqlite_db_path(self) -> str:
        return parse_sqlite_path(self.DATABASE_URL)


settings = Settings()
