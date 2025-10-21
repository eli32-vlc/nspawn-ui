#!/usr/bin/env python3
"""
ZenithStack - Self-Hosted Container Management Platform
Main FastAPI application entry point
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
import uvicorn
import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api import containers, network, ssh, system, logs, auth
from core import config

# Initialize FastAPI app
app = FastAPI(
    title="ZenithStack API",
    description="Self-Hosted Container Management Platform using systemd-nspawn",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")
templates = Jinja2Templates(directory=str(frontend_path / "templates"))

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(ssh.router, prefix="/api/ssh", tags=["SSH"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])

# Root endpoint - serve main UI
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/vps/create", response_class=HTMLResponse)
async def create_vps_page(request: Request):
    """Serve the VPS creation wizard page"""
    return templates.TemplateResponse("create_vps.html", {"request": request})

@app.get("/vps/{vps_id}", response_class=HTMLResponse)
async def vps_detail_page(request: Request, vps_id: str):
    """Serve the VPS detail page"""
    return templates.TemplateResponse("vps_detail.html", {"request": request, "vps_id": vps_id})

@app.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    """Serve the network configuration page"""
    return templates.TemplateResponse("network.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Serve the settings page"""
    return templates.TemplateResponse("settings.html", {"request": request})

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "ZenithStack"}

# API documentation redirect
@app.get("/api")
async def api_root():
    """Redirect to API documentation"""
    return {"message": "ZenithStack API", "docs": "/docs", "redoc": "/redoc"}

if __name__ == "__main__":
    # Get configuration
    host = os.getenv("ZENITH_HOST", "0.0.0.0")
    port = int(os.getenv("ZENITH_PORT", "8080"))
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ZENITH_DEBUG", "false").lower() == "true",
        log_level="info"
    )
