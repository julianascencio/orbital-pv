from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPACE_PV_", env_file=".env", extra="ignore")
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
