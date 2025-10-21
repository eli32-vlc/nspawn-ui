# Developer Guide - Recent Changes

## Architecture Overview

### Backend Structure
```
backend/
├── api/
│   ├── containers.py      # Container CRUD operations, creation status
│   ├── network.py         # Network management
│   ├── system.py          # System information
│   └── ...
├── services/
│   └── container_service.py  # Core container creation logic
└── main.py                # FastAPI app, routes
```

### Frontend Structure
```
frontend/
├── templates/
│   ├── index.html         # Dashboard
│   ├── create_vps.html    # VPS creation wizard
│   ├── network.html       # Network management
│   ├── settings.html      # Settings page
│   └── vps_detail.html    # VPS details
└── static/js/
    ├── create_vps.js      # VPS creation with status polling
    ├── network.js         # Network page logic
    └── settings.js        # Settings page logic
```

## Key Components

### Container Service (`services/container_service.py`)

The `ContainerService` class handles all container lifecycle operations:

```python
class ContainerService:
    def create_container(
        self,
        name: str,
        distro: str,
        root_password: str,
        cpu_quota: int = 100,
        memory_mb: int = 512,
        disk_gb: int = 10,
        enable_ssh: bool = True,
        enable_ipv6: bool = True,
        ipv6_mode: Optional[str] = None,
        wireguard_config: Optional[str] = None,
        status_callback = None
    ) -> Dict
```

**Key Methods:**
- `get_architecture()`: Detects x86_64 or ARM64
- `get_ubuntu_mirror(arch)`: Returns correct mirror for architecture
- `create_container()`: Main creation logic with status callbacks
- `_set_root_password()`: Sets password using systemd-nspawn chroot
- `_configure_network()`: Sets up systemd-networkd
- `_install_ssh()`: Installs and configures OpenSSH
- `_configure_wireguard()`: Installs WireGuard and writes config
- `_create_nspawn_config()`: Creates systemd-nspawn unit config

### Container API (`api/containers.py`)

**Status Tracking:**
```python
creation_status = {
    "container_id": {
        "status": "installing",      # initializing, installing, completed, failed
        "message": "Current step...",
        "progress": 30,              # 0-100
        "error": None
    }
}
```

**New Endpoints:**
- `POST /api/containers/create`: Starts background creation task
- `GET /api/containers/create-status/{container_id}`: Get current status

**Background Task:**
Container creation runs in a background task to avoid blocking. Status updates are provided via callback function that updates the `creation_status` dictionary.

### Frontend Status Polling (`create_vps.js`)

```javascript
// Poll creation status every 2 seconds
async function pollCreationStatus(containerId) {
    const pollInterval = setInterval(async () => {
        const response = await fetch(
            `${API_BASE}/api/containers/create-status/${containerId}`,
            { headers: getAuthHeaders() }
        );
        
        const status = await response.json();
        
        // Update UI: progress bar, message
        // Stop polling on completed/failed
    }, 2000);
}
```

## ARM64 Support Implementation

### Mirror Selection Logic
```python
def get_ubuntu_mirror(self, arch: str) -> str:
    """Get the appropriate Ubuntu mirror based on architecture"""
    if arch == "arm64":
        return "http://ports.ubuntu.com/ubuntu-ports"
    else:
        return "http://archive.ubuntu.com/ubuntu"
```

### Architecture Detection
```python
def get_architecture(self) -> str:
    """Get the system architecture"""
    arch = platform.machine()
    # Normalize architecture names
    if arch in ["aarch64", "arm64"]:
        return "arm64"
    elif arch in ["x86_64", "amd64"]:
        return "amd64"
    return arch
```

### Usage in Debootstrap
```python
# Get appropriate mirror
if distro_name == "ubuntu":
    mirror = self.get_ubuntu_mirror(arch)
else:
    mirror = self.get_debian_mirror(arch)

# Run debootstrap with correct architecture
cmd = [
    "debootstrap",
    "--arch=" + arch,
    suite,
    str(container_dir),
    mirror
]
```

## WireGuard Integration

### User Flow
1. User selects "WireGuard" in IPv6 mode dropdown
2. Textarea appears for configuration input
3. Configuration is validated (basic check for content)
4. Config is passed to backend in `wireguard_config` field
5. Backend writes to `/etc/wireguard/wg0.conf` in container
6. WireGuard packages are installed
7. `wg-quick@wg0` service is enabled

### Implementation
```python
def _configure_wireguard(self, container_dir: Path, wireguard_config: str):
    # Create wireguard directory
    wg_dir = container_dir / "etc" / "wireguard"
    wg_dir.mkdir(parents=True, exist_ok=True)
    
    # Write config with restricted permissions
    wg_config_file = wg_dir / "wg0.conf"
    wg_config_file.write_text(wireguard_config)
    wg_config_file.chmod(0o600)
    
    # Install wireguard via systemd-nspawn
    install_script = """#!/bin/bash
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y wireguard wireguard-tools
    systemctl enable wg-quick@wg0
    """
    # Execute in container...
```

## Testing

### Manual Testing Checklist

**VPS Creation (x86_64):**
- [ ] Create Debian container
- [ ] Create Ubuntu 22.04 container
- [ ] Create Ubuntu 24.04 container
- [ ] Enable SSH
- [ ] Enable IPv6 with native mode
- [ ] Enable IPv6 with WireGuard

**VPS Creation (ARM64):**
- [ ] Verify mirror is `ports.ubuntu.com`
- [ ] Create Ubuntu 22.04 container
- [ ] Verify packages install correctly

**Status Tracking:**
- [ ] Progress bar updates during creation
- [ ] Status messages appear
- [ ] Completion redirects to dashboard
- [ ] Error messages display on failure

**Network Page:**
- [ ] Bridge status loads
- [ ] IPv6 mode selection works
- [ ] Port forwarding modal opens

**Settings Page:**
- [ ] System info loads
- [ ] Storage info displays
- [ ] Preferences can be saved

### API Testing

**Test Container Creation:**
```bash
curl -X POST http://localhost:8080/api/containers/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-vps",
    "distro": "ubuntu:22.04",
    "root_password": "secure123",
    "cpu_quota": 100,
    "memory_mb": 512,
    "disk_gb": 10,
    "enable_ssh": true,
    "enable_ipv6": true,
    "ipv6_mode": "native"
  }'
```

**Check Status:**
```bash
curl http://localhost:8080/api/containers/create-status/test-vps \
  -H "Authorization: Bearer $TOKEN"
```

## Common Development Tasks

### Adding a New Distribution

1. Update `services/container_service.py`:
   ```python
   elif distro_name == "alpine":
       # Implement Alpine Linux support
       # May need different tools than debootstrap
   ```

2. Update `frontend/static/js/create_vps.js`:
   ```javascript
   const distroVersions = {
       'debian': ['bookworm', 'bullseye', 'sid'],
       'ubuntu': ['24.04', '22.04', '20.04'],
       'alpine': ['3.18', '3.17'],  // Add new distro
       'arch': ['latest']
   };
   ```

### Adding Status Messages

Update the callback in `api/containers.py`:
```python
def update_creation_status(message: str):
    if container_id in creation_status:
        creation_status[container_id]["message"] = message
        # Add new keyword matching
        if "your_keyword" in message.lower():
            creation_status[container_id]["progress"] = 50
```

### Debugging Container Creation

1. Enable debug logging in container service:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Check container filesystem:
   ```bash
   ls -la /var/lib/machines/CONTAINER_NAME/
   ```

3. Check systemd-nspawn status:
   ```bash
   systemctl status systemd-nspawn@CONTAINER_NAME
   ```

4. Access container:
   ```bash
   machinectl shell CONTAINER_NAME
   ```

## Performance Considerations

### Background Tasks
Container creation runs asynchronously to prevent API timeouts. FastAPI's `BackgroundTasks` is used:

```python
async def create_container(
    container: ContainerCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_token)
):
    background_tasks.add_task(create_container_task)
```

### Status Polling
Frontend polls status every 2 seconds. This is a reasonable balance between responsiveness and server load. For production, consider:
- WebSocket for real-time updates
- Exponential backoff for polling
- Caching status responses

### Resource Cleanup
Failed container creation attempts clean up partial filesystems:
```python
except Exception as e:
    if container_dir.exists():
        subprocess.run(["rm", "-rf", str(container_dir)])
    raise
```

## Security Considerations

1. **Root Password**: Stored only temporarily, never logged
2. **WireGuard Config**: Saved with 0600 permissions
3. **Container Isolation**: systemd-nspawn provides namespace isolation
4. **Resource Limits**: Enforced via cgroups

## Future Improvements

1. **WebSocket Status**: Replace polling with WebSocket for real-time updates
2. **Template System**: Pre-configured container templates
3. **Snapshot Support**: Container snapshots using btrfs/lvm
4. **Metrics**: Resource usage monitoring and graphing
5. **Multi-host**: Federation across multiple hosts
