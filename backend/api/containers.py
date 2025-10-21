"""
Container (VPS) management API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from api.auth import verify_token
import subprocess
import json

router = APIRouter()

class ContainerCreate(BaseModel):
    name: str = Field(..., description="Container name")
    distro: str = Field(..., description="Linux distribution (debian, ubuntu, arch)")
    architecture: Optional[str] = Field(None, description="Architecture (arm64, x86_64)")
    root_password: str = Field(..., description="Root password for SSH access")
    cpu_quota: Optional[int] = Field(100, description="CPU quota percentage (100 = 1 core)")
    memory_mb: Optional[int] = Field(512, description="Memory limit in MB")
    disk_gb: Optional[int] = Field(10, description="Disk quota in GB")
    enable_ssh: Optional[bool] = Field(True, description="Enable SSH server")
    enable_ipv6: Optional[bool] = Field(True, description="Enable IPv6 networking")

class ContainerInfo(BaseModel):
    id: str
    name: str
    status: str  # running, stopped, failed
    distro: str
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    cpu_quota: int
    memory_mb: int
    disk_gb: int
    created_at: datetime
    uptime: Optional[str] = None

class ContainerResponse(BaseModel):
    success: bool
    message: str
    container_id: Optional[str] = None
    data: Optional[dict] = None

@router.post("/create", response_model=ContainerResponse)
async def create_container(container: ContainerCreate, user: dict = Depends(verify_token)):
    """Create a new VPS container"""
    try:
        # For now, return a mock response
        # TODO: Implement actual container creation using systemd-nspawn
        container_id = f"vps-{container.name}"
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container.name} created successfully",
            container_id=container_id,
            data={
                "name": container.name,
                "distro": container.distro,
                "status": "creating"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[ContainerInfo])
async def list_containers(user: dict = Depends(verify_token)):
    """List all VPS containers"""
    try:
        # Use machinectl to list containers
        result = subprocess.run(
            ["machinectl", "list", "--no-pager", "--output=json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # If machinectl fails or no containers, return empty list
            return []
        
        # Parse the output and return container list
        # For now, return empty list as placeholder
        return []
    except Exception as e:
        # Return empty list if machinectl not available
        return []

@router.get("/{container_id}", response_model=ContainerInfo)
async def get_container(container_id: str, user: dict = Depends(verify_token)):
    """Get detailed information about a specific VPS container"""
    try:
        # TODO: Implement actual container info retrieval
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{container_id}/start", response_model=ContainerResponse)
async def start_container(container_id: str, user: dict = Depends(verify_token)):
    """Start a stopped VPS container"""
    try:
        result = subprocess.run(
            ["machinectl", "start", container_id],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Failed to start container: {result.stderr}")
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container_id} started successfully"
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{container_id}/stop", response_model=ContainerResponse)
async def stop_container(container_id: str, user: dict = Depends(verify_token)):
    """Stop a running VPS container"""
    try:
        result = subprocess.run(
            ["machinectl", "stop", container_id],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Failed to stop container: {result.stderr}")
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container_id} stopped successfully"
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{container_id}/restart", response_model=ContainerResponse)
async def restart_container(container_id: str, user: dict = Depends(verify_token)):
    """Restart a VPS container"""
    try:
        # Stop then start
        await stop_container(container_id, user)
        await start_container(container_id, user)
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container_id} restarted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{container_id}", response_model=ContainerResponse)
async def delete_container(container_id: str, user: dict = Depends(verify_token)):
    """Delete a VPS container"""
    try:
        # First stop the container
        subprocess.run(["machinectl", "stop", container_id], capture_output=True)
        
        # Then remove it
        result = subprocess.run(
            ["machinectl", "remove", container_id],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Failed to delete container: {result.stderr}")
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container_id} deleted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{container_id}/force-stop", response_model=ContainerResponse)
async def force_stop_container(container_id: str, user: dict = Depends(verify_token)):
    """Force stop an unresponsive VPS container"""
    try:
        result = subprocess.run(
            ["machinectl", "terminate", container_id],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Failed to force stop container: {result.stderr}")
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container_id} force stopped successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
