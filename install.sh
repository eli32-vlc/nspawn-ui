#!/bin/bash

# nspawn-vps Automated Installer
# Comprehensive Container Management Platform

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/nspawn-manager"
SYSTEMD_SERVICE_DIR="/etc/systemd/system"
CONFIG_DIR="/etc/nspawn-manager"
LOG_DIR="/var/log/nspawn-manager"
MACHINES_DIR="/var/lib/machines"

# Logging function
log() {
    local message="$1"
    local timestamp
    timestamp="$(date +'%Y-%m-%d %H:%M:%S')"

    echo -e "${BLUE}[$timestamp]${NC} $message"

    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR"
    fi
    if [[ ! -f "$LOG_DIR/install.log" ]]; then
        touch "$LOG_DIR/install.log"
    fi

    echo "[$timestamp] $message" >> "$LOG_DIR/install.log"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
    log "[INFO] $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    log "[WARNING] $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log "[ERROR] $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if systemd is available
    if ! command -v systemctl &> /dev/null; then
        log_error "systemd is not available. This installer only works on systemd-based systems."
        exit 1
    fi

    # Check architecture
    ARCH=$(uname -m)
    if [[ "$ARCH" != "x86_64" && "$ARCH" != "aarch64" ]]; then
        log_error "Unsupported architecture: $ARCH. Only x86_64 and aarch64 are supported."
        exit 1
    fi
    log_info "Architecture: $ARCH"

    # Check disk space (at least 10GB free)
    # Use df in 1K-blocks (default); 10GB = 10 * 1024 * 1024 = 10485760 blocks
    FREE_SPACE=$(df --output=avail / | tail -n 1)
    if [[ $FREE_SPACE -lt 10485760 ]]; then  # 10GB in 1K blocks
        log_warn "Less than 10GB free space available. Installation may fail."
    else
        log_info "Sufficient disk space available"
    fi

    # Check distribution
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "Distribution: $NAME ($VERSION)"
    else
        log_error "Cannot determine Linux distribution"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    # Create log directory
    mkdir -p /var/log/nspawn-manager
    touch /var/log/nspawn-manager/install.log

    case "$ID" in
        ubuntu|debian)
            apt-get update
            apt-get install -y \
                systemd-container \
                debootstrap \
                python3 \
                python3-pip \
                python3-venv \
                python3-systemd \
                bridge-utils \
                iptables \
                dnsmasq \
                wireguard-tools \
                iproute2 \
                btrfs-progs \
                lvm2 \
                curl \
                wget \
                git \
                jq \
                dnsutils \
                net-tools
            ;;
        fedora|centos|rhel)
            dnf install -y \
                systemd-container \
                debootstrap \
                python3 \
                python3-pip \
                python3-venv \
                python3-systemd \
                bridge-utils \
                iptables \
                dnsmasq \
                wireguard-tools \
                iproute \
                btrfs-progs \
                lvm2 \
                curl \
                wget \
                git \
                jq \
                bind-utils \
                net-tools
            ;;
        arch)
            pacman -Sy --noconfirm \
                systemd-container \
                debootstrap \
                python \
                python-pip \
                python-systemd \
                bridge-utils \
                iptables \
                dnsmasq \
                wireguard-tools \
                iproute2 \
                btrfs-progs \
                lvm2 \
                curl \
                wget \
                git \
                jq \
                dnsutils \
                net-tools
            ;;
        *)
            log_error "Unsupported distribution: $ID"
            exit 1
            ;;
    esac

    # Install Python packages
    pip3 install --upgrade pip
    pip3 install fastapi uvicorn websockets pydantic sqlalchemy python-multipart bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv
}

# Create system user
create_system_user() {
    log_info "Creating system user..."

    # Check if user already exists
    if id "nspawn-manager" &>/dev/null; then
        log_info "User nspawn-manager already exists"
        return 0
    fi

    # Create system user
    useradd --system --no-create-home --shell /bin/false nspawn-manager
    log_info "Created system user nspawn-manager"
}

# Create directory structure
create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/backend"
    mkdir -p "$INSTALL_DIR/frontend"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    
    # Set proper permissions
    chown -R nspawn-manager:nspawn-manager "$INSTALL_DIR"
    chown -R nspawn-manager:nspawn-manager "$LOG_DIR"
    chmod 755 "$INSTALL_DIR"
}

# Detect IPv6 connectivity
detect_ipv6() {
    log_info "Detecting IPv6 connectivity..."
    
    # Use ping -6 where available; ping6 may not exist on all distros
    if ping -6 -c 1 -W 3 google.com &>/dev/null || ping -6 -c 1 -W 3 ipv6.google.com &>/dev/null; then
        HAS_IPV6=true
        log_info "IPv6 connectivity detected"
        return 0
    else
        HAS_IPV6=false
        log_warn "No IPv6 connectivity detected"
        return 1
    fi
}

# Configure networking
configure_networking() {
    log_info "Configuring networking..."

    # Enable IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    echo 1 > /proc/sys/net/ipv6/conf/all/forwarding
    
    # Make IP forwarding persistent
    cat > /etc/sysctl.d/99-nspawn-vps.conf << EOF
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF
    
    # Bridge creation and NAT are managed by the nspawn-bridge.service to avoid duplication
    log_info "Deferring bridge and NAT setup to nspawn-bridge.service"
}

# Interactive network configuration
interactive_networking() {
    log_info "Configuring network settings..."
    
    # IPv6 detection
    if detect_ipv6; then
        echo
        read -p "Native IPv6 detected. Would you like to use it for container networking? (yes/no): " USE_NATIVE_IPV6
        
        if [[ "$USE_NATIVE_IPV6" =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Configuring native IPv6 for containers..."
            
            # Find the current IPv6 address and subnet
            IPV6_ADDR=$(ip -6 addr show | grep 'inet6.*global' | head -n 1 | awk '{print $2}')
            if [[ -n "$IPV6_ADDR" ]]; then
                log_info "Current IPv6 address: $IPV6_ADDR"
                # We'll configure IPv6 networking for containers later
            fi
        else
            USE_NATIVE_IPV6="no"
        fi
    else
        USE_NATIVE_IPV6="no"
    fi
    
    if [[ "$USE_NATIVE_IPV6" != "yes" ]]; then
        echo
        read -p "Would you like to configure a 6in4 tunnel for IPv6? (yes/no): " USE_6IN4
        
        if [[ "$USE_6IN4" =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Configuring 6in4 tunnel..."
            
            read -p "Enter tunnel server IPv4 address: " TUNNEL_SERVER
            read -p "Enter tunnel client IPv6 address: " TUNNEL_CLIENT_IP6
            read -p "Enter routed IPv6 prefix (e.g., 2001:db8:1232::/48): " IPV6_PREFIX
            
            # Create sit0 tunnel interface
            cat > /etc/systemd/network/sit0.netdev << EOF
[NetDev]
Name=sit0
Kind=sit

[Tunnel]
Remote=$TUNNEL_SERVER
Local=0.0.0.0
Ttl=255
EOF

            cat > /etc/systemd/network/sit0.network << EOF
[Match]
Name=sit0

[Network]
IPv6AcceptRA=no

[Address]
Address=$TUNNEL_CLIENT_IP6

[Route]
Gateway=${TUNNEL_CLIENT_IP6%::*}::1
EOF

            systemctl enable systemd-networkd
            systemctl restart systemd-networkd
            
        else
            read -p "Would you like to configure a WireGuard tunnel for IPv6? (yes/no): " USE_WIREGUARD
            
            if [[ "$USE_WIREGUARD" =~ ^[Yy][Ee][Ss]$ ]]; then
                log_info "Configuring WireGuard tunnel..."
                
                read -p "Enter WireGuard server public key: " WG_SERVER_PUBKEY
                read -p "Enter WireGuard client private key: " WG_CLIENT_PRIVKEY
                read -p "Enter WireGuard endpoint (host:port): " WG_ENDPOINT
                read -p "Enter WireGuard tunnel address(es) for this host (comma separated, e.g., 2001:db8::2/64): " WG_INTERFACE_ADDRS
                read -p "Enter allowed IPv6 subnets (comma separated): " WG_ALLOWED_IPS
                
                # Install wireguard if not already installed
                if ! command -v wg &>/dev/null; then
                    case "$ID" in
                        ubuntu|debian)
                            apt-get install -y wireguard
                            ;;
                        fedora)
                            dnf install -y wireguard-tools
                            ;;
                        arch)
                            pacman -S --noconfirm wireguard-tools
                            ;;
                    esac
                fi
                
                # Create WireGuard configuration
                mkdir -p /etc/wireguard
                cat > /etc/wireguard/wg0.conf << EOF
[Interface]
PrivateKey = $WG_CLIENT_PRIVKEY
Address = $WG_INTERFACE_ADDRS

[Peer]
PublicKey = $WG_SERVER_PUBKEY
Endpoint = $WG_ENDPOINT
AllowedIPs = $WG_ALLOWED_IPS
EOF
                
                systemctl enable wg-quick@wg0
                systemctl start wg-quick@wg0
            else
                log_warn "No IPv6 connectivity will be available. Containers will only have IPv4 access."
            fi
        fi
    fi
}

# Deploy backend application
deploy_backend() {
    log_info "Deploying backend application..."

    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Install Python dependencies
    pip install fastapi uvicorn websockets pydantic sqlalchemy python-multipart bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv
    
    # Copy backend file from our source
    if [[ ! -f "$SCRIPT_DIR/backend/main.py" ]]; then
        log_error "Backend source file $SCRIPT_DIR/backend/main.py not found!"
        return 1
    fi
    cp "$SCRIPT_DIR/backend/main.py" "$INSTALL_DIR/backend/main.py"

    # Compile Python bytecode for faster startup using py_compile
    "$INSTALL_DIR/venv/bin/python" -m compileall "$INSTALL_DIR/backend/"
    
    # Set ownership
    chown -R nspawn-manager:nspawn-manager "$INSTALL_DIR/backend"
}

# Deploy frontend
deploy_frontend() {
    log_info "Deploying frontend application..."

    # Create basic HTML structure
    mkdir -p "$INSTALL_DIR/frontend"
    
    # Create main HTML page
    cat > "$INSTALL_DIR/frontend/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>nspawn-vps - Container Management</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="bi bi-server"></i> nspawn-vps
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="#" onclick="showDashboard()">Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="showContainers()">Containers</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="showCreate()">Create</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="showNetwork()">Network</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="showSystem()">System</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="showMonitoring()">Monitoring</a>
                    </li>
                </ul>
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="#" id="loginStatus">Login</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4" id="mainContent">
        <!-- Dashboard will be loaded here -->
        <div id="dashboardView">
            <div class="row">
                <div class="col-md-12">
                    <h2>Container Management Dashboard</h2>
                    <div class="card">
                        <div class="card-body">
                            <p>Welcome to nspawn-vps - Your self-hosted container management platform.</p>
                            <p>Use the navigation menu to manage your containers, create new ones, or configure networking.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- System stats -->
            <div class="row mt-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-server text-primary"></i> Total Containers</h5>
                            <h3 class="text-primary" id="totalContainers">0</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-play-circle text-success"></i> Running</h5>
                            <h3 class="text-success" id="runningContainers">0</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-stop-circle text-warning"></i> Stopped</h5>
                            <h3 class="text-warning" id="stoppedContainers">0</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title"><i class="bi bi-cpu text-info"></i> System Load</h5>
                            <h3 class="text-info" id="systemLoad">0%</h3>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick actions -->
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <button class="btn btn-primary me-md-2" type="button" onclick="showCreate()">
                            <i class="bi bi-plus-circle"></i> Create Container
                        </button>
                        <button class="btn btn-outline-primary" type="button" onclick="refreshContainers()">
                            <i class="bi bi-arrow-clockwise"></i> Refresh
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Containers list will be loaded here -->
        <div id="containersView" style="display: none;">
            <div class="row">
                <div class="col-md-12">
                    <h2>Containers</h2>
                    <div class="card">
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-striped" id="containersTable">
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>Status</th>
                                            <th>Distribution</th>
                                            <th>IP Address</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="containersList">
                                        <!-- Container rows will be populated here -->
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Create container form will be loaded here -->
        <div id="createView" style="display: none;">
            <div class="row">
                <div class="col-md-12">
                    <h2>Create New Container</h2>
                    <div class="card">
                        <div class="card-body">
                            <form id="createContainerForm">
                                <div class="mb-3">
                                    <label for="containerName" class="form-label">Container Name</label>
                                    <input type="text" class="form-control" id="containerName" required>
                                </div>
                                <div class="row">
                                    <div class="col-md-6">
                                        <label for="distroSelect" class="form-label">Distribution</label>
                                        <select class="form-select" id="distroSelect" required>
                                            <option value="debian">Debian</option>
                                            <option value="ubuntu">Ubuntu</option>
                                            <option value="fedora">Fedora</option>
                                            <option value="alpine">Alpine</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="archSelect" class="form-label">Architecture</label>
                                        <select class="form-select" id="archSelect" required>
                                            <option value="x86_64">x86_64</option>
                                            <option value="arm64">arm64</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="rootPassword" class="form-label">Root Password</label>
                                    <input type="password" class="form-control" id="rootPassword" required>
                                </div>
                                <div class="row">
                                    <div class="col-md-4">
                                        <label for="cpuLimit" class="form-label">CPU Limit</label>
                                        <input type="text" class="form-control" id="cpuLimit" placeholder="e.g., 1.0 (1 core)">
                                    </div>
                                    <div class="col-md-4">
                                        <label for="memoryLimit" class="form-label">Memory Limit</label>
                                        <input type="text" class="form-control" id="memoryLimit" placeholder="e.g., 1G">
                                    </div>
                                    <div class="col-md-4">
                                        <label for="storageLimit" class="form-label">Storage Limit</label>
                                        <input type="text" class="form-control" id="storageLimit" placeholder="e.g., 10G">
                                    </div>
                                </div>
                                <div class="mb-3 form-check">
                                    <input type="checkbox" class="form-check-input" id="enableSSH">
                                    <label class="form-check-label" for="enableSSH">Enable SSH Access</label>
                                </div>
                                <div class="mb-3 form-check">
                                    <input type="checkbox" class="form-check-input" id="enableDocker">
                                    <label class="form-check-label" for="enableDocker">Enable Docker-in-Container</label>
                                </div>
                                <button type="submit" class="btn btn-primary">Create Container</button>
                                <button type="button" class="btn btn-secondary" onclick="showDashboard()">Cancel</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Network config will be loaded here -->
        <div id="networkView" style="display: none;">
            <div class="row">
                <div class="col-md-12">
                    <h2>Network Configuration</h2>
                    <div class="card">
                        <div class="card-body">
                            <h5>Bridge Status: <span id="networkStatus" class="badge bg-secondary">Unknown</span></h5>
                            <p>Bridge Name: <code id="bridgeName">br0</code></p>
                            <p>IPv4 NAT is configured to allow containers internet access.</p>
                            
                            <h5 class="mt-4">Bridge Details</h5>
                            <div id="bridgeDetails">Loading bridge information...</div>
                            
                            <h5 class="mt-4">Container IP Addresses</h5>
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Container</th>
                                            <th>IPv4</th>
                                            <th>IPv6</th>
                                        </tr>
                                    </thead>
                                    <tbody id="networkList">
                                        <!-- Network info will be populated here -->
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- System info will be loaded here -->
        <div id="systemView" style="display: none;">
            <div class="row">
                <div class="col-md-12">
                    <h2>System Information</h2>
                    <div class="card">
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h5>Memory Information</h5>
                                    <div id="systemMemory">Loading...</div>
                                </div>
                                <div class="col-md-6">
                                    <h5>Disk Usage</h5>
                                    <div id="systemDisk">Loading...</div>
                                </div>
                            </div>
                            <div class="row mt-3">
                                <div class="col-md-12">
                                    <h5>System Load</h5>
                                    <div id="systemLoad">Loading...</div>
                                    <small class="text-muted">Last updated: <span id="systemTimestamp">N/A</span></small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal for showing logs/details -->
    <div class="modal fade" id="logsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="logsModalLabel">Container Logs</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="logsContent" class="bg-light p-2 rounded" style="height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px;">
                        <!-- Logs will be displayed here -->
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS and dependencies -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="js/app.js"></script>
</body>
</html>
EOF

    # Create frontend JS
    mkdir -p "$INSTALL_DIR/frontend/js"
    cat > "$INSTALL_DIR/frontend/js/app.js" << 'EOF'
// nspawn-vps Frontend Application
let authToken = localStorage.getItem('authToken');
let currentView = 'dashboard';
let logWebSocket = null;

// API base URL
const API_BASE = '/api';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in
    checkLoginStatus();
    
    // Load dashboard by default
    loadDashboard();
    
    // Set up form submission
    document.getElementById('createContainerForm').addEventListener('submit', handleCreateContainer);
});

// Navigation functions
function showDashboard() {
    document.getElementById('dashboardView').style.display = 'block';
    document.getElementById('containersView').style.display = 'none';
    document.getElementById('createView').style.display = 'none';
    document.getElementById('networkView').style.display = 'none';
    document.getElementById('systemView').style.display = 'none';
    currentView = 'dashboard';
    loadDashboard();
}

function showContainers() {
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('containersView').style.display = 'block';
    document.getElementById('createView').style.display = 'none';
    document.getElementById('networkView').style.display = 'none';
    document.getElementById('systemView').style.display = 'none';
    currentView = 'containers';
    loadContainers();
}

function showCreate() {
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('containersView').style.display = 'none';
    document.getElementById('createView').style.display = 'block';
    document.getElementById('networkView').style.display = 'none';
    document.getElementById('systemView').style.display = 'none';
    currentView = 'create';
}

function showNetwork() {
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('containersView').style.display = 'none';
    document.getElementById('createView').style.display = 'none';
    document.getElementById('networkView').style.display = 'block';
    document.getElementById('systemView').style.display = 'none';
    currentView = 'network';
    loadNetworkInfo();
}

function showSystem() {
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('containersView').style.display = 'none';
    document.getElementById('createView').style.display = 'none';
    document.getElementById('networkView').style.display = 'none';
    document.getElementById('systemView').style.display = 'block';
    currentView = 'system';
    loadSystemInfo();
}

function showMonitoring() {
    // We'll add monitoring to the system view for now
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('containersView').style.display = 'none';
    document.getElementById('createView').style.display = 'none';
    document.getElementById('networkView').style.display = 'none';
    document.getElementById('systemView').style.display = 'block';
    currentView = 'monitoring';
    loadMonitoringOverview();
}

// Authentication functions
function checkLoginStatus() {
    const loginStatus = document.getElementById('loginStatus');
    if (authToken) {
        loginStatus.textContent = 'Logout';
        loginStatus.onclick = logout;
    } else {
        loginStatus.textContent = 'Login';
        loginStatus.onclick = showLogin;
    }
}

function showLogin() {
    // Simple login modal would go here
    const username = prompt('Enter username:');
    const password = prompt('Enter password:');
    
    if (username && password) {
        login(username, password);
    }
}

async function login(username, password) {
    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            checkLoginStatus();
            alert('Login successful!');
        } else {
            alert('Invalid credentials');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed');
    }
}

function logout() {
    authToken = null;
    localStorage.removeItem('authToken');
    checkLoginStatus();
    showDashboard();
    alert('Logged out');
}

// Dashboard functions
async function loadDashboard() {
    try {
        const stats = await fetchSystemStats();
        document.getElementById('totalContainers').textContent = stats.total || 0;
        document.getElementById('runningContainers').textContent = stats.running || 0;
        document.getElementById('stoppedContainers').textContent = stats.stopped || 0;
        document.getElementById('systemLoad').textContent = stats.load || '0%';
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

// Containers functions
async function loadContainers() {
    try {
        const containers = await fetchContainers();
        renderContainersList(containers);
    } catch (error) {
        console.error('Error loading containers:', error);
        document.getElementById('containersList').innerHTML = '<tr><td colspan="5">Error loading containers</td></tr>';
    }
}

async function fetchContainers() {
    const response = await fetch(`${API_BASE}/containers`, {
        headers: {
            'Authorization': `Bearer ${authToken}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch containers');
    }
    
    return await response.json();
}

function renderContainersList(containers) {
    const containerList = document.getElementById('containersList');
    containerList.innerHTML = '';
    
    containers.forEach(container => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${container.name}</td>
            <td>
                <span class="badge bg-${container.state === 'running' ? 'success' : container.state === 'stopped' ? 'secondary' : 'warning'}">
                    ${container.state}
                </span>
            </td>
            <td>${container.distro || 'N/A'}</td>
            <td>${container.ip_address || 'N/A'}</td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-success" onclick="startContainer('${container.name}')">Start</button>
                    <button class="btn btn-sm btn-warning" onclick="stopContainer('${container.name}')">Stop</button>
                    <button class="btn btn-sm btn-info" onclick="showContainerLogs('${container.name}')">Logs</button>
                    <button class="btn btn-sm btn-primary dropdown-toggle" type="button" id="actionDropdown" data-bs-toggle="dropdown">Actions</button>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="#" onclick="showContainerDetails('${container.name}')">Details</a></li>
                        <li><a class="dropdown-item" href="#" onclick="restartContainer('${container.name}')">Restart</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item text-danger" href="#" onclick="deleteContainer('${container.name}')">Delete</a></li>
                    </ul>
                </div>
            </td>
        `;
        containerList.appendChild(row);
    });
}

async function handleCreateContainer(event) {
    event.preventDefault();
    
    const config = {
        name: document.getElementById('containerName').value,
        distro: document.getElementById('distroSelect').value,
        architecture: document.getElementById('archSelect').value,
        root_password: document.getElementById('rootPassword').value,
        cpu_limit: document.getElementById('cpuLimit').value || null,
        memory_limit: document.getElementById('memoryLimit').value || null,
        storage_limit: document.getElementById('storageLimit').value || null,
        enable_ssh: document.getElementById('enableSSH').checked,
        enable_docker: document.getElementById('enableDocker').checked
    };
    
    try {
        const response = await fetch(`${API_BASE}/containers/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            alert('Container created successfully!');
            document.getElementById('createContainerForm').reset();
            showDashboard();
        } else {
            const error = await response.json();
            alert(`Error creating container: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating container:', error);
        alert('Error creating container');
    }
}

async function startContainer(containerId) {
    try {
        const response = await fetch(`${API_BASE}/containers/${containerId}/start`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            alert(`Container ${containerId} started successfully`);
            if (currentView === 'containers' || currentView === 'dashboard') {
                loadContainers();
            }
        } else {
            const error = await response.json();
            alert(`Error starting container: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting container:', error);
        alert('Error starting container');
    }
}

async function stopContainer(containerId) {
    try {
        const response = await fetch(`${API_BASE}/containers/${containerId}/stop`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            alert(`Container ${containerId} stopped successfully`);
            if (currentView === 'containers' || currentView === 'dashboard') {
                loadContainers();
            }
        } else {
            const error = await response.json();
            alert(`Error stopping container: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error stopping container:', error);
        alert('Error stopping container');
    }
}

async function restartContainer(containerId) {
    try {
        const response = await fetch(`${API_BASE}/containers/${containerId}/restart`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            alert(`Container ${containerId} restarted successfully`);
            if (currentView === 'containers' || currentView === 'dashboard') {
                loadContainers();
            }
        } else {
            const error = await response.json();
            alert(`Error restarting container: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error restarting container:', error);
        alert('Error restarting container');
    }
}

async function deleteContainer(containerId) {
    if (!confirm(`Are you sure you want to delete container ${containerId}? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/containers/${containerId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            alert(`Container ${containerId} deleted successfully`);
            if (currentView === 'containers' || currentView === 'dashboard') {
                loadContainers();
            }
        } else {
            const error = await response.json();
            alert(`Error deleting container: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting container:', error);
        alert('Error deleting container');
    }
}

// Logs functions
async function showContainerLogs(containerId) {
    try {
        // First get recent logs
        const response = await fetch(`${API_BASE}/containers/${containerId}/logs`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const logData = await response.json();
            let logsHtml = '';
            
            if (Array.isArray(logData.logs)) {
                logData.logs.forEach(log => {
                    logsHtml += `<div>${log}</div>`;
                });
            } else {
                logsHtml = '<div>No logs available</div>';
            }
            
            document.getElementById('logsContent').innerHTML = logsHtml;
            
            // Scroll to bottom
            const logsContainer = document.getElementById('logsContent');
            logsContainer.scrollTop = logsContainer.scrollHeight;
            
            // Create modal
            const logsModal = new bootstrap.Modal(document.getElementById('logsModal'));
            logsModal.show();
            
            // Then try to connect WebSocket for real-time logs
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/containers/${containerId}/logs`;
            
            if (logWebSocket) {
                logWebSocket.close();
            }
            
            logWebSocket = new WebSocket(wsUrl);
            
            logWebSocket.onmessage = function(event) {
                const logsContainer = document.getElementById('logsContent');
                logsContainer.innerHTML += `<div>${event.data}</div>`;
                logsContainer.scrollTop = logsContainer.scrollHeight;
            };
            
            logWebSocket.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
            
            logWebSocket.onclose = function() {
                console.log('WebSocket connection closed');
            };
        } else {
            const error = await response.json();
            alert(`Error getting logs: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error showing logs:', error);
        document.getElementById('logsContent').innerHTML = `Error loading logs: ${error.message}`;
        const logsModal = new bootstrap.Modal(document.getElementById('logsModal'));
        logsModal.show();
    }
}

// Container details function
async function showContainerDetails(containerId) {
    try {
        const response = await fetch(`${API_BASE}/containers/${containerId}/status`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const statusData = await response.json();
            
            // Show in a modal
            const detailsHtml = `
                <h5>Container: ${statusData.container_id}</h5>
                <p><strong>Status:</strong> ${statusData.status["State"] || 'N/A'}</p>
                <p><strong>Network:</strong> ${statusData.network_info}</p>
                <hr>
                <h6>Full Status:</h6>
                <pre>${statusData.raw_status}</pre>
            `;
            
            document.getElementById('logsContent').innerHTML = detailsHtml;
            document.getElementById('logsModalLabel').textContent = 'Container Details';
            
            const logsModal = new bootstrap.Modal(document.getElementById('logsModal'));
            logsModal.show();
        } else {
            const error = await response.json();
            alert(`Error getting container details: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error showing container details:', error);
        alert('Error showing container details');
    }
}

// Network functions
async function loadNetworkInfo() {
    try {
        // Load basic bridge status
        const bridgeResponse = await fetch(`${API_BASE}/network/bridge-status`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (bridgeResponse.ok) {
            const bridgeInfo = await bridgeResponse.json();
            
            // Update bridge status
            document.getElementById('networkStatus').className = 'badge';
            if (bridgeInfo.status === 'up') {
                document.getElementById('networkStatus').classList.add('bg-success');
                document.getElementById('networkStatus').textContent = 'UP';
            } else {
                document.getElementById('networkStatus').classList.add('bg-danger');
                document.getElementById('networkStatus').textContent = 'DOWN';
            }
            
            document.getElementById('bridgeName').textContent = bridgeInfo.bridge_name;
            
            if (bridgeInfo.interfaces) {
                document.getElementById('bridgeDetails').innerHTML = `<pre>${bridgeInfo.interfaces}</pre>`;
            } else {
                document.getElementById('bridgeDetails').textContent = 'No bridge information available';
            }
        }
        
        // Load IPv6 status
        const ipv6Response = await fetch(`${API_BASE}/network/ipv6-status`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (ipv6Response.ok) {
            const ipv6Info = await ipv6Response.json();
            
            // Update IPv6 info display (create element if needed)
            let ipv6Element = document.getElementById('ipv6Info');
            if (!ipv6Element) {
                // Create IPv6 info section if it doesn't exist
                const container = document.querySelector('#networkView .card-body');
                const ipv6Div = document.createElement('div');
                ipv6Div.id = 'ipv6Info';
                ipv6Div.innerHTML = `
                    <h5 class="mt-4">IPv6 Status</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <p>IPv6 Forwarding: <span id="ipv6Forwarding" class="badge bg-secondary">Unknown</span></p>
                        </div>
                        <div class="col-md-6">
                            <p>IPv6 Connectivity: <span id="ipv6Connectivity" class="badge bg-secondary">Unknown</span></p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-12">
                            <p>Tunnels: <span id="tunnelsList">None</span></p>
                        </div>
                    </div>
                `;
                container.appendChild(ipv6Div);
            }
            
            // Update IPv6 forwarding status
            const forwardingElement = document.getElementById('ipv6Forwarding');
            forwardingElement.className = 'badge';
            if (ipv6Info.ipv6_forwarding) {
                forwardingElement.classList.add('bg-success');
                forwardingElement.textContent = 'Enabled';
            } else {
                forwardingElement.classList.add('bg-warning');
                forwardingElement.textContent = 'Disabled';
            }
            
            // Update IPv6 connectivity status
            const connectivityElement = document.getElementById('ipv6Connectivity');
            connectivityElement.className = 'badge';
            if (ipv6Info.has_ipv6_connectivity) {
                connectivityElement.classList.add('bg-success');
                connectivityElement.textContent = 'Available';
            } else {
                connectivityElement.classList.add('bg-danger');
                connectivityElement.textContent = 'Unavailable';
            }
            
            // Update tunnels list
            document.getElementById('tunnelsList').textContent = ipv6Info.tunnels.length > 0 ? 
                ipv6Info.tunnels.join(', ') : 'None configured';
        }
        
        // Load assigned IPs
        const ipsResponse = await fetch(`${API_BASE}/network/assigned-ips`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (ipsResponse.ok) {
            const ipsInfo = await ipsResponse.json();
            renderNetworkInfo(ipsInfo.container_ips);
        }
    } catch (error) {
        console.error('Error loading network info:', error);
    }
}

function renderNetworkInfo(containerIps) {
    const networkList = document.getElementById('networkList');
    networkList.innerHTML = '';
    
    if (containerIps && containerIps.length > 0) {
        containerIps.forEach(ipInfo => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${ipInfo.container_name}</td>
                <td>${ipInfo.ip_address || 'N/A'}</td>
                <td>N/A</td>
            `;
            networkList.appendChild(row);
        });
    } else {
        networkList.innerHTML = `
            <tr>
                <td colspan="3">No containers with assigned IP addresses found</td>
            </tr>
        `;
    }
}

// System functions
async function loadSystemInfo() {
    try {
        const response = await fetch(`${API_BASE}/system/resources`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const systemData = await response.json();
            
            document.getElementById('systemMemory').textContent = systemData.memory.split('\n')[0]; // First line of memory info
            document.getElementById('systemDisk').innerHTML = `<pre>${systemData.disk_usage}</pre>`;
            document.getElementById('systemLoad').textContent = `Load: ${systemData.load_average}`;
            
            // Update timestamp
            const date = new Date(systemData.timestamp);
            document.getElementById('systemTimestamp').textContent = date.toLocaleString();
        } else {
            document.getElementById('systemMemory').textContent = 'Error loading system information';
        }
    } catch (error) {
        console.error('Error loading system info:', error);
        document.getElementById('systemMemory').textContent = 'Error loading system information';
    }
}

// Monitoring functions
async function loadMonitoringOverview() {
    try {
        const response = await fetch(`${API_BASE}/monitoring/overview`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const monitoringData = await response.json();
            
            // Update the system view with monitoring data
            document.getElementById('systemMemory').innerHTML = `
                <h6>System Overview</h6>
                <div class="row">
                    <div class="col-md-3">
                        <div class="card text-center bg-light">
                            <div class="card-body">
                                <h5 class="card-title">Total Containers</h5>
                                <h3>${monitoringData.overview.total_containers}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center bg-success text-white">
                            <div class="card-body">
                                <h5 class="card-title">Running</h5>
                                <h3>${monitoringData.overview.running_containers}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center bg-warning text-dark">
                            <div class="card-body">
                                <h5 class="card-title">Stopped</h5>
                                <h3>${monitoringData.overview.stopped_containers}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center bg-info text-white">
                            <div class="card-body">
                                <h5 class="card-title">Load Avg</h5>
                                <h3>${monitoringData.system.load_average['1min']}</h3>
                            </div>
                        </div>
                    </div>
                </div>
                
                <h6 class="mt-4">Resource Usage</h6>
                <div class="row">
                    <div class="col-md-6">
                        <div class="progress mb-2">
                            <div class="progress-bar progress-bar-striped" role="progressbar" 
                                 style="width: ${monitoringData.system.memory_usage_percent}%;" 
                                 aria-valuenow="${monitoringData.system.memory_usage_percent}" 
                                 aria-valuemin="0" aria-valuemax="100">
                                Memory: ${monitoringData.system.memory_usage_percent}%
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="progress mb-2">
                            <div class="progress-bar progress-bar-striped bg-warning" role="progressbar" 
                                 style="width: ${monitoringData.system.disk_usage_percent}%;" 
                                 aria-valuenow="${monitoringData.system.disk_usage_percent}" 
                                 aria-valuemin="0" aria-valuemax="100">
                                Disk: ${monitoringData.system.disk_usage_percent}%
                            </div>
                        </div>
                    </div>
                </div>
                
                <h6 class="mt-4">Container List</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Container</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${monitoringData.containers.map(container => 
                                `<tr>
                                    <td>${container.name}</td>
                                    <td><span class="badge bg-${container.state === 'running' ? 'success' : 'secondary'}">${container.state}</span></td>
                                </tr>`
                            ).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            
            document.getElementById('systemDisk').innerHTML = '';
            document.getElementById('systemLoad').textContent = `Last updated: ${new Date(monitoringData.system.timestamp).toLocaleString()}`;
        } else {
            document.getElementById('systemMemory').textContent = 'Error loading monitoring information';
        }
    } catch (error) {
        console.error('Error loading monitoring info:', error);
        document.getElementById('systemMemory').textContent = 'Error loading monitoring information';
    }
}

// System stats functions
async function fetchSystemStats() {
    try {
        const response = await fetch(`${API_BASE}/system/info`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const systemInfo = await response.json();
            
            // In a real implementation, this would get actual counts
            // For now, let's fetch containers to get counts
            const containers = await fetchContainers();
            let running = 0;
            let stopped = 0;
            
            containers.forEach(c => {
                if (c.state === 'running') running++;
                else stopped++;
            });
            
            return {
                total: containers.length,
                running: running,
                stopped: stopped,
                load: systemInfo.load_average || '0%'
            };
        }
    } catch (error) {
        console.error('Error fetching system stats:', error);
        return {
            total: 0,
            running: 0,
            stopped: 0,
            load: '0%'
        };
    }
}

// Refresh functions
function refreshContainers() {
    if (currentView === 'dashboard') {
        loadDashboard();
    } else if (currentView === 'containers') {
        loadContainers();
    } else if (currentView === 'network') {
        loadNetworkInfo();
    } else if (currentView === 'system') {
        loadSystemInfo();
    }
}

// Cleanup WebSocket when changing views
window.addEventListener('beforeunload', function() {
    if (logWebSocket) {
        logWebSocket.close();
    }
});
EOF

    # Create CSS directory and file
    mkdir -p "$INSTALL_DIR/frontend/css"
    cat > "$INSTALL_DIR/frontend/css/style.css" << 'EOF'
body {
    background-color: #f8f9fa;
}

.card {
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    border: 1px solid rgba(0, 0, 0, 0.125);
}

.navbar-brand {
    font-weight: bold;
}

.status-badge {
    font-size: 0.8em;
}

.logs-container {
    background-color: #000;
    color: #00ff00;
    padding: 10px;
    border-radius: 5px;
    font-family: 'Courier New', monospace;
    height: 300px;
    overflow-y: auto;
}

.table th {
    border-top: none;
}

.table td, .table th {
    vertical-align: middle;
}
EOF

    # Set ownership
    chown -R nspawn-manager:nspawn-manager "$INSTALL_DIR/frontend"
}

# Create systemd service file
create_systemd_service() {
    log_info "Creating systemd service..."

    # Create the nspawn-manager service
    cat > "$SYSTEMD_SERVICE_DIR/nspawn-manager.service" << EOF
[Unit]
Description=nspawn-vps Container Management Platform
After=network.target nspawn-bridge.service
Wants=network.target
Documentation=https://github.com/your-repo/nspawn-vps

[Service]
Type=simple
User=nspawn-manager
Group=nspawn-manager
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
Environment=SECRET_KEY=$(openssl rand -base64 32)
Environment=ADMIN_PASSWORD=admin123
ExecStart=$INSTALL_DIR/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080 --log-level info
Restart=always
RestartSec=5

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR $MACHINES_DIR $CONFIG_DIR $LOG_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Create the network bridge service
    cat > "$SYSTEMD_SERVICE_DIR/nspawn-bridge.service" << EOF
[Unit]
Description=Network Bridge for nspawn-vps
After=network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes

# Create the bridge
ExecStart=/bin/bash -c 'ip link add br0 type bridge && ip link set br0 up'

# Enable IP forwarding
ExecStart=/bin/bash -c 'echo 1 > /proc/sys/net/ipv4/ip_forward && echo 1 > /proc/sys/net/ipv6/conf/all/forwarding'

# Enable NAT
ExecStart=/bin/bash -c 'DEFAULT_IFACE=$(ip route show default | awk '\''{for (i=1; i<=NF; i++) if ($i == "dev") {print $(i+1); exit}}'\''); if [[ -z "$DEFAULT_IFACE" ]]; then echo "No default interface found; skipping NAT configuration" >&2; exit 0; fi; iptables -t nat -A POSTROUTING -o "$DEFAULT_IFACE" -j MASQUERADE && iptables -A FORWARD -i br0 -o "$DEFAULT_IFACE" -j ACCEPT && iptables -A FORWARD -i "$DEFAULT_IFACE" -o br0 -j ACCEPT'

# Save iptables rules
ExecStart=/bin/bash -c 'iptables-save > /etc/iptables/rules.v4 2>/dev/null || true'

ExecStop=/bin/bash -c 'DEFAULT_IFACE=$(ip route show default | awk '\''{for (i=1; i<=NF; i++) if ($i == "dev") {print $(i+1); exit}}'\''); iptables -t nat -D POSTROUTING -o "$DEFAULT_IFACE" -j MASQUERADE 2>/dev/null || true && iptables -D FORWARD -i br0 -o "$DEFAULT_IFACE" -j ACCEPT 2>/dev/null || true && iptables -D FORWARD -i "$DEFAULT_IFACE" -o br0 -j ACCEPT 2>/dev/null || true && ip link set br0 down 2>/dev/null || true && ip link delete br0 2>/dev/null || true'

[Install]
WantedBy=network.target
EOF

    # Reload systemd daemon
    systemctl daemon-reload
    systemctl enable nspawn-bridge.service
}

# Setup completed message
show_completion_message() {
    log_info "Installation completed successfully!"

    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                           nspawn-vps Installation Complete                    ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║                                                                              ║${NC}"
    echo -e "${GREEN}║  Access the WebUI at:                                                      ║${NC}"
    IPV4_ADDR=$(hostname -I | awk '{print $1}')
    echo -e "${GREEN}║    IPv4: http://$IPV4_ADDR:8080                                          ║${NC}"
    if [[ -n "${IPV6_ADDR:-}" ]]; then
        echo -e "${GREEN}║    IPv6: http://[$(echo $IPV6_ADDR | cut -d'/' -f1)]:8080                ║${NC}"
    fi
    echo -e "${GREEN}║                                                                              ║${NC}"
    echo -e "${GREEN}║  Default login:                                                             ║${NC}"
    echo -e "${GREEN}║    Username: admin                                                          ║${NC}"
    echo -e "${GREEN}║    Password: admin123                                                       ║${NC}"
    echo -e "${GREEN}║                                                                              ║${NC}"
    echo -e "${GREEN}║  Start the service:                                                         ║${NC}"
    echo -e "${GREEN}║    sudo systemctl start nspawn-manager                                      ║${NC}"
    echo -e "${GREEN}║                                                                              ║${NC}"
    echo -e "${GREEN}║  Enable auto-start on boot:                                                 ║${NC}"
    echo -e "${GREEN}║    sudo systemctl enable nspawn-manager                                     ║${NC}"
    echo -e "${GREEN}║                                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo
}

# Main installation function
main() {
    log_info "Starting nspawn-vps installation..."
    
    check_root
    check_prerequisites
    install_dependencies
    create_system_user
    create_directories
    interactive_networking
    configure_networking
    deploy_backend
    deploy_frontend
    create_systemd_service
    
    # Enable and start services
    systemctl enable nspawn-bridge.service
    systemctl start nspawn-bridge.service
    systemctl enable nspawn-manager.service
    systemctl start nspawn-manager.service
    
    show_completion_message
    
    log_info "Installation finished. Service is now running."
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi