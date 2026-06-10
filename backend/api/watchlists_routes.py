from __future__ import annotations

from fastapi import APIRouter
from backend.compute.watchlists import list_watchlists, create_watchlist, update_watchlist, delete_watchlist

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


@router.get("")
def get_watchlists():
    return list_watchlists()


@router.post("")
def post_watchlist(body: dict):
    return create_watchlist(body or {})


@router.put("/{watchlist_id}")
def put_watchlist(watchlist_id: str, body: dict):
    return update_watchlist(watchlist_id, body or {}) or {"id": watchlist_id, "status": "not_found"}


@router.delete("/{watchlist_id}")
def remove_watchlist(watchlist_id: str):
    return delete_watchlist(watchlist_id)
