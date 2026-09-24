from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_INDEX_HTML = Path(__file__).resolve().parents[2] / "web" / "index.html"


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Browser UI for /generate. Served by the gateway itself: a page hosted elsewhere over
    HTTPS could not call a plain-HTTP LAN address (mixed content), and same-origin needs no
    CORS. no-cache so a Watchtower update shows up on the next reload."""
    return FileResponse(
        _INDEX_HTML,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
