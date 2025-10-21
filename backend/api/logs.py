"""
Logging and monitoring API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
from api.auth import verify_token
import asyncio
import subprocess

router = APIRouter()

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    container_id: str

@router.get("/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    lines: int = 100,
    level: Optional[str] = None,
    user: dict = Depends(verify_token)
):
    """Get recent log entries for a container"""
    try:
        # Use journalctl to get container logs
        cmd = ["journalctl", "-u", f"systemd-nspawn@{container_id}", "-n", str(lines), "--no-pager"]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"logs": [], "message": "No logs available"}
        
        return {
            "logs": result.stdout.split('\n'),
            "container_id": container_id,
            "lines": lines
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/containers/{container_id}/metrics")
async def get_container_metrics(container_id: str, user: dict = Depends(verify_token)):
    """Get resource usage metrics for a container"""
    # TODO: Implement metrics collection
    return {
        "container_id": container_id,
        "cpu_percent": 0.0,
        "memory_mb": 0,
        "disk_mb": 0,
        "network_rx_bytes": 0,
        "network_tx_bytes": 0
    }

@router.websocket("/ws/containers/{container_id}/logs")
async def websocket_container_logs(websocket: WebSocket, container_id: str):
    """Stream real-time logs via WebSocket"""
    await websocket.accept()
    
    try:
        # Stream logs in real-time
        process = await asyncio.create_subprocess_exec(
            "journalctl", "-u", f"systemd-nspawn@{container_id}", "-f", "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            await websocket.send_text(line.decode('utf-8'))
    except WebSocketDisconnect:
        if process:
            process.terminate()
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
        await websocket.close()
