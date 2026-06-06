"""Configuración central de la aplicación (pydantic-settings).

Único punto que conoce la configuración: el resto de módulos importan `settings`
desde aquí. Lee variables de entorno y/o un fichero `.env`.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    cors_origins: str = "http://localhost:5173"  # coma-separado
    cache_ttl_seconds: int = 900
    db_path: str = "./data/app.db"
    refresh_cron: str = "0 6 * * *"
    refresh_max_age_hours: float = 20  # el cron refresca snapshots más viejos de esto
    enable_scheduler: bool = False  # arrancar el job batch dentro del proceso web (por defecto off)
    markets: str = "US,CA,UK"
    universe_scope: str = "equities"  # equities | all
    uk_gbp_only: bool = True  # UK: solo empresas en GBP (excluir cross-listings extranjeros)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def markets_list(self) -> list[str]:
        return [m.strip().upper() for m in self.markets.split(",") if m.strip()]


settings = Settings()
