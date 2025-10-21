"""
Authentication API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
import jwt
from datetime import datetime, timedelta
from core.config import settings

router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    username: str
    message: str

def create_token(username: str) -> str:
    """Create a JWT token for authenticated user"""
    payload = {
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    # For now, simple admin authentication
    # In production, this should check against a database
    if request.username == settings.ADMIN_USERNAME:
        # Check password (for now using simple comparison, should use bcrypt)
        # TODO: Implement proper password hashing
        if request.password == "admin":  # Default password for development
            token = create_token(request.username)
            return LoginResponse(
                token=token,
                username=request.username,
                message="Login successful"
            )
    
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.get("/verify")
async def verify(user: dict = Depends(verify_token)):
    """Verify if the current token is valid"""
    return {"valid": True, "username": user.get("username")}

@router.post("/logout")
async def logout(user: dict = Depends(verify_token)):
    """Logout user (client should discard token)"""
    return {"message": "Logged out successfully"}
