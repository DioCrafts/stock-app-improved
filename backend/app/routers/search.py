"""Endpoint de búsqueda → GlobalSearch (cabecera, ⌘K).

    GET /search?q=   (por ticker o nombre, sobre el universo)
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.company import SearchHit
from app.services import company_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchHit])
def search(q: str = Query("", description="ticker o nombre"), limit: int = Query(10, ge=1, le=50)):
    q = q.strip()
    if not q:
        return []
    return company_service.search(q, limit)
