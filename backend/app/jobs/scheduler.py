"""Proceso DEDICADO del planificador — NO corre dentro del proceso web (ver H2).

Ejecuta el pipeline de refresco (universo → fundamentales con frescura por antigüedad
→ scoring) según REFRESH_CRON. Se lanza como su propio proceso/contenedor:

    uv run python -m app.jobs.scheduler        # local
    docker compose: servicio 'scheduler'

Al estar fuera del web se evita: (a) bloquear/competir con la API, y (b) que cada
worker de uvicorn arranque su propio scheduler y duplique el job.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.jobs.refresh_insiders import refresh_insiders, refresh_insiders_uk
from app.jobs.refresh_snapshots import refresh_snapshots
from app.jobs.score_snapshots import score_universe
from app.universe.refresh import refresh_universe


def scheduled_refresh() -> None:
    """Universo → fundamentales (refresco por antigüedad) → scores."""
    refresh_universe()
    refresh_snapshots(max_age_hours=settings.refresh_max_age_hours)
    score_universe()


def scheduled_insider_refresh() -> None:
    """Actividad de insiders con cadencia propia: EE.UU. (SEC EDGAR) + UK (FCA NSM).
    Cada mercado va en su propio try para que un fallo no impida el otro."""
    try:
        refresh_insiders()          # US — Form 4 vía EDGAR
    except Exception as err:        # noqa: BLE001
        print(f"[scheduler] insiders US error: {err}", flush=True)
    try:
        refresh_insiders_uk()       # UK — PDMR vía NSM
    except Exception as err:        # noqa: BLE001
        print(f"[scheduler] insiders UK error: {err}", flush=True)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()
    scheduler.add_job(
        scheduled_refresh,
        CronTrigger.from_crontab(settings.refresh_cron),
        id="refresh",
        max_instances=1,          # no solapar ejecuciones (M7)
        coalesce=True,            # si se acumulan disparos, ejecutar uno solo
        misfire_grace_time=3600,  # si el job previo seguía corriendo, no descartar el disparo
    )
    scheduler.add_job(
        scheduled_insider_refresh,
        CronTrigger.from_crontab(settings.insider_refresh_cron),
        id="insiders",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler


def run() -> None:
    scheduler = build_scheduler()
    print(
        f"[scheduler] iniciado · cron='{settings.refresh_cron}' · "
        f"insiders='{settings.insider_refresh_cron}' · "
        f"max_age={settings.refresh_max_age_hours}h",
        flush=True,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    run()
