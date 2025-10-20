from pydantic import BaseModel
from typing import List, Optional

class ContainerBase(BaseModel):
    name: str
    image: str
    status: str
    ip_address: Optional[str] = None
    created_at: str

class ContainerCreate(ContainerBase):
    pass

class ContainerUpdate(ContainerBase):
    status: Optional[str] = None
    ip_address: Optional[str] = None

class Container(ContainerBase):
    id: int

class ContainerList(BaseModel):
    containers: List[Container]