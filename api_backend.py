from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import json
import os
from typing import Optional
from container_manager import ContainerManager
import asyncio

app = FastAPI(title="nspawn-ui API", description="Container management API using systemd-nspawn")
container_manager = ContainerManager()

# Mount static files for the web UI
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/js", StaticFiles(directory="static/js"), name="js")

class ContainerCreateRequest(BaseModel):
    name: str
    distribution: str
    release: str = "latest"
    root_password: Optional[str] = None
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    cpu_limit: Optional[int] = None  # percentage
    memory_limit: Optional[int] = None  # in MB
    storage_limit: Optional[int] = None  # in MB

class ContainerActionRequest(BaseModel):
    name: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/containers")
async def list_containers():
    """List all containers with their status, IPs, and resource usage"""
    try:
        containers = container_manager.list_containers()
        return JSONResponse(content=containers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/containers")
async def create_container(request: ContainerCreateRequest):
    """Create a new container"""
    try:
        result = container_manager.create_container(
            name=request.name,
            distribution=request.distribution,
            release=request.release,
            root_password=request.root_password,
            ipv4=request.ipv4,
            ipv6=request.ipv6,
            cpu_limit=request.cpu_limit,
            memory_limit=request.memory_limit,
            storage_limit=request.storage_limit
        )
        return JSONResponse(content={"message": "Container created", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/containers/start")
async def start_container(request: ContainerActionRequest):
    """Start a container"""
    try:
        result = container_manager.start_container(request.name)
        return JSONResponse(content={"message": f"Container {request.name} started", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/containers/stop")
async def stop_container(request: ContainerActionRequest):
    """Stop a container"""
    try:
        result = container_manager.stop_container(request.name)
        return JSONResponse(content={"message": f"Container {request.name} stopped", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/containers/restart")
async def restart_container(request: ContainerActionRequest):
    """Restart a container"""
    try:
        result = container_manager.restart_container(request.name)
        return JSONResponse(content={"message": f"Container {request.name} restarted", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/containers/{name}")
async def remove_container(name: str):
    """Remove a container"""
    try:
        result = container_manager.remove_container(name)
        return JSONResponse(content={"message": f"Container {name} removed", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/containers/{name}/logs")
async def get_container_logs(name: str):
    """Get container logs"""
    try:
        logs = container_manager.get_container_logs(name)
        return JSONResponse(content={"logs": logs})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/networking")
async def get_networking_info():
    """Get networking configuration"""
    try:
        network_info = container_manager.get_networking_info()
        return JSONResponse(content=network_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/networking/setup")
async def setup_networking(request: Request):
    """Setup networking configuration"""
    try:
        data = await request.json()
        network_type = data.get('type')  # 'native', '6in4', 'wireguard'
        config = data.get('config', {})
        
        result = container_manager.setup_networking(network_type, config)
        return JSONResponse(content={"message": "Networking configured", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ssh/setup")
async def setup_ssh(request: Request):
    """Setup SSH inside a container"""
    try:
        data = await request.json()
        container_name = data.get('container_name')
        ssh_config = data.get('ssh_config', {})
        
        result = container_manager.setup_ssh(container_name, ssh_config)
        return JSONResponse(content={"message": "SSH configured", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def api_status():
    """Health check endpoint"""
    return JSONResponse(content={"status": "running", "backend": "systemd-nspawn"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)