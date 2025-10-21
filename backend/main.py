from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import subprocess
import json
import os
import pwd
import grp
import hashlib
import secrets
import time
import logging
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import sqlite3
import threading
from contextlib import contextmanager

# Initialize FastAPI app
app = FastAPI(title="nspawn-vps API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security setup
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Database setup (SQLite for simplicity)
DATABASE_PATH = "/etc/nspawn-manager/containers.db"

def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create containers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            distro TEXT NOT NULL,
            architecture TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'stopped',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ip_address TEXT,
            cpu_limit TEXT,
            memory_limit TEXT,
            storage_limit TEXT,
            config TEXT
        )
    """)
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a database connection"""
    return sqlite3.connect(DATABASE_PATH)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    # Create config directory if it doesn't exist
    os.makedirs("/etc/nspawn-manager", exist_ok=True)
    init_db()
    
    # Create default admin user if it doesn't exist
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if admin user exists
    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cursor.fetchone():
        # Create default admin user
        hashed_password = pwd_context.hash(os.getenv("ADMIN_PASSWORD", "admin123"))
        cursor.execute(
            "INSERT INTO users (username, hashed_password, created_at, is_admin) VALUES (?, ?, ?, ?)",
            ("admin", hashed_password, datetime.now().isoformat(), 1)
        )
        conn.commit()
    
    conn.close()

# Enhanced security middleware
@app.middleware("http")
async def security_middleware(request, call_next):
    # Add security headers
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Enhanced authentication and authorization
async def get_current_user_with_role(required_role: str = "user"):
    """Get current user with role verification"""
    async def get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, is_admin FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user is None:
            raise credentials_exception
        
        # Check role requirements
        is_admin = bool(user[1])  # is_admin field
        if required_role == "admin" and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        
        return {"username": user[0], "is_admin": is_admin}
    
    return get_user

# Add rate limiting simulation (in production, use a proper rate limiter)
request_counts = {}
from datetime import datetime, timedelta

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Simple IP-based rate limiting (100 requests per minute per IP)
    client_ip = request.client.host
    now = datetime.now()
    
    # Clean up old entries
    old_keys = [key for key, time in request_counts.items() if now - time > timedelta(minutes=1)]
    for key in old_keys:
        del request_counts[key]
    
    # Count requests
    if client_ip in request_counts:
        if request_counts[client_ip] >= 100:  # 100 requests per minute limit
            return HTTPException(status_code=429, detail="Rate limit exceeded")
        request_counts[client_ip] += 1
    else:
        request_counts[client_ip] = 1
    
    response = await call_next(request)
    return response

# Models
class ContainerConfig(BaseModel):
    name: str
    distro: str
    architecture: str
    root_password: str
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    storage_limit: Optional[str] = None
    enable_ssh: Optional[bool] = True
    enable_docker: Optional[bool] = False

class User(BaseModel):
    username: str
    password: str

class SSHConfig(BaseModel):
    container_id: str
    port: int = 22

class TokenData(BaseModel):
    username: Optional[str] = None

class Container(BaseModel):
    id: Optional[int] = None
    name: str
    distro: str
    architecture: str
    state: str
    created_at: str
    updated_at: str
    ip_address: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    storage_limit: Optional[str] = None
    config: Optional[dict] = None

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, hashed_password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        stored_username, stored_hashed_password = row
        if verify_password(password, stored_hashed_password):
            return {"username": stored_username}
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user is None:
        raise credentials_exception
    return {"username": user[0]}

# Systemd-nspawn management functions
def run_machinectl_command(args):
    """Run a machinectl command and return the result"""
    try:
        cmd = ["machinectl"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"machinectl command failed: {e.stderr}")

def get_container_state(container_name: str):
    """Get the current state of a container"""
    try:
        # List machines and find our container
        output = run_machinectl_command(["list", "--no-legend"])
        for line in output.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == container_name:
                return parts[1]  # state
        return "unknown"
    except:
        return "unknown"

def create_container_db_entry(config: ContainerConfig):
    """Create a container entry in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO containers (
            name, distro, architecture, created_at, updated_at, state, config
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        config.name,
        config.distro,
        config.architecture,
        created_at,
        created_at,
        "creating",
        json.dumps(config.dict())
    ))
    
    container_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return container_id

def update_container_state(container_name: str, state: str):
    """Update container state in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updated_at = datetime.now().isoformat()
    cursor.execute("""
        UPDATE containers
        SET state = ?, updated_at = ?
        WHERE name = ?
    """, (state, updated_at, container_name))
    
    conn.commit()
    conn.close()

def get_container_by_name(container_name: str) -> Optional[Container]:
    """Get a container from the database by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, distro, architecture, state, created_at, updated_at,
               ip_address, cpu_limit, memory_limit, storage_limit, config
        FROM containers WHERE name = ?
    """, (container_name,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return Container(
            id=row[0],
            name=row[1],
            distro=row[2],
            architecture=row[3],
            state=row[4],
            created_at=row[5],
            updated_at=row[6],
            ip_address=row[7],
            cpu_limit=row[8],
            memory_limit=row[9],
            storage_limit=row[10],
            config=json.loads(row[11]) if row[11] else None
        )
    return None

# API endpoints
@app.get("/")
def read_root():
    return {"message": "nspawn-vps API", "version": "1.0.0"}

@app.post("/api/login")
async def login(user: User):
    authenticated_user = authenticate_user(user.username, user.password)
    if not authenticated_user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(
        data={"sub": user.username}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/containers")
async def list_containers(current_user: dict = Depends(get_current_user_with_role("user"))):
    """List all containers with status and metadata"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, distro, architecture, state, created_at, 
               ip_address FROM containers
        ORDER BY created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    containers = []
    for row in rows:
        # Get current state via machinectl
        current_state = get_container_state(row[1])  # row[1] is name
        if current_state != row[4]:  # row[4] is stored state
            # Update database with current state
            update_container_state(row[1], current_state)
        
        containers.append({
            "id": row[0],
            "name": row[1],
            "distro": row[2],
            "architecture": row[3],
            "state": current_state,
            "created_at": row[5],
            "ip_address": row[6] if row[6] else "N/A"
        })
    
    return containers

@app.post("/api/containers/create")
async def create_container(config: ContainerConfig, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Create a new container with specified configuration"""
    try:
        # Validate container name
        if not config.name.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise HTTPException(status_code=400, detail="Invalid container name. Only alphanumeric characters, hyphens, underscores, and dots are allowed.")
        
        # Check if container already exists
        existing_container = get_container_by_name(config.name)
        if existing_container:
            raise HTTPException(status_code=400, detail=f"Container {config.name} already exists")
        
        # Create database entry first
        container_id = create_container_db_entry(config)
        
        # Determine debootstrap architecture mapping
        arch_map = {
            "x86_64": "amd64",
            "arm64": "arm64"
        }
        debootstrap_arch = arch_map.get(config.architecture, "amd64")
        
        # Select appropriate mirror based on distribution
        mirrors = {
            "debian": "http://deb.debian.org/debian",
            "ubuntu": "http://archive.ubuntu.com/ubuntu",
            "kali": "http://http.kali.org/kali"
        }
        
        mirror = mirrors.get(config.distro, mirrors["debian"])
        
        # Run debootstrap to create the base system
        debootstrap_cmd = [
            "debootstrap",
            "--arch", debootstrap_arch,
            "--variant=minbase",
            config.distro, 
            f"/var/lib/machines/{config.name}",
            mirror
        ]
        
        # Execute debootstrap
        subprocess.run(debootstrap_cmd, check=True)
        
        # Set root password inside the container
        subprocess.run([
            "chroot", f"/var/lib/machines/{config.name}",
            "/bin/bash", "-c", f"echo 'root:{config.root_password}' | chpasswd"
        ], check=True)
        
        # Install essential packages based on distribution
        if config.distro in ["debian", "ubuntu"]:
            install_cmd = [
                "chroot", f"/var/lib/machines/{config.name}",
                "/bin/bash", "-c", 
                "apt-get update && apt-get install -y systemd systemd-sysv openssh-server sudo"
            ]
        else:
            # For other distros, adjust accordingly
            install_cmd = [
                "chroot", f"/var/lib/machines/{config.name}",
                "/bin/bash", "-c", 
                "apt-get update && apt-get install -y systemd systemd-sysv openssh-server sudo"
            ]  # Default to Debian/Ubuntu packages
        
        subprocess.run(install_cmd, check=True)
        
        # Configure SSH if requested
        if config.enable_ssh:
            # Enable SSH service
            subprocess.run([
                "chroot", f"/var/lib/machines/{config.name}",
                "systemctl", "enable", "ssh"
            ], check=True)
            
            # Configure SSH to allow root login
            subprocess.run([
                "chroot", f"/var/lib/machines/{config.name}",
                "/bin/bash", "-c", 
                "echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && "
                "echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config"
            ], check=True)
        
        # Configure container resource limits if specified
        if config.cpu_limit or config.memory_limit or config.storage_limit:
            # Create systemd slice for resource limits
            slice_path = f"/etc/systemd/system/machine-{config.name}.slice"
            with open(slice_path, 'w') as f:
                f.write(f"""[Slice]
Description=Resource limits for container {config.name}
""")
                
            if config.cpu_limit:
                f.write(f"CPUQuota={config.cpu_limit}\n")
            if config.memory_limit:
                f.write(f"MemoryMax={config.memory_limit}\n")
            
            # Reload systemd
            subprocess.run(["systemctl", "daemon-reload"], check=True)
        
        # Update database with created state
        update_container_state(config.name, "stopped")
        
        return {
            "message": f"Container {config.name} created successfully", 
            "id": container_id,
            "name": config.name
        }
    except subprocess.CalledProcessError as e:
        # Update database with error state
        update_container_state(config.name, "error")
        raise HTTPException(status_code=500, detail=f"Error creating container: {str(e)}")
    except Exception as e:
        # Update database with error state
        update_container_state(config.name, "error")
        raise HTTPException(status_code=500, detail=f"Error creating container: {str(e)}")

@app.post("/api/containers/{container_id}/start")
async def start_container(container_id: str, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Start a stopped container"""
    try:
        # Verify container exists in database
        container = get_container_by_name(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Start the container using machinectl
        run_machinectl_command(["start", container_id])
        
        # Update database state
        update_container_state(container_id, "running")
        
        return {"message": f"Container {container_id} started successfully"}
    except subprocess.CalledProcessError as e:
        # Update database with error state
        update_container_state(container_id, "error")
        raise HTTPException(status_code=500, detail=f"Error starting container: {str(e)}")

@app.post("/api/containers/{container_id}/stop")
async def stop_container(container_id: str, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Stop a running container"""
    try:
        # Verify container exists in database
        container = get_container_by_name(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Stop the container using machinectl
        run_machinectl_command(["stop", container_id])
        
        # Update database state
        update_container_state(container_id, "stopped")
        
        return {"message": f"Container {container_id} stopped successfully"}
    except subprocess.CalledProcessError as e:
        # Update database with error state
        update_container_state(container_id, "error")
        raise HTTPException(status_code=500, detail=f"Error stopping container: {str(e)}")

@app.post("/api/containers/{container_id}/restart")
async def restart_container(container_id: str, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Restart a container"""
    try:
        # Verify container exists in database
        container = get_container_by_name(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Restart the container using machinectl
        run_machinectl_command(["reboot", container_id])
        
        return {"message": f"Container {container_id} restarted successfully"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error restarting container: {str(e)}")

@app.delete("/api/containers/{container_id}")
async def delete_container(container_id: str, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Remove container and optionally its data"""
    try:
        # Verify container exists in database
        container = get_container_by_name(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Stop container if running
        current_state = get_container_state(container_id)
        if current_state == "running":
            try:
                run_machinectl_command(["stop", container_id])
            except:
                pass  # Continue even if stop fails
        
        # Remove container using machinectl
        run_machinectl_command(["remove", container_id])
        
        # Remove from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM containers WHERE name = ?", (container_id,))
        conn.commit()
        conn.close()
        
        return {"message": f"Container {container_id} removed successfully"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error removing container: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing container: {str(e)}")

@app.post("/api/containers/{container_id}/setup-ssh")
async def setup_ssh(container_id: str, ssh_config: SSHConfig, current_user: dict = Depends(get_current_user_with_role("admin"))):
    """Install and configure SSH server inside container"""
    try:
        # Verify container exists
        container = get_container_by_name(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Install SSH server if not already installed
        install_cmd = f"if ! command -v sshd >/dev/null 2>&1; then apt-get update && apt-get install -y openssh-server; fi"
        subprocess.run([
            "chroot", f"/var/lib/machines/{container_id}",
            "/bin/bash", "-c", install_cmd
        ], check=True)
        
        # Configure SSH to allow root login and password authentication
        subprocess.run([
            "chroot", f"/var/lib/machines/{container_id}",
            "/bin/bash", "-c", 
            "echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && "
            "echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config"
        ], check=True)
        
        # Enable and start SSH service
        subprocess.run([
            "chroot", f"/var/lib/machines/{container_id}",
            "systemctl", "enable", "ssh"
        ], check=True)
        
        subprocess.run([
            "chroot", f"/var/lib/machines/{container_id}",
            "systemctl", "start", "ssh"
        ], check=True)
        
        return {
            "message": f"SSH configured in container {container_id}",
            "container_id": container_id,
            "port": ssh_config.port
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error configuring SSH: {str(e)}")

@app.get("/api/network/bridge-status")
async def get_bridge_status(current_user: dict = Depends(get_current_user_with_role("user"))):
    """Check network bridge health and configuration"""
    try:
        # Check if bridge exists
        result = subprocess.run(["ip", "addr", "show", "br0"], capture_output=True, text=True)
        if result.returncode == 0:
            interfaces = result.stdout
            status = "up"
        else:
            interfaces = ""
            status = "down"
        
        # Check IPv4 and IPv6 NAT status
        ipv4_nat_result = subprocess.run(["iptables", "-t", "nat", "-L", "-n"], capture_output=True, text=True)
        ipv6_nat_result = subprocess.run(["ip6tables", "-t", "nat", "-L", "-n"], capture_output=True, text=True)
        
        return {
            "bridge_name": "br0",
            "status": status,
            "interfaces": interfaces,
            "ipv4_nat_rules": ipv4_nat_result.stdout if ipv4_nat_result.returncode == 0 else "Error",
            "ipv6_nat_rules": ipv6_nat_result.stdout if ipv6_nat_result.returncode == 0 else "Not available"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting bridge status: {str(e)}")

@app.get("/api/network/ipv4-nat-rules")
async def get_ipv4_nat_rules(current_user: dict = Depends(get_current_user)):
    """Get current IPv4 NAT forwarding rules"""
    try:
        result = subprocess.run(["iptables", "-t", "nat", "-L", "-n", "-v"], capture_output=True, text=True, check=True)
        return {"rules": result.stdout}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error getting IPv4 NAT rules: {str(e)}")

@app.get("/api/network/ipv6-status")
async def get_ipv6_status(current_user: dict = Depends(get_current_user)):
    """Check IPv6 connectivity and configuration"""
    try:
        # Check if IPv6 is enabled
        with open('/proc/sys/net/ipv6/conf/all/forwarding', 'r') as f:
            ipv6_forwarding = f.read().strip()
        
        # Check for IPv6 addresses on interfaces
        result = subprocess.run(["ip", "-6", "addr", "show"], capture_output=True, text=True, check=True)
        
        # Check for available tunnels
        tunnels = []
        if os.path.exists('/sys/class/net/sit0'):
            tunnels.append("sit0 (6in4)")
        if os.path.exists('/sys/class/net/wg0'):
            tunnels.append("wg0 (WireGuard)")
        
        return {
            "ipv6_forwarding": ipv6_forwarding == "1",
            "addresses": result.stdout,
            "tunnels": tunnels,
            "has_ipv6_connectivity": check_ipv6_connectivity()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting IPv6 status: {str(e)}")

def check_ipv6_connectivity():
    """Check if IPv6 connectivity is available"""
    try:
        result = subprocess.run(["ping6", "-c", "1", "-W", "3", "2001:4860:4860::8888"], 
                              capture_output=True, text=False)
        return result.returncode == 0
    except:
        return False

@app.post("/api/network/port-forward")
async def create_port_forward(rule: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """Create port forwarding rule for container"""
    try:
        container_ip = rule.get("container_ip")
        container_port = rule.get("container_port")
        host_port = rule.get("host_port")
        
        if not container_ip or not container_port or not host_port:
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # Create DNAT rule for port forwarding
        cmd = [
            "iptables", "-t", "nat", "-A", "PREROUTING", 
            "-p", "tcp", "--dport", str(host_port), 
            "-j", "DNAT", "--to-destination", f"{container_ip}:{container_port}"
        ]
        subprocess.run(cmd, check=True)
        
        # Allow forwarded traffic in filter table
        allow_cmd = [
            "iptables", "-A", "FORWARD", 
            "-p", "tcp", "-d", container_ip, "--dport", str(container_port),
            "-j", "ACCEPT"
        ]
        subprocess.run(allow_cmd, check=True)
        
        return {
            "message": f"Port forwarding from host port {host_port} to {container_ip}:{container_port} created successfully",
            "rule": f"{host_port} -> {container_ip}:{container_port}"
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error creating port forward: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating port forward: {str(e)}")

@app.get("/api/network/assigned-ips")
async def get_assigned_ips(current_user: dict = Depends(get_current_user)):
    """Get IP addresses assigned to containers"""
    try:
        # Get container IP addresses using machinectl
        containers = await get_current_user  # This is just to satisfy auth
        # Actually fetch containers to get their network info
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, ip_address FROM containers")
        rows = cursor.fetchall()
        conn.close()
        
        container_ips = []
        for row in rows:
            container_name, ip_address = row
            # Try to get current IP if not stored in DB
            if not ip_address or ip_address == "N/A":
                try:
                    result = subprocess.run(["machinectl", "status", container_name], 
                                          capture_output=True, text=True)
                    # Parse the output to find IP addresses (simplified)
                    for line in result.stdout.split('\n'):
                        if 'Address:' in line:
                            # Extract IP from line like "Address: 10.0.0.100"
                            ip_address = line.split('Address:')[1].strip().split()[0]
                            break
                except:
                    ip_address = "N/A"
            
            container_ips.append({
                "container_name": container_name,
                "ip_address": ip_address
            })
        
        return {"container_ips": container_ips}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting assigned IPs: {str(e)}")

@app.get("/api/system/info")
async def get_system_info(current_user: dict = Depends(get_current_user_with_role("user"))):
    """Get system information"""
    try:
        # Get system info
        hostname_result = subprocess.run(["hostname"], capture_output=True, text=True, check=True)
        kernel_result = subprocess.run(["uname", "-r"], capture_output=True, text=True, check=True)
        
        # Get system load
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[0]  # 1-minute load average
        
        # Get memory info
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        
        # Get disk info for containers directory
        stat_result = os.statvfs('/var/lib/machines') if os.path.exists('/var/lib/machines') else os.statvfs('/')
        available_space = stat_result.f_frsize * stat_result.f_bavail  # Available space in bytes
        
        # Get architecture
        arch_result = subprocess.run(["uname", "-m"], capture_output=True, text=True, check=True)
        
        # Get available distributions (simplified)
        available_distros = [
            {"name": "Debian", "versions": ["stable", "testing"]},
            {"name": "Ubuntu", "versions": ["20.04", "22.04"]},
            {"name": "Kali", "versions": ["latest"]}
        ]
        
        return {
            "hostname": hostname_result.stdout.strip(),
            "kernel": kernel_result.stdout.strip(),
            "architecture": arch_result.stdout.strip(),
            "load_average": load,
            "available_disk_space_gb": round(available_space / (1024**3), 2),
            "available_distros": available_distros,
            "version": "1.0.0"
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error getting system info: {str(e)}")

@app.get("/api/distros/available")
async def get_available_distros(current_user: dict = Depends(get_current_user)):
    """Get list of supported distributions and architectures"""
    return {
        "distros": [
            {
                "name": "debian",
                "versions": ["stable", "testing", "unstable"],
                "architectures": ["x86_64", "arm64"],
                "description": "Debian GNU/Linux"
            },
            {
                "name": "ubuntu",
                "versions": ["20.04", "22.04", "24.04"],
                "architectures": ["x86_64", "arm64"],
                "description": "Ubuntu Linux"
            },
            {
                "name": "alpine",
                "versions": ["latest"],
                "architectures": ["x86_64", "arm64"],
                "description": "Alpine Linux"
            }
        ]
    }

# WebSocket for real-time logs
@app.websocket("/ws/containers/{container_id}/logs")
async def websocket_container_logs(websocket: WebSocket, container_id: str):
    await websocket.accept()
    try:
        # Verify container exists
        result = subprocess.run(["machinectl", "list", "--no-legend"], capture_output=True, text=True)
        container_exists = False
        for line in result.stdout.strip().split('\n'):
            if line.strip() and container_id in line.split():
                container_exists = True
                break
        
        if not container_exists:
            await websocket.send_text(f"Error: Container {container_id} does not exist")
            await websocket.close()
            return
        
        # For real-time logs, we'll use journalctl to follow the container logs
        process = await asyncio.create_subprocess_exec(
            "journalctl", "-M", container_id, "-f", "-n", "0", "--no-tail",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Read logs asynchronously
        async def read_logs():
            while True:
                line = await process.stdout.readline()
                if line:
                    await websocket.send_text(line.decode('utf-8').strip())
                else:
                    break
        
        # Run log reading in background
        log_task = asyncio.create_task(read_logs())
        
        # Keep connection alive
        try:
            while True:
                # Wait for messages from client (we may receive commands later)
                data = await websocket.receive_text()
                # Process any client commands if needed
        except WebSocketDisconnect:
            log_task.cancel()  # Cancel the log reading task when client disconnects
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    process.kill()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except:
            pass

# Additional monitoring endpoints
@app.get("/api/containers/{container_id}/metrics")
async def get_container_metrics(container_id: str, current_user: dict = Depends(get_current_user_with_role("user"))):
    """Retrieve resource usage statistics for a container"""
    try:
        # Check if container exists
        state = get_container_state(container_id)
        if state == "unknown":
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Get memory usage using machinectl show
        result = subprocess.run(["machinectl", "show", container_id], capture_output=True, text=True, check=True)
        
        metrics = {}
        for line in result.stdout.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Extract relevant metrics
                if key in ['MemoryCurrent', 'CPUUsageNSec', 'TasksCurrent', 'IPInBytes', 'IPOutBytes']:
                    metrics[key.lower()] = value
        
        # Convert CPU usage nanoseconds to seconds
        if 'cpuusagensec' in metrics:
            cpu_ns = int(metrics['cpuusagensec']) if metrics['cpuusagensec'].isdigit() else 0
            metrics['cpu_usage_seconds'] = round(cpu_ns / 1_000_000_000, 2)
        
        # Get disk usage for container's root directory
        container_path = f"/var/lib/machines/{container_id}"
        if os.path.exists(container_path):
            try:
                disk_result = subprocess.run(["du", "-sh", container_path], capture_output=True, text=True)
                if disk_result.returncode == 0:
                    disk_usage = disk_result.stdout.split()[0] if disk_result.stdout.strip() else "N/A"
                    metrics['disk_usage'] = disk_usage
            except:
                metrics['disk_usage'] = "N/A"
        
        return {
            "container_id": container_id,
            "state": state,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")

@app.get("/api/system/resources")
async def get_system_resources(current_user: dict = Depends(get_current_user_with_role("user"))):
    """Get system resource usage"""
    try:
        # Get memory information
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        
        # Get disk usage for containers directory
        result = subprocess.run(["df", "-h", "/var/lib/machines"], capture_output=True, text=True)
        disk_usage = result.stdout
        
        # Get CPU information
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        
        # Get load average
        with open('/proc/loadavg', 'r') as f:
            loadavg = f.read().strip()
        
        # Get number of running containers
        containers_result = subprocess.run(["machinectl", "list", "--no-legend"], capture_output=True, text=True)
        running_containers = 0
        for line in containers_result.stdout.strip().split('\n'):
            if line.strip() and 'running' in line:
                running_containers += 1
        
        return {
            "memory": meminfo,
            "disk_usage": disk_usage,
            "cpu_info": cpuinfo[:500],  # First 500 chars
            "load_average": loadavg,
            "running_containers": running_containers,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system resources: {str(e)}")

@app.get("/api/monitoring/overview")
async def get_monitoring_overview(current_user: dict = Depends(get_current_user_with_role("user"))):
    """Get an overview of system and container monitoring"""
    try:
        # Get all containers
        containers_result = subprocess.run(["machinectl", "list", "--no-legend"], capture_output=True, text=True)
        
        containers = []
        for line in containers_result.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    name, state = parts[0], parts[1]
                    containers.append({
                        "name": name,
                        "state": state
                    })
        
        # Get system resources
        with open('/proc/loadavg', 'r') as f:
            loadavg = f.read().strip().split()
        
        # Get memory usage
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        
        mem_total = mem_free = 0
        for line in meminfo:
            if line.startswith('MemTotal:'):
                mem_total = int(line.split()[1])  # in KB
            elif line.startswith('MemAvailable:'):
                mem_free = int(line.split()[1])  # in KB
        
        mem_used = mem_total - mem_free
        mem_usage_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
        
        # Get disk usage for containers directory
        disk_result = subprocess.run(["df", "/var/lib/machines"], capture_output=True, text=True)
        disk_lines = disk_result.stdout.strip().split('\n')
        if len(disk_lines) > 1:
            disk_parts = disk_lines[1].split()
            disk_used = int(disk_parts[2])  # in 1K blocks
            disk_total = int(disk_parts[1])  # in 1K blocks
            disk_usage_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
        else:
            disk_usage_percent = 0
        
        return {
            "overview": {
                "total_containers": len(containers),
                "running_containers": len([c for c in containers if c["state"] == "running"]),
                "stopped_containers": len([c for c in containers if c["state"] == "stopped"]),
            },
            "system": {
                "load_average": {
                    "1min": loadavg[0],
                    "5min": loadavg[1],
                    "15min": loadavg[2]
                },
                "memory_usage_percent": round(mem_usage_percent, 2),
                "disk_usage_percent": round(disk_usage_percent, 2),
                "timestamp": datetime.now().isoformat()
            },
            "containers": containers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting monitoring overview: {str(e)}")

# Serve frontend static files
frontend_path = "/opt/nspawn-manager/frontend"
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

# Additional API endpoints for enhanced functionality
@app.get("/api/containers/{container_id}/logs")
async def get_container_logs(container_id: str, current_user: dict = Depends(get_current_user)):
    """Get recent logs for a container"""
    try:
        # Using journalctl to get container logs (machines logs)
        result = subprocess.run([
            "journalctl", "-M", container_id, "-n", "100", "--no-pager"
        ], capture_output=True, text=True, check=True)
        
        logs = result.stdout.strip().split('\n')
        return {"container_id": container_id, "logs": logs}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error getting logs: {str(e)}")

@app.get("/api/containers/{container_id}/status")
async def get_container_status(container_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed status information for a container"""
    try:
        # Get detailed container info using machinectl show
        result = subprocess.run(["machinectl", "show", container_id], capture_output=True, text=True, check=True)
        
        # Parse the properties
        properties = {}
        for line in result.stdout.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                properties[key] = value
        
        # Get network information
        network_info = properties.get('NetworkInterfaces', 'N/A')
        
        # Get IP addresses using machinectl status
        status_result = subprocess.run(["machinectl", "status", container_id], capture_output=True, text=True)
        
        return {
            "container_id": container_id,
            "status": properties,
            "network_info": network_info,
            "raw_status": status_result.stdout
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error getting container status: {str(e)}")

@app.get("/api/system/resources")
async def get_system_resources(current_user: dict = Depends(get_current_user)):
    """Get system resource usage"""
    try:
        # Get memory information
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        
        # Get disk usage for containers directory
        result = subprocess.run(["df", "-h", "/var/lib/machines"], capture_output=True, text=True)
        disk_usage = result.stdout
        
        # Get CPU information
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        
        # Get load average
        with open('/proc/loadavg', 'r') as f:
            loadavg = f.read().strip()
        
        return {
            "memory": meminfo,
            "disk_usage": disk_usage,
            "cpu_info": cpuinfo[:500],  # First 500 chars
            "load_average": loadavg,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system resources: {str(e)}")

@app.get("/api/distros/refresh")
async def refresh_distributions(current_user: dict = Depends(get_current_user)):
    """Refresh available distribution templates"""
    try:
        # In a real implementation, this would update the cached list of available distributions
        # For now, return the same list we have
        available_distros = [
            {"name": "Debian", "versions": ["stable", "testing"]},
            {"name": "Ubuntu", "versions": ["20.04", "22.04"]},
            {"name": "Kali", "versions": ["latest"]}
        ]
        
        return {"message": "Distribution list refreshed", "distros": available_distros}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing distributions: {str(e)}")

@app.post("/api/containers/{container_id}/exec")
async def execute_command_in_container(container_id: str, command: str, current_user: dict = Depends(get_current_user)):
    """Execute a command inside a container"""
    try:
        # Validate container exists and is running
        state = get_container_state(container_id)
        if state != "running":
            raise HTTPException(status_code=400, detail=f"Container {container_id} is not running")
        
        # Execute command in container
        result = subprocess.run([
            "machinectl", "exec", container_id, "/bin/bash", "-c", command
        ], capture_output=True, text=True, check=True)
        
        return {
            "container_id": container_id,
            "command": command,
            "output": result.stdout,
            "error": result.stderr if result.stderr else None
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {str(e)}")

# Mount frontend if it exists
import os
frontend_path = "/opt/nspawn-manager/frontend"
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)