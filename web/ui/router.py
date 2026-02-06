"""
Web UI routes for serving HTML templates.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["web"])

# Setup templates directory
WEB_ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, build_id: str = None):
    """
    Render the main index page showing all builds.

    Args:
        request: FastAPI Request object
        build_id: Optional build ID to automatically show log modal and
            trigger artifact download on build completion

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "build_id": build_id}
    )


@router.get("/add_build", response_class=HTMLResponse)
async def add_build(request: Request, rebuild_from: str = None):
    """
    Render the add build page for creating new firmware builds.

    Args:
        request: FastAPI Request object
        rebuild_from: Optional build ID to copy configuration from

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(
        "add_build.html",
        {"request": request, "rebuild_from": rebuild_from}
    )
