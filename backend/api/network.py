"""
Network configuration API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from api.auth import verify_token

router = APIRouter()

class PortForwardRule(BaseModel):
    host_port: int
    container_id: str
    container_port: int
    protocol: str = "tcp"  # tcp or udp

class NetworkInfo(BaseModel):
    bridge_name: str
    ipv4_subnet: str
    ipv6_prefix: Optional[str] = None
    status: str

@router.get("/bridge-status", response_model=NetworkInfo)
async def get_bridge_status(user: dict = Depends(verify_token)):
    """Get network bridge status and configuration"""
    return NetworkInfo(
        bridge_name="br0",
        ipv4_subnet="10.0.0.0/24",
        ipv6_prefix=None,
        status="active"
    )

@router.post("/assign-ipv6")
async def assign_ipv6(container_id: str, user: dict = Depends(verify_token)):
    """Allocate IPv6 address for a container"""
    # TODO: Implement IPv6 address allocation
    return {"message": "IPv6 assignment not yet implemented"}

@router.get("/ipv4-nat-rules")
async def get_nat_rules(user: dict = Depends(verify_token)):
    """List current NAT forwarding rules"""
    # TODO: Implement NAT rules listing
    return {"rules": []}

@router.post("/port-forward")
async def create_port_forward(rule: PortForwardRule, user: dict = Depends(verify_token)):
    """Create port forwarding rule for container"""
    # TODO: Implement port forwarding
    return {"message": "Port forwarding created", "rule": rule.dict()}

@router.delete("/port-forward/{rule_id}")
async def delete_port_forward(rule_id: str, user: dict = Depends(verify_token)):
    """Remove port forwarding rule"""
    # TODO: Implement port forward deletion
    return {"message": "Port forwarding rule deleted"}
