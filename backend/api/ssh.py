"""
SSH configuration API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.auth import verify_token

router = APIRouter()

class SSHSetupRequest(BaseModel):
    container_id: str
    root_password: str
    port: int = 22
    permit_root_login: bool = True

@router.post("/setup")
async def setup_ssh(request: SSHSetupRequest, user: dict = Depends(verify_token)):
    """Install and configure SSH server inside container"""
    # TODO: Implement SSH setup
    return {
        "message": "SSH setup initiated",
        "container_id": request.container_id,
        "ssh_port": request.port
    }

@router.get("/{container_id}/status")
async def get_ssh_status(container_id: str, user: dict = Depends(verify_token)):
    """Check if SSH is configured and running in container"""
    # TODO: Implement SSH status check
    return {
        "container_id": container_id,
        "ssh_enabled": False,
        "ssh_running": False
    }
