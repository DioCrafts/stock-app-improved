"""Tests del proceso planificador (sin red, sin arrancar el scheduler)."""
from apscheduler.schedulers.blocking import BlockingScheduler

from app.jobs import scheduler as sch


def test_scheduled_refresh_pipeline_order(monkeypatch):
    """El pipeline corre en orden: universo → fundamentales → scoring."""
    calls = []
    monkeypatch.setattr(sch, "refresh_universe", lambda: calls.append("universe"))
    monkeypatch.setattr(sch, "refresh_snapshots", lambda **kw: calls.append("snapshots"))
    monkeypatch.setattr(sch, "score_universe", lambda: calls.append("scores"))
    sch.scheduled_refresh()
    assert calls == ["universe", "snapshots", "scores"]


def test_build_scheduler_one_job_with_safe_misfire():
    s = sch.build_scheduler()
    assert isinstance(s, BlockingScheduler)
    jobs = s.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.max_instances == 1
    assert job.misfire_grace_time == 3600
    assert job.coalesce is True
