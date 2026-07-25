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
async def index(request: Request):
    """
    Render the main index page showing all builds.

    Args:
        request: FastAPI Request object

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@router.get("/add_build", response_class=HTMLResponse)
async def add_build(request: Request):
    """
    Render the add build page for creating new firmware builds.

    Args:
        request: FastAPI Request object

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(
        "add_build.html",
        {"request": request}
    )
