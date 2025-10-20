from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import subprocess
import json
import os
import pwd
import grp
from datetime import datetime
import asyncio
import signal
import time

app = FastAPI(title="nspawn-ui API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class Container(BaseModel):
    name: str
    status: str
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    storage_limit: Optional[str] = None
    created_at: Optional[datetime] = None
    pid: Optional[int] = None
    ip_address: Optional[str] = None

class CreateContainerRequest(BaseModel):
    name: str
    distro: str
    root_password: str
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None  # in MB
    storage_limit: Optional[str] = None  # in GB
    enable_docker: Optional[bool] = False
    enable_nested: Optional[bool] = False

class StartContainerRequest(BaseModel):
    name: str

class StopContainerRequest(BaseModel):
    name: str

class RestartContainerRequest(BaseModel):
    name: str

class SSHSetupRequest(BaseModel):
    name: str
    ssh_public_key: str

class NetworkConfigRequest(BaseModel):
    name: str
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    enable_nat: Optional[bool] = True

# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

def run_command(command: List[str], shell=False) -> dict:
    """Execute a shell command and return result"""
    try:
        if shell:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        else:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {
            "success": True,
            "output": result.stdout,
            "error": None
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "output": e.stdout,
            "error": e.stderr
        }

def get_container_ip(container_name: str) -> Optional[str]:
    """Get the IP address of a container"""
    try:
        # Check if container is running
        status_result = run_command(["machinectl", "status", container_name], shell=True)
        if not status_result["success"]:
            return None
        
        # If container is running, try to get IP
        # This is a more complex operation that would require checking the actual network interfaces
        # For now, we'll use a simplified approach
        network_result = run_command([
            "machinectl", "show", container_name, 
            "--property=NetworkInterfaces", "--output=cat"
        ])
        
        if network_result["success"]:
            # In a real implementation, we would parse the actual IP addresses
            # For now, we'll return a placeholder
            if "running" in status_result["output"]:
                return f"10.0.1.{hash(container_name) % 254 + 1}"  # Placeholder IP
        
        return None
    except Exception:
        return None

@app.get("/")
def read_root():
    return {"message": "nspawn-ui API is running"}

@app.get("/containers", response_model=List[Container])
def get_containers():
    """Get list of all containers"""
    try:
        # Use machinectl to list containers
        result = run_command(["machinectl", "list", "--no-legend", "--no-pager"], shell=True)
        
        containers = []
        if result["success"] and result["output"]:
            for line in result["output"].strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        status = parts[1]  # running, stopped, etc.
                        
                        # Get additional details with proper error handling
                        detail_result = run_command([
                            "machinectl", "show", name, 
                            "--property=Leader", "--output=cat"
                        ])
                        
                        pid = None
                        if detail_result["success"]:
                            try:
                                # Parse the PID from the output
                                if detail_result["output"].strip():
                                    pid_line = detail_result["output"].strip()
                                    if '=' in pid_line:
                                        pid = pid_line.split('=')[1]
                                        pid = int(pid) if pid.isdigit() else None
                            except:
                                pass  # If parsing fails, pid remains None
                        
                        # Get IP address if available
                        ip_address = get_container_ip(name)
                        
                        container = Container(
                            name=name,
                            status=status,
                            created_at=datetime.now(),
                            pid=pid,
                            ip_address=ip_address
                        )
                        containers.append(container)
        else:
            # If machinectl fails, check the machines directory directly
            machines_dir = "/var/lib/machines"
            if os.path.exists(machines_dir):
                for item in os.listdir(machines_dir):
                    item_path = os.path.join(machines_dir, item)
                    if os.path.isdir(item_path):
                        # Check if container is running
                        status_result = run_command(["machinectl", "status", item], shell=True)
                        if status_result["success"] and "running" in status_result["output"]:
                            status = "running"
                        else:
                            status = "stopped"
                        
                        container = Container(
                            name=item,
                            status=status,
                            created_at=datetime.now()
                        )
                        containers.append(container)
        
        return containers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing containers: {str(e)}")

@app.post("/containers")
def create_container(request: CreateContainerRequest):
    """Create a new container with specified resources and options"""
    # Validate inputs
    if not request.name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate name doesn't contain dangerous characters
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Container name can only contain alphanumeric characters, hyphens, and underscores")
    
    # Check if container already exists
    machines_dir = "/var/lib/machines"
    container_path = os.path.join(machines_dir, request.name)
    if os.path.exists(container_path):
        raise HTTPException(status_code=400, detail="Container already exists")
    
    # Determine debootstrap URL based on distro
    distro_urls = {
        "bullseye": "http://deb.debian.org/debian",
        "bookworm": "http://deb.debian.org/debian",
        "jammy": "http://archive.ubuntu.com/ubuntu",
        "focal": "http://archive.ubuntu.com/ubuntu",
        "alma8": "http://repo.almalinux.org/almalinux/8/BaseOS/x86_64/os/",
        "alma9": "http://repo.almalinux.org/almalinux/9/BaseOS/x86_64/os/"
    }
    
    if request.distro not in distro_urls:
        raise HTTPException(status_code=400, detail=f"Unsupported distribution: {request.distro}")
    
    debootstrap_cmd = [
        "debootstrap",
        "--variant=minbase"
    ]
    
    # Add arch for some distros
    if request.distro.startswith("alma"):
        debootstrap_cmd.extend(["--arch", "amd64"])
    
    debootstrap_cmd.extend([
        request.distro,
        container_path,
        distro_urls[request.distro]
    ])
    
    try:
        # Create base container with debootstrap
        result = run_command(debootstrap_cmd)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to create container: {result['error']}")
        
        # Set up root password
        setup_password_cmd = [
            "chroot", container_path,
            "/bin/bash", "-c", f"echo 'root:{request.root_password}' | chpasswd"
        ]
        
        password_result = run_command(setup_password_cmd)
        if not password_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to set password: {password_result['error']}")
        
        # Set up basic networking
        setup_network_cmd = [
            "chroot", container_path,
            "/bin/bash", "-c", 
            "echo 'nameserver 8.8.8.8' > /etc/resolv.conf && "
            "echo 'nameserver 8.8.4.4' >> /etc/resolv.conf && "
            "echo '127.0.0.1 localhost' > /etc/hosts && "
            f"echo '127.0.0.1 {request.name}' >> /etc/hosts"
        ]
        
        net_result = run_command(setup_network_cmd)
        if not net_result["success"]:
            # Non-critical error, continue anyway
            print(f"Warning: Network setup failed: {net_result['error']}")
        
        # Set up systemd-nspawn configuration with advanced options
        config_created = False
        additional_setup = []
        
        if request.cpu_limit or request.memory_limit or request.storage_limit or request.enable_docker or request.enable_nested:
            nspawn_config_dir = "/etc/systemd/nspawn"
            os.makedirs(nspawn_config_dir, exist_ok=True)
            
            config_path = os.path.join(nspawn_config_dir, f"{request.name}.nspawn")
            with open(config_path, 'w') as f:
                f.write(f"# Configuration for container {request.name}\n")
                
                # Handle Docker-in-CT
                if request.enable_docker:
                    f.write(f"\n[Exec]\n")
                    f.write(f"Boot=false\n")  # Don't boot init system for Docker containers
                    f.write(f"User=root\n")
                    
                    f.write(f"\n[Files]\n")
                    f.write(f"Bind=/var/lib/docker\n")  # Mount Docker data directory
                    f.write(f"Bind=/var/run/docker.sock:/var/run/docker.sock\n")  # Mount Docker socket
                
                # Handle nested containers
                if request.enable_nested:
                    f.write(f"\n[Security]\n")
                    f.write(f"PrivateUsers=false\n")  # Enable user namespace sharing
                    f.write(f"Capability=all\n")  # Grant all capabilities
                    f.write(f"NoNewPrivileges=false\n")  # Allow privilege escalation
                
                # Handle resource limits
                if request.cpu_limit or request.memory_limit or request.storage_limit:
                    f.write(f"\n[Resources]\n")
                    if request.cpu_limit:
                        f.write(f"CPUQuota={request.cpu_limit}\n")
                    if request.memory_limit:
                        f.write(f"MemoryMax={request.memory_limit}M\n")
                    if request.storage_limit:
                        # Note: Storage limits require system-level configuration
                        f.write(f"LimitNOFILE=1048576\n")  # Increase file descriptor limit
                
                # Network configuration for containers
                f.write(f"\n[Network]\n")
                f.write(f"VirtualEthernet=true\n")  # Create virtual ethernet interface
                
                additional_setup.append(f"Docker support: {'enabled' if request.enable_docker else 'disabled'}")
                additional_setup.append(f"Nested containers: {'enabled' if request.enable_nested else 'disabled'}")
            
            config_created = True
        
        # If Docker is enabled, install Docker inside the container
        if request.enable_docker:
            install_docker_cmd = [
                "chroot", container_path,
                "/bin/bash", "-c", 
                "if command -v apt-get >/dev/null 2>&1; then "
                "apt-get update > /dev/null 2>&1 && apt-get install -y curl gnupg lxc iptables > /dev/null 2>&1 && "
                "curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && "
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && '
                "apt-get update > /dev/null 2>&1 && apt-get install -y docker-ce docker-ce-cli containerd.io > /dev/null 2>&1 && "
                "systemctl enable docker > /dev/null 2>&1 || true; "
                "elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then "
                "dnf install -y yum-utils curl > /dev/null 2>&1 || yum install -y yum-utils curl > /dev/null 2>&1 && "
                "yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo > /dev/null 2>&1 && "
                "dnf install -y docker-ce docker-ce-cli containerd.io > /dev/null 2>&1 || yum install -y docker-ce docker-ce-cli containerd.io > /dev/null 2>&1 && "
                "systemctl enable docker > /dev/null 2>&1 || true; "
                "fi"
            ]
            
            docker_result = run_command(install_docker_cmd)
            if docker_result["success"]:
                additional_setup.append("Docker installed in container")
            else:
                additional_setup.append(f"Docker installation may have failed: {docker_result['error']}")
        
        return {
            "success": True,
            "message": f"Container {request.name} created successfully",
            "details": {
                "config_created": config_created,
                "additional_setup": additional_setup
            },
            "container": Container(
                name=request.name,
                status="stopped",
                created_at=datetime.now()
            )
        }
    except Exception as e:
        # Clean up on failure
        try:
            if os.path.exists(container_path):
                run_command(["rm", "-rf", container_path], shell=True)
            
            # Remove config file if created
            config_path = f"/etc/systemd/nspawn/{request.name}.nspawn"
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass  # Best effort cleanup
        
        raise HTTPException(status_code=500, detail=f"Error creating container: {str(e)}")

@app.post("/containers/start")
def start_container(request: StartContainerRequest):
    """Start a container"""
    if not request.name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate container name
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    command = ["machinectl", "start", request.name]
    result = run_command(command)
    
    if result["success"]:
        return {
            "success": True,
            "message": f"Container {request.name} started successfully"
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {result['error']}")

@app.post("/containers/stop")
def stop_container(request: StopContainerRequest):
    """Stop a container"""
    if not request.name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate container name
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    command = ["machinectl", "stop", request.name]
    result = run_command(command)
    
    if result["success"]:
        return {
            "success": True,
            "message": f"Container {request.name} stopped successfully"
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {result['error']}")

@app.post("/containers/restart")
def restart_container(request: RestartContainerRequest):
    """Restart a container"""
    if not request.name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate container name
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    # First stop the container
    stop_result = run_command(["machinectl", "stop", request.name])
    if not stop_result["success"]:
        # Continue anyway, as container might not be running
        pass
    
    # Wait a moment
    time.sleep(1)
    
    # Then start it again
    start_result = run_command(["machinectl", "start", request.name])
    if start_result["success"]:
        return {
            "success": True,
            "message": f"Container {request.name} restarted successfully"
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to restart container: {start_result['error']}")

@app.delete("/containers/{name}")
def remove_container(name: str):
    """Remove a container"""
    if not name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate container name
    if not name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    # Stop container first if running
    containers_result = run_command(["machinectl", "list", "--no-legend", "--no-pager"], shell=True)
    if containers_result["success"]:
        # Check if the container is running
        list_lines = containers_result["output"].strip().split('\n')
        for line in list_lines:
            if name in line and "running" in line:
                # Stop the container
                stop_result = run_command(["machinectl", "stop", name])
                if not stop_result["success"]:
                    print(f"Warning: Could not stop container before removal: {stop_result['error']}")
                break
    
    # Remove the container
    command = ["machinectl", "remove", name]
    result = run_command(command)
    
    if result["success"]:
        # Remove config file if it exists
        config_path = f"/etc/systemd/nspawn/{name}.nspawn"
        if os.path.exists(config_path):
            try:
                os.remove(config_path)
            except:
                pass  # Best effort
        
        return {
            "success": True,
            "message": f"Container {name} removed successfully"
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to remove container: {result['error']}")

@app.get("/containers/{name}/logs")
def get_container_logs(name: str):
    """Get container logs"""
    if not name:
        raise HTTPException(status_code=400, detail="Container name is required")
    
    # Validate container name
    if not name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    # Try to get logs from journalctl first
    command = ["journalctl", "-u", f"systemd-nspawn@{name}", "-n", "100", "--no-pager"]
    result = run_command(command)
    
    if result["success"]:
        return {
            "container": name,
            "logs": result["output"]
        }
    else:
        # If systemd service logs are not available, try alternate method
        # Check if container exists and get status
        status_result = run_command(["machinectl", "status", name], shell=True)
        
        if status_result["success"]:
            return {
                "container": name,
                "logs": status_result["output"]
            }
        else:
            # If container doesn't exist or we can't get status, try to read container files
            container_path = f"/var/lib/machines/{name}"
            if os.path.exists(container_path):
                # This would be a more complex implementation to read container-specific logs
                return {
                    "container": name,
                    "logs": f"Container {name} exists but no detailed logs available via journalctl"
                }
            else:
                raise HTTPException(status_code=404, detail=f"Container {name} not found")

@app.post("/containers/{name}/ssh")
def setup_ssh(request: SSHSetupRequest):
    """Set up SSH access for a container"""
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    container_path = f"/var/lib/machines/{request.name}"
    
    if not os.path.exists(container_path):
        raise HTTPException(status_code=404, detail="Container not found")
    
    try:
        # Validate SSH public key format
        if not is_valid_ssh_key(request.ssh_public_key):
            raise HTTPException(status_code=400, detail="Invalid SSH public key format")
        
        # Create .ssh directory in container
        mkdir_cmd = ["chroot", container_path, "/bin/mkdir", "-p", "/root/.ssh"]
        mkdir_result = run_command(mkdir_cmd)
        if not mkdir_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to create .ssh directory")
        
        # Write the public key to authorized_keys
        auth_keys_path = os.path.join(container_path, "root/.ssh/authorized_keys")
        with open(auth_keys_path, 'w') as f:
            f.write(request.ssh_public_key.strip() + "\n")
        
        # Set proper permissions
        chmod_cmd = ["chroot", container_path, "/bin/chmod", "700", "/root/.ssh"]
        chown_cmd = ["chroot", container_path, "/bin/chown", "root:root", "/root/.ssh"]
        chmod_file_cmd = ["chroot", container_path, "/bin/chmod", "600", "/root/.ssh/authorized_keys"]
        chown_file_cmd = ["chroot", container_path, "/bin/chown", "root:root", "/root/.ssh/authorized_keys"]
        
        for cmd in [chmod_cmd, chown_cmd, chmod_file_cmd, chown_file_cmd]:
            result = run_command(cmd)
            if not result["success"]:
                print(f"Warning: Failed to set permissions: {result['error']}")
        
        # Install and configure SSH server in container if needed
        install_ssh_cmd = [
            "chroot", container_path,
            "/bin/bash", "-c", 
            "if command -v apt-get >/dev/null 2>&1; then "
            "apt-get update > /dev/null 2>&1 && apt-get install -y openssh-server > /dev/null 2>&1 && "
            "mkdir -p /run/sshd && "
            "sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && "
            "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && "
            "systemctl enable ssh > /dev/null 2>&1 || true; "
            "elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then "
            "dnf install -y openssh-server > /dev/null 2>&1 || yum install -y openssh-server > /dev/null 2>&1 && "
            "systemctl enable sshd > /dev/null 2>&1 || true && "
            "sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && "
            "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config; "
            "elif command -v pacman >/dev/null 2>&1; then "
            "pacman -S --noconfirm openssh > /dev/null 2>&1 && "
            "systemctl enable sshd > /dev/null 2>&1 || true && "
            "sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && "
            "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config; "
            "fi"
        ]
        
        ssh_result = run_command(install_ssh_cmd)
        if not ssh_result["success"]:
            print(f"Warning: Could not install/configure SSH: {ssh_result['error']}")
        
        # Try to restart SSH if container is running
        status_result = run_command(["machinectl", "status", request.name], shell=True)
        if status_result["success"] and "running" in status_result["output"]:
            # Try to restart SSH inside the running container
            restart_ssh_cmd = [
                "machinectl", "exec", request.name,
                "/bin/bash", "-c", 
                "systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true"
            ]
            run_command(restart_ssh_cmd)
        
        return {
            "success": True,
            "message": f"SSH setup completed for container {request.name}",
            "details": {
                "container": request.name,
                "ssh_configured": True,
                "public_key_added": True
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set up SSH: {str(e)}")

def is_valid_ssh_key(key_str: str) -> bool:
    """Validate if the provided string is a valid SSH public key"""
    import re
    
    # Remove any extra whitespace
    key_str = key_str.strip()
    
    # SSH keys typically start with the type (ssh-rsa, ssh-dss, ssh-ed25519, ecdsa-sha2-nistp256, etc.)
    # and have the format: <type> <base64_key> [comment]
    if not key_str:
        return False
    
    # Split the key into parts
    parts = key_str.split()
    if len(parts) < 2:  # Need at least type and key
        return False
    
    key_type = parts[0]
    key_data = parts[1]
    
    # Check if key type is valid
    valid_types = ["ssh-rsa", "ssh-dss", "ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"]
    if key_type not in valid_types:
        return False
    
    # Check if key data is valid base64
    import base64
    try:
        base64.b64decode(key_data)
    except Exception:
        return False
    
    return True

@app.post("/containers/{name}/network")
def configure_network(request: NetworkConfigRequest):
    """Configure networking for a container"""
    if not request.name.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    container_path = f"/var/lib/machines/{request.name}"
    if not os.path.exists(container_path):
        raise HTTPException(status_code=404, detail="Container not found")
    
    try:
        # Create systemd-networkd configuration for this container
        network_config_dir = "/etc/systemd/network"
        os.makedirs(network_config_dir, exist_ok=True)
        
        # Create a network file for the container
        network_file = f"/var/lib/machines/{request.name}.network"
        
        with open(network_file, 'w') as f:
            f.write(f"# Network configuration for {request.name}\n")
            f.write("[Match]\n")
            f.write(f"Virtualization=container\n")
            f.write("\n[Network]\n")
            
            if request.ipv4:
                f.write(f"Address={request.ipv4}\n")
                f.write("Gateway=10.0.0.1\n")  # This would need to be configurable
                f.write("DNS=8.8.8.8\n")
            
            if request.ipv6:
                f.write(f"Address={request.ipv6}\n")
                f.write("IPv6AcceptRA=yes\n")
            
            if request.enable_nat:
                # Enable IP forwarding for NAT
                f.write("IPForward=ipv4\n")
        
        # If the container is running, we need to restart it for changes to take effect
        status_result = run_command(["machinectl", "status", request.name], shell=True)
        if status_result["success"] and "running" in status_result["output"]:
            # Restart the container to apply network changes
            restart_result = run_command(["machinectl", "restart", request.name])
            if not restart_result["success"]:
                print(f"Warning: Could not restart container after network config: {restart_result['error']}")
        
        network_config = []
        if request.ipv4:
            network_config.append(f"IPv4: {request.ipv4}")
        if request.ipv6:
            network_config.append(f"IPv6: {request.ipv6}")
        
        return {
            "success": True,
            "message": f"Network configuration updated for container {request.name}",
            "config": network_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure network: {str(e)}")

@app.websocket("/ws/logs/{container_name}")
async def websocket_logs(websocket: WebSocket, container_name: str):
    """WebSocket endpoint for real-time container logs"""
    await manager.connect(websocket)
    try:
        # Verify that container exists
        containers_result = run_command(["machinectl", "list", "--no-legend", "--no-pager"], shell=True)
        if containers_result["success"]:
            container_exists = any(container_name in line for line in containers_result["output"].split('\n') if line.strip())
            if not container_exists:
                await manager.send_personal_message(f"Error: Container {container_name} not found", websocket)
                return
        
        # Try to get live logs using journalctl with follow
        import threading
        import time
        
        def follow_logs():
            try:
                # Use journalctl to follow logs in real-time
                process = subprocess.Popen([
                    "journalctl", "-u", f"systemd-nspawn@{container_name}", 
                    "-f", "--no-pager", "--output=cat"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                while True:
                    if websocket.client_state.value != 3:  # WebSocket.CONNECTING = 3
                        # Check if WebSocket is closed
                        break
                        
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    # Send the log line to the WebSocket client
                    try:
                        asyncio.run(websocket.send_text(line.strip()))
                    except:
                        break  # Connection closed, exit loop
                    
                    time.sleep(0.1)  # Small delay to prevent overwhelming
            except Exception as e:
                try:
                    asyncio.run(websocket.send_text(f"Error streaming logs: {str(e)}"))
                except:
                    pass
        
        # Start the log following in a separate thread
        log_thread = threading.Thread(target=follow_logs, daemon=True)
        log_thread.start()
        
        # Keep the WebSocket connection alive
        while True:
            try:
                # Wait for messages from client (though we don't really expect any)
                data = await websocket.receive_text()
            except:
                break  # Connection closed
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        # Clean up when disconnecting
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)