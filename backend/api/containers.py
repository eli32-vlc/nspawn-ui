"""
Container (VPS) management API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from api.auth import verify_token
import subprocess
import json
import asyncio
from services.container_service import container_service

router = APIRouter()

# Track container creation status
creation_status = {}

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
    ipv6_mode: Optional[str] = Field(None, description="IPv6 mode (native, 6in4, wireguard)")
    wireguard_config: Optional[str] = Field(None, description="WireGuard configuration")

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
async def create_container(container: ContainerCreate, background_tasks: BackgroundTasks, user: dict = Depends(verify_token)):
    """Create a new VPS container"""
    try:
        container_id = f"{container.name}"
        
        # Initialize status tracking
        creation_status[container_id] = {
            "status": "initializing",
            "message": "Initializing container creation...",
            "progress": 0,
            "error": None
        }
        
        # Define status callback
        def update_creation_status(message: str):
            if container_id in creation_status:
                creation_status[container_id]["message"] = message
                # Update progress based on message keywords
                if "architecture" in message.lower():
                    creation_status[container_id]["progress"] = 10
                elif "directory" in message.lower():
                    creation_status[container_id]["progress"] = 20
                elif "installing" in message.lower() or "base system" in message.lower():
                    creation_status[container_id]["progress"] = 30
                    creation_status[container_id]["status"] = "installing"
                elif "password" in message.lower():
                    creation_status[container_id]["progress"] = 60
                elif "network" in message.lower():
                    creation_status[container_id]["progress"] = 70
                elif "ssh" in message.lower():
                    creation_status[container_id]["progress"] = 80
                elif "wireguard" in message.lower():
                    creation_status[container_id]["progress"] = 85
                elif "configuration" in message.lower():
                    creation_status[container_id]["progress"] = 90
                elif "starting" in message.lower():
                    creation_status[container_id]["progress"] = 95
                elif "successfully" in message.lower():
                    creation_status[container_id]["progress"] = 100
                    creation_status[container_id]["status"] = "completed"
        
        # Define background task
        def create_container_task():
            try:
                result = container_service.create_container(
                    name=container.name,
                    distro=container.distro,
                    root_password=container.root_password,
                    cpu_quota=container.cpu_quota,
                    memory_mb=container.memory_mb,
                    disk_gb=container.disk_gb,
                    enable_ssh=container.enable_ssh,
                    enable_ipv6=container.enable_ipv6,
                    ipv6_mode=container.ipv6_mode,
                    wireguard_config=container.wireguard_config,
                    status_callback=update_creation_status
                )
                
                if container_id in creation_status:
                    creation_status[container_id]["status"] = "completed"
                    creation_status[container_id]["message"] = "Container created successfully"
                    creation_status[container_id]["progress"] = 100
                    creation_status[container_id]["result"] = result
                    
            except Exception as e:
                if container_id in creation_status:
                    creation_status[container_id]["status"] = "failed"
                    creation_status[container_id]["message"] = str(e)
                    creation_status[container_id]["error"] = str(e)
        
        # Add task to background
        background_tasks.add_task(create_container_task)
        
        return ContainerResponse(
            success=True,
            message=f"VPS {container.name} creation started",
            container_id=container_id,
            data={
                "name": container.name,
                "distro": container.distro,
                "status": "creating"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/create-status/{container_id}")
async def get_creation_status(container_id: str, user: dict = Depends(verify_token)):
    """Get the status of container creation"""
    if container_id not in creation_status:
        raise HTTPException(status_code=404, detail="Container creation status not found")
    
    return creation_status[container_id]

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
