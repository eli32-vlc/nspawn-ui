# nspawn-ui

A self-hosted container manager that uses **systemd-nspawn** as the backend and provides a **Bootstrap-based WebUI** for managing containers, networking, and logs.  
It supports **dual-stack networking (IPv4 + IPv6)**, **Docker-in-CT**, **nested containers**, and **SSH setup**.

## Features

- **WebUI**: Bootstrap 5 frontend for container management
- **Container Lifecycle**: Create, start, stop, remove containers
- **Multiple Distros**: Support for Debian, Ubuntu, CentOS, Fedora via debootstrap
- **Resource Limits**: CPU, memory, and storage limits per container
- **Networking**: Dual-stack (IPv4 + IPv6) with NAT setup
- **SSH Setup**: Automatic SSH key configuration from WebUI
- **Live Logs**: Container logs viewing in WebUI
- **Docker-in-CT**: Support for running Docker inside containers
- **Nested Containers**: Support for container nesting

## Architecture

### Components

1. **WebUI**: Bootstrap 5 frontend for responsive design
2. **API Backend**: Python FastAPI service for container/networking management
3. **Container Management**: systemd-nspawn with debootstrap support
4. **Networking**: IPv6 setup with multiple options (native, 6in4 tunnel, WireGuard)
5. **Installer**: Bash script to set up the entire system

### Directory Structure

```
nspawn-ui/
├── api/                    # FastAPI backend
│   ├── main.py            # Main API application
│   └── requirements.txt   # Python dependencies
├── webui/                 # Bootstrap frontend
│   ├── index.html         # Main HTML page
│   └── script.js          # Client-side JavaScript
├── installer/             # Installation script
│   └── install.sh         # Main installer
├── systemd/               # Systemd service files
│   └── nspawn-ui.service  # Service unit file
├── utils/                 # Utility scripts
│   ├── containers.py      # Container management utilities
│   └── validate_build.sh  # Build validation script
├── requirements.txt       # Top-level Python dependencies
└── README.md              # This file
```

## Installation

### Prerequisites

- Linux system with systemd
- systemd-container package
- Python 3.8+
- debootstrap (for Debian/Ubuntu containers)

### Automatic Installation

Run the installer script as root:

```bash
sudo ./installer/install.sh
```

The installer will:
- Install required dependencies
- Set up networking (bridge, IPv6 tunnel if needed)
- Create the nspawn-ui user
- Install the API service as a systemd service
- Configure firewall rules for NAT

### Manual Installation

1. Clone the repository
2. Install Python dependencies: `pip install -r requirements.txt`
3. Set up networking configuration
4. Create systemd service file
5. Start the service

## Usage

### Starting the Service

The service should be started automatically by the installer. To start manually:

```bash
sudo systemctl start nspawn-ui
sudo systemctl enable nspawn-ui  # Enable auto-start on boot
```

### Accessing the WebUI

The WebUI is accessible at: `http://<your-server-ip>:8000`

### Command Line Utilities

Use the utility script for container management:

```bash
# List containers
sudo machinectl list

# Create a container using the WebUI or API

# Start/stop containers
sudo machinectl start <container-name>
sudo machinectl stop <container-name>
```

## API Endpoints

The API is available at `http://<server>:8000` with the following endpoints:

- `GET /` - Root endpoint
- `GET /containers` - List all containers
- `POST /containers` - Create a new container
- `POST /containers/start` - Start a container
- `POST /containers/stop` - Stop a container
- `POST /containers/restart` - Restart a container
- `DELETE /containers/{name}` - Remove a container
- `GET /containers/{name}/logs` - Get container logs
- `POST /containers/{name}/ssh` - Setup SSH for container
- `POST /containers/{name}/network` - Configure network for container
- `WEBSOCKET /ws/logs/{container_name}` - Real-time logs

## Networking

The system supports various networking configurations:

1. **IPv4 NAT**: Default outbound internet access via iptables NAT
2. **IPv6**: Support for native IPv6 or 6in4 tunnel (Hurricane Electric style)
3. **Bridge Setup**: systemd-networkd for container networking

## Security

- Service runs under dedicated `nspawn-ui` user
- Limited capabilities (CAP_NET_ADMIN, CAP_SYS_ADMIN)
- Configurable resource limits per container
- Isolated container filesystems

## Development

### Running in Development Mode

```bash
cd nspawn-ui/api
pip install -r ../requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The WebUI files can be served from any static file server, or accessed directly via file:// protocol during development.

## Testing

Validate your installation with the validation script:

```bash
sudo ./utils/validate_build.sh
```

This will check:
- Python dependencies
- Systemd-nspawn tools
- Network configuration
- Service status
- API connectivity
- Directory structure
- And more

## Troubleshooting

- Check service status: `systemctl status nspawn-ui`
- View service logs: `journalctl -u nspawn-ui -f`
- Verify container status: `machinectl list`
- Check networking: `ip addr show` for interface status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see the LICENSE file for details.