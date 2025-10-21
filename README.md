# ZenithStack

**Self-Hosted Container Management Platform**

A production-grade, self-hosted VPS container orchestration platform leveraging **systemd-nspawn** with a modern **Bootstrap 5 WebUI**. Enterprise-level container management with advanced networking, cross-architecture support, and real-time monitoring.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)

## Features

### 🚀 Container Management
- **Multi-Distribution Support**: Debian, Ubuntu, Arch Linux with automatic architecture detection
- **Resource Control**: CPU, memory, and disk quota management with real-time monitoring
- **One-Click Operations**: Start, stop, restart, and delete containers from the WebUI
- **SSH Integration**: Automatic SSH server setup with password authentication

### 🌐 Advanced Networking
- **IPv4 NAT**: Automatic NAT configuration for container internet access
- **IPv6 Support**: Native IPv6, 6in4 tunnels, or WireGuard VPN integration
- **Port Forwarding**: Easy port mapping for exposing container services
- **DNS Configuration**: Automatic DNS setup (8.8.8.8, 1.1.1.1)

### 💻 Modern WebUI
- **Bootstrap 5 Interface**: Responsive, mobile-first design
- **Real-Time Updates**: Live status indicators and metrics
- **Multi-Step Wizard**: Intuitive VPS creation process
- **Live Logs**: Real-time log streaming with WebSocket support

### 🔒 Security
- **JWT Authentication**: Secure token-based authentication
- **User Isolation**: systemd-nspawn namespace isolation
- **Resource Limits**: Prevent resource exhaustion with cgroup controls

## Quick Start

### Prerequisites

- **Linux Distribution**: Ubuntu 20.04+, Debian 11+, Arch Linux, or compatible
- **systemd**: Version 239 or higher
- **Root Access**: Installation requires sudo/root privileges
- **Disk Space**: Minimum 10GB available
- **Architecture**: x86_64 or ARM64/aarch64

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/eli32-vlc/nspawn-ui.git
   cd nspawn-ui
   ```

2. **Run the installer**:
   ```bash
   sudo ./install.sh
   ```

3. **Follow the interactive prompts**:
   - System dependency installation
   - Network configuration (IPv4/IPv6)
   - Admin credentials setup

4. **Access the WebUI**:
   - Open your browser to `http://YOUR_SERVER_IP:8080`
   - Login with credentials: `admin` / `admin`
   - **⚠️ Change the default password immediately!**

## Architecture

### Technology Stack

**Backend:**
- **FastAPI**: High-performance async web framework
- **Uvicorn**: ASGI server for production deployment
- **Python 3.9+**: Modern Python runtime
- **systemd-nspawn**: Container runtime engine

**Frontend:**
- **Bootstrap 5**: Responsive UI framework
- **Vanilla JavaScript**: No heavy frameworks, fast and efficient
- **WebSocket**: Real-time log streaming

**Networking:**
- **systemd-networkd**: Modern Linux networking
- **iptables/nftables**: Firewall and NAT management
- **Bridge networking**: Container network isolation

### Directory Structure

```
/opt/zenithstack/          # Application files
├── backend/               # Python FastAPI backend
│   ├── api/              # API endpoints
│   ├── core/             # Core configuration
│   ├── models/           # Data models
│   └── services/         # Business logic
└── frontend/             # WebUI files
    ├── static/           # CSS, JS, images
    └── templates/        # HTML templates

/var/lib/zenithstack/     # Application data
/var/lib/machines/        # Container storage
/etc/zenithstack/         # Configuration files
/var/log/zenithstack/     # Log files
```

## Usage

### Creating a VPS

1. Navigate to **Create VPS** in the WebUI
2. **Step 1 - Basic Configuration**:
   - Enter VPS name (lowercase, hyphens allowed)
   - Select distribution (Debian, Ubuntu, Arch)
   - Choose version
   - Set root password (minimum 8 characters)

3. **Step 2 - Resource Allocation**:
   - CPU Limit: 100% = 1 core (slider from 25% to 400%)
   - Memory: 256MB to 8GB
   - Disk Quota: 5GB to 100GB

4. **Step 3 - Advanced Options**:
   - Enable SSH server (recommended)
   - Enable IPv6 networking
   - Click **Create VPS**

### Managing VPS Instances

**Dashboard View:**
- See all VPS instances with status indicators
- Filter and search by name, status, or distribution
- Quick actions: Start, Stop, Delete

**VPS Detail View:**
- Click any VPS to see detailed information
- View network addresses (IPv4 NAT, IPv6 global)
- Monitor resource usage (CPU, Memory, Disk)
- Stream real-time logs
- Control buttons: Start, Stop, Restart, Delete

### API Access

The platform provides a RESTful API for automation:

**Authentication:**
```bash
curl -X POST http://YOUR_SERVER:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

**List VPS Instances:**
```bash
curl http://YOUR_SERVER:8080/api/containers \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Create VPS:**
```bash
curl -X POST http://YOUR_SERVER:8080/api/containers/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-vps",
    "distro": "debian:bookworm",
    "root_password": "secure_password",
    "cpu_quota": 100,
    "memory_mb": 512,
    "disk_gb": 10,
    "enable_ssh": true,
    "enable_ipv6": true
  }'
```

**API Documentation:**
- Interactive docs: `http://YOUR_SERVER:8080/docs`
- ReDoc: `http://YOUR_SERVER:8080/redoc`

## Network Configuration

### IPv4 NAT (Default)
- Containers use private subnet: `10.0.0.0/24`
- Automatic NAT masquerading for internet access
- Port forwarding available via API

### IPv6 Options

**Native IPv6:**
- Automatic if IPv6 connectivity detected
- Each container gets a globally routable address

**6in4 Tunnel (Hurricane Electric):**
```bash
# During installation, provide:
- Tunnel server IPv4
- Tunnel client IPv6
- Routed IPv6 prefix
```

**WireGuard VPN:**
```bash
# Install WireGuard and configure
sudo apt install wireguard
# Place config in /etc/wireguard/wg0.conf
```

## Troubleshooting

### Service won't start
```bash
# Check service status
sudo systemctl status zenithstack

# View logs
sudo journalctl -u zenithstack -f

# Restart service
sudo systemctl restart zenithstack
```

### Can't access WebUI
```bash
# Check if port 8080 is open
sudo netstat -tlnp | grep 8080

# Check firewall
sudo ufw status
sudo ufw allow 8080/tcp
```

### Container creation fails
```bash
# Check systemd-nspawn availability
machinectl --version

# Verify debootstrap
which debootstrap

# Check disk space
df -h /var/lib/machines
```

### Network issues
```bash
# Check IP forwarding
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding

# Verify NAT rules
sudo iptables -t nat -L -n -v
```

## Development

### Running in Development Mode

```bash
# Navigate to backend
cd /opt/zenithstack/backend

# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
ZENITH_DEBUG=true python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### Project Structure

```
backend/
├── main.py              # Application entry point
├── api/                 # API endpoints
│   ├── auth.py         # Authentication
│   ├── containers.py   # Container management
│   ├── network.py      # Network configuration
│   ├── ssh.py          # SSH setup
│   ├── system.py       # System information
│   └── logs.py         # Logging & monitoring
├── core/
│   └── config.py       # Configuration settings
└── requirements.txt    # Python dependencies

frontend/
├── templates/          # HTML templates
│   ├── index.html     # Dashboard
│   ├── login.html     # Login page
│   ├── create_vps.html # VPS creation wizard
│   └── vps_detail.html # VPS detail view
└── static/
    ├── css/
    │   └── style.css  # Custom styles
    └── js/
        ├── login.js
        ├── dashboard.js
        ├── create_vps.js
        └── vps_detail.js
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **systemd-nspawn**: The lightweight container runtime
- **FastAPI**: Modern Python web framework
- **Bootstrap**: Responsive UI framework
- Hurricane Electric for IPv6 tunnel services

## Support

For issues, questions, or contributions:
- GitHub Issues: [https://github.com/eli32-vlc/nspawn-ui/issues](https://github.com/eli32-vlc/nspawn-ui/issues)
- Documentation: See `/docs` directory

## Roadmap

- [ ] Multi-user support with RBAC
- [ ] Container snapshots and backups
- [ ] HTTPS/TLS support with Let's Encrypt
- [ ] Container templates and cloning
- [ ] Advanced monitoring and alerting
- [ ] Multi-host federation
- [ ] Web-based terminal (ttyd integration)
- [ ] Docker-in-container support

---

**ZenithStack** - Elevating Container Management to New Heights
