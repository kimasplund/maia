"""
Main API module for MAIA.
"""
import os
from datetime import timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from ..core.ha_client import HAClient

app = FastAPI(title="MAIA", description="MAIA - Multi-modal AI Assistant")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the base directory
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Mount static files
static_dir = os.path.join(base_dir, "rootfs", "app", "web", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configure templates
templates_dir = os.path.join(base_dir, "rootfs", "app", "web", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Initialize Home Assistant client
ha_client = None

@app.on_event("startup")
async def startup_event():
    """Initialize the Home Assistant client on startup."""
    global ha_client
    try:
        ha_client = HAClient()
        if not await ha_client.validate_token():
            raise ValueError("Invalid Home Assistant token")
            
        # Register MAIA as a device in Home Assistant
        await ha_client.register_device({
            "name": "MAIA",
            "manufacturer": "Kim Asplund",
            "model": "MAIA v1.0",
            "identifiers": ["maia_assistant"],
            "sw_version": "1.0.0"
        })
    except Exception as e:
        print(f"Failed to initialize Home Assistant client: {e}")
        raise

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Validate credentials against Home Assistant."""
    if not ha_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Home Assistant connection not available"
        )
    
    # Use the provided token to validate against Home Assistant
    headers = {"Authorization": f"Bearer {form_data.password}"}
    try:
        async with ha_client.session.get(f"{ha_client.base_url}/api/", headers=headers) as response:
            if response.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Home Assistant token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return {"access_token": form_data.password, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/")
async def root(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "message": "Welcome to MAIA - Multi-modal AI Assistant"
    })

@app.get("/login")
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "ha_url": ha_client.base_url if ha_client else None
    })

@app.get("/api/status")
async def get_status():
    """Get MAIA status and Home Assistant connection info."""
    if not ha_client:
        return {
            "status": "error",
            "message": "Not connected to Home Assistant"
        }
    
    try:
        config = await ha_client.get_config()
        return {
            "status": "ok",
            "ha_version": config.get("version"),
            "ha_url": ha_client.base_url,
            "maia_version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        } 