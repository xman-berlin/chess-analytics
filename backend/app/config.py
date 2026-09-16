from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    chess_username: str = "TorstenGeise"
    time_classes: str = "daily"
    stockfish_path: str = "stockfish"
    analysis_depth: int = 16
    analysis_limit: int = 50
    sync_interval_hours: int = 6
    database_url: str = "sqlite:///./data/chess.db"
    cors_origins: str = "http://localhost:4200"

    @property
    def time_class_list(self) -> list[str]:
        return [t.strip() for t in self.time_classes.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        raw = self.database_url.replace("sqlite:///", "", 1)
        path = Path(raw)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
