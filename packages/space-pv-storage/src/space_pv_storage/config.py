from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """Storage configuration shared by API, workers and local labs."""

    model_config = SettingsConfigDict(env_prefix="SPACE_PV_", env_file=".env", extra="ignore")

    postgres_dsn: str = "postgresql+psycopg://spacepv:spacepv@localhost:5432/spacepv"
    duckdb_path: Path = Path("data/space_pv.duckdb")
