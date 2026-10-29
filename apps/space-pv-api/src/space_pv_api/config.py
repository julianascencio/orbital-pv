from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPACE_PV_", env_file=".env", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
