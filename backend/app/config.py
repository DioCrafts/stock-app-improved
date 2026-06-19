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
    cache_dir: str = ".cache"  # en Docker apuntar al volumen (CACHE_DIR=/data/cache) para que persista
    db_path: str = "./data/app.db"
    refresh_cron: str = "0 6 * * *"  # usado por el proceso planificador (app.jobs.scheduler)
    refresh_max_age_hours: float = 20  # el planificador refresca snapshots más viejos de esto
    markets: str = "US,CA,UK"
    universe_scope: str = "equities"  # equities | all
    uk_gbp_only: bool = True  # UK: solo empresas en GBP (excluir cross-listings extranjeros)

    # Insiders (SEC EDGAR, solo US). La SEC exige un User-Agent identificable con
    # contacto/email por su política de "fair access" → pon el tuyo en SEC_USER_AGENT.
    sec_user_agent: str = "stock-app-improved insider-research (admin@example.com)"
    insider_max_filings: int = 60      # nº de Form 4 recientes a leer por empresa (incremental)
    insider_refresh_cron: str = "30 7 * * *"  # cron del refresco diario de insiders

    # Insiders UK (FCA NSM, gratis y oficial). User-Agent identificable (servicio del regulador).
    nsm_user_agent: str = "stock-app-improved insider-research (admin@example.com)"
    insider_uk_since_days: int = 4     # ventana del barrido incremental NSM (PDMR por fecha)
    insider_uk_max_pages: int = 40     # tope de páginas del barrido (cota de seguridad)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def markets_list(self) -> list[str]:
        return [m.strip().upper() for m in self.markets.split(",") if m.strip()]


settings = Settings()
