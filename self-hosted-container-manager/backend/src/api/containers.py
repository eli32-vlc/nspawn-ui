from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import subprocess

router = APIRouter()

class Container(BaseModel):
    name: str
    image: str
    command: Optional[str] = None

@router.post("/containers/", response_model=Container)
async def create_container(container: Container):
    try:
        subprocess.run(["systemd-nspawn", "-D", container.name, "--image", container.image, container.command], check=True)
        return container
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to create container")

@router.get("/containers/", response_model=List[Container])
async def list_containers():
    # Logic to list containers
    return []

@router.post("/containers/{container_name}/start")
async def start_container(container_name: str):
    try:
        subprocess.run(["systemd-nspawn", "-D", container_name, "--boot"], check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to start container")

@router.post("/containers/{container_name}/stop")
async def stop_container(container_name: str):
    try:
        subprocess.run(["systemd-nspawn", "-D", container_name, "--shutdown"], check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to stop container")

@router.delete("/containers/{container_name}")
async def remove_container(container_name: str):
    try:
        subprocess.run(["rm", "-rf", container_name], check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to remove container")