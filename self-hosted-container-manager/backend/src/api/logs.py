from fastapi import APIRouter, HTTPException
import logging
import os

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_DIR = "/var/log/containers"

@router.get("/logs/{container_id}")
async def get_container_logs(container_id: str):
    log_file_path = os.path.join(LOG_DIR, f"{container_id}.log")
    
    if not os.path.exists(log_file_path):
        raise HTTPException(status_code=404, detail="Log file not found")
    
    with open(log_file_path, "r") as log_file:
        logs = log_file.read()
    
    logger.info(f"Retrieved logs for container: {container_id}")
    return {"container_id": container_id, "logs": logs}

@router.get("/logs")
async def list_container_logs():
    try:
        log_files = os.listdir(LOG_DIR)
        container_logs = [log_file.replace(".log", "") for log_file in log_files if log_file.endswith(".log")]
        logger.info("Listed container logs")
        return {"containers": container_logs}
    except Exception as e:
        logger.error(f"Error listing logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")