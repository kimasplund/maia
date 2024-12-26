"""
Web interface for MAIA.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MAIA Web Interface",
    description="Web interface for MAIA - My AI Assistant",
    version="1.0.0"
)

# Setup static files and templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render index page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.get("/camera", response_class=HTMLResponse)
async def camera(request: Request):
    """Render camera page."""
    return templates.TemplateResponse(
        "camera.html",
        {"request": request}
    )

@app.get("/voice", response_class=HTMLResponse)
async def voice(request: Request):
    """Render voice page."""
    return templates.TemplateResponse(
        "voice.html",
        {"request": request}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Render settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {"request": request}
    )

@app.get("/faces", response_class=HTMLResponse)
async def faces(request: Request):
    """Render face management page."""
    return templates.TemplateResponse(
        "faces.html",
        {"request": request}
    ) 