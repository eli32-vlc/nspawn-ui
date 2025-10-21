"""
System management API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from api.auth import verify_token
import platform
import psutil
from datetime import datetime

router = APIRouter()

class SystemInfo(BaseModel):
    version: str
    uptime: str
    architecture: str
    hostname: str
    cpu_count: int
    total_memory_mb: int
    available_memory_mb: int
    disk_total_gb: float
    disk_available_gb: float

class Distribution(BaseModel):
    name: str
    versions: List[str]
    architectures: List[str]

@router.get("/info", response_model=SystemInfo)
async def get_system_info(user: dict = Depends(verify_token)):
    """Get system information and resource availability"""
    try:
        # Get system information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time)
        
        return SystemInfo(
            version="1.0.0",
            uptime=uptime,
            architecture=platform.machine(),
            hostname=platform.node(),
            cpu_count=psutil.cpu_count(),
            total_memory_mb=memory.total // (1024 * 1024),
            available_memory_mb=memory.available // (1024 * 1024),
            disk_total_gb=disk.total / (1024**3),
            disk_available_gb=disk.free / (1024**3)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources")
async def get_system_resources(user: dict = Depends(verify_token)):
    """Get current system resource usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/distros/available", response_model=List[Distribution])
async def get_available_distros(user: dict = Depends(verify_token)):
    """List supported distributions and architectures"""
    # Detect host architecture
    arch = platform.machine()
    
    # Map architecture names
    if arch in ["aarch64", "arm64"]:
        supported_archs = ["arm64"]
    elif arch in ["x86_64", "amd64"]:
        supported_archs = ["x86_64"]
    else:
        supported_archs = [arch]
    
    distros = [
        Distribution(
            name="debian",
            versions=["bookworm", "bullseye", "sid"],
            architectures=supported_archs
        ),
        Distribution(
            name="ubuntu",
            versions=["22.04", "20.04", "24.04"],
            architectures=supported_archs
        ),
        Distribution(
            name="arch",
            versions=["latest"],
            architectures=supported_archs
        ),
    ]
    
    return distros

@router.post("/distros/refresh")
async def refresh_distros(user: dict = Depends(verify_token)):
    """Update available distribution templates"""
    # TODO: Implement distribution template refresh
    return {"message": "Distribution templates refreshed"}
