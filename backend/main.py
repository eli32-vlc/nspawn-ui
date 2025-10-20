import json
import subprocess
import string
import random
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import List, Optional
import os
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend

# --- Authentication ---
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
USERS_FILE = "/opt/nspawn-ui/users.json"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    if username in users:
        return User(username=username)
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

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user

# --- App ---
app = FastAPI()

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    if not (form_data.username in users and verify_password(form_data.password, users[form_data.username])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


class Container(BaseModel):
    name: str
    status: str
    ip: Optional[str] = None
    image: str

class ContainerCreate(BaseModel):
    distro: str
    root_password: str
    cpu_max: Optional[int] = None
    memory_max_mb: Optional[int] = None
    storage_max_gb: Optional[int] = None

class SshDetails(BaseModel):
    username: str

class SshKey(BaseModel):
    private_key: str

def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return e.stderr

def generate_container_name(distro: str) -> str:
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{distro}-{random_suffix}"

@app.get("/containers", response_model=List[Container], dependencies=[Depends(get_current_user)])
def list_containers():
    command = ["machinectl", "list", "--json"]
    try:
        output = run_command(command)
        data = json.loads(output)
        containers = []
        for item in data:
            name = item.get("name")
            status = item.get("state")
            image = item.get("class")
            ip_command = ["machinectl", "shell", name, "hostname", "-I"]
            ip_output = run_command(ip_command).strip()
            ip = ip_output.split(' ')[0] if ip_output else None
            containers.append(Container(name=name, status=status, ip=ip, image=image))
        return containers
    except (json.JSONDecodeError, FileNotFoundError):
        return []

@app.post("/containers", response_model=Container, dependencies=[Depends(get_current_user)])
async def create_container(container: ContainerCreate):
    container_name = generate_container_name(container.distro)
    container_path = f"/var/lib/machines/{container_name}"
    loop_file = f"/var/lib/machines/{container_name}.raw"

    if container.storage_max_gb:
        run_command(["dd", "if=/dev/zero", f"of={loop_file}", "bs=1G", f"count={container.storage_max_gb}"])
        run_command(["mkfs.ext4", loop_file])
        os.makedirs(container_path, exist_ok=True)
        run_command(["mount", loop_file, container_path])
    else:
        os.makedirs(container_path, exist_ok=True)

    debootstrap_command = [
        "debootstrap",
        "--variant=minbase",
        container.distro,
        container_path,
    ]
    debootstrap_result = run_command(debootstrap_command)
    if "error" in debootstrap_result.lower():
        if container.storage_max_gb:
            run_command(["umount", container_path])
            run_command(["rm", loop_file])
        run_command(["rm", "-rf", container_path])
        return {"error": f"Debootstrap failed: {debootstrap_result}"}

    password_command = [
        "systemd-nspawn",
        "-D",
        container_path,
        "/bin/sh",
        "-c",
        f"echo 'root:{container.root_password}' | chpasswd",
    ]
    run_command(password_command)

    config_dir = os.path.join(container_path, ".nspawn-ui")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "config.json"), "w") as f:
        json.dump(container.dict(), f)

    if container.storage_max_gb:
        run_command(["umount", container_path])

    new_container = {
        "name": container_name,
        "status": "stopped",
        "image": container.distro,
    }
    return new_container

@app.post("/containers/{container_name}/start", dependencies=[Depends(get_current_user)])
def start_container(container_name: str):
    container_path = f"/var/lib/machines/{container_name}"
    loop_file = f"/var/lib/machines/{container_name}.raw"
    config_path = os.path.join(container_path, ".nspawn-ui", "config.json")

    if os.path.exists(loop_file):
        run_command(["mount", loop_file, container_path])

    properties = []
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        if config.get("cpu_max"):
            properties.append(f'CPUQuota={config["cpu_max"]}% ')
        if config.get("memory_max_mb"):
            properties.append(f'MemoryMax={config["memory_max_mb"]}M')

    command = ["machinectl", "start", container_name]
    if properties:
        command.insert(1, f"--property={''.join(properties)}")

    run_command(command)
    return {"message": f"Container {container_name} started"}

@app.post("/containers/{container_name}/stop", dependencies=[Depends(get_current_user)])
def stop_container(container_name: str):
    container_path = f"/var/lib/machines/{container_name}"
    loop_file = f"/var/lib/machines/{container_name}.raw"

    run_command(["machinectl", "poweroff", container_name])

    if os.path.exists(loop_file):
        run_command(["umount", container_path])

    return {"message": f"Container {container_name} stopped"}

@app.post("/containers/{container_name}/restart", dependencies=[Depends(get_current_user)])
def restart_container(container_name: str):
    stop_container(container_name)
    start_container(container_name)
    return {"message": f"Container {container_name} restarted"}

@app.delete("/containers/{container_name}", dependencies=[Depends(get_current_user)])
def remove_container(container_name: str):
    container_path = f"/var/lib/machines/{container_name}"
    loop_file = f"/var/lib/machines/{container_name}.raw"

    run_command(["machinectl", "terminate", container_name])

    if os.path.exists(loop_file):
        run_command(["rm", loop_file])

    run_command(["rm", "-rf", container_path])
    return {"message": f"Container {container_name} removed"}

@app.get("/containers/{container_name}/logs", dependencies=[Depends(get_current_user)])
def get_container_logs(container_name: str):
    logs = run_command(["journalctl", "-M", container_name, "--no-pager"])
    return {"logs": logs}

@app.get("/containers/{container_name}/network", dependencies=[Depends(get_current_user)])
def get_container_network(container_name: str):
    ip_command = ["machinectl", "shell", container_name, "hostname", "-I"]
    ip_output = run_command(ip_command).strip()
    return {"network": {"ip": ip_output}}

@app.post("/containers/{container_name}/ssh", response_model=SshKey, dependencies=[Depends(get_current_user)])
def setup_ssh(container_name: str, ssh_details: SshDetails):
    container_path = f"/var/lib/machines/{container_name}"

    # Install SSH server
    install_ssh_command = [
        "systemd-nspawn",
        "-D", container_path,
        "apt-get", "update",
    ]
    run_command(install_ssh_command)
    install_ssh_command = [
        "systemd-nspawn",
        "-D", container_path,
        "apt-get", "install", "-y", "openssh-server",
    ]
    run_command(install_ssh_command)

    # Create user
    create_user_command = [
        "systemd-nspawn",
        "-D", container_path,
        "useradd", "-m", ssh_details.username,
    ]
    run_command(create_user_command)

    # Generate SSH key
    key = rsa.generate_private_key(
        backend=crypto_default_backend(),
        public_exponent=65537,
        key_size=2048
    )
    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption()
    )
    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.OpenSSH,
        crypto_serialization.PublicFormat.OpenSSH
    )

    # Setup SSH key
    ssh_dir = f"{container_path}/home/{ssh_details.username}/.ssh"
    authorized_keys_file = f"{ssh_dir}/authorized_keys"

    run_command(["mkdir", "-p", ssh_dir])
    with open(authorized_keys_file, "wb") as f:
        f.write(public_key)

    run_command(["chown", "-R", f"{ssh_details.username}:{ssh_details.username}", f"{container_path}/home/{ssh_details.username}"])
    run_command(["chmod", "700", ssh_dir])
    run_command(["chmod", "600", authorized_keys_file])

    return SshKey(private_key=private_key.decode('utf-8'))
