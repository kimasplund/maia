from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiohttp
import os

app = FastAPI(
    title="MAIA",
    description="MAIA - Multi-Agent Intelligence Assistant",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to MAIA - Multi-Agent Intelligence Assistant"}

@app.get("/test_ha_connection")
async def test_ha_connection():
    # Try supervisor URL first (for add-on mode), fallback to HA_URL (for standalone mode)
    ha_url = os.getenv("SUPERVISOR_URL")
    if not ha_url:
        # If running as add-on, use supervisor
        if os.path.exists("/data/options.json"):
            ha_url = "http://supervisor/core"
        else:
            raise HTTPException(status_code=500, detail="Home Assistant URL not configured")
    
    ha_token = os.getenv("SUPERVISOR_TOKEN")
    if not ha_token:
        raise HTTPException(status_code=500, detail="Home Assistant token not configured")
    
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"Attempting to connect to: {ha_url}/api/config")
            print(f"Using token: {ha_token[:10]}...")
            
            # Try different endpoints based on the URL
            if ha_url.endswith("/core"):
                api_url = f"{ha_url}/api/config"  # Add-on mode
            else:
                api_url = f"{ha_url}/api/config"  # Standalone mode
            
            async with session.get(api_url, headers=headers, ssl=False) as response:
                print(f"Response status: {response.status}")
                if response.status == 401:
                    raise HTTPException(status_code=401, detail="Invalid Home Assistant token")
                elif response.status != 200:
                    text = await response.text()
                    print(f"Error response: {text}")
                    raise HTTPException(status_code=response.status, detail=f"Error connecting to Home Assistant: {text}")
                
                config = await response.json()
                return {
                    "status": "connected",
                    "mode": "add-on" if ha_url.endswith("/core") else "standalone",
                    "ha_version": config.get("version", "unknown"),
                    "location_name": config.get("location_name", "unknown")
                }
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Home Assistant: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 