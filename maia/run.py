import os
import sys
import uvicorn

# Add the rootfs/app directory to Python path
app_dir = os.path.join(os.path.dirname(__file__), "rootfs", "app")
sys.path.append(app_dir)

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8080, reload=True) 