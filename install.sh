#!/bin/bash
#
# ZenithStack Installer Script
# Self-Hosted Container Management Platform using systemd-nspawn
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="/var/log/zenithstack-install.log"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root. Please use sudo."
    fi
}

# Detect OS and architecture
detect_system() {
    log "Detecting system information..."
    
    # Detect OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        error "Unable to detect operating system"
    fi
    
    # Detect architecture
    ARCH=$(uname -m)
    
    info "Operating System: $OS $OS_VERSION"
    info "Architecture: $ARCH"
    
    # Check if systemd is available
    if ! command -v systemctl &> /dev/null; then
        error "systemd is not available on this system"
    fi
    
    # Check systemd version
    SYSTEMD_VERSION=$(systemctl --version | head -n1 | awk '{print $2}')
    if [ "$SYSTEMD_VERSION" -lt 239 ]; then
        warn "systemd version $SYSTEMD_VERSION is below recommended version 239"
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y \
                systemd-container \
                debootstrap \
                bridge-utils \
                iproute2 \
                iptables \
                python3 \
                python3-pip \
                python3-venv \
                dnsmasq \
                git \
                curl \
                wget
            ;;
        fedora|centos|rhel)
            dnf install -y \
                systemd-container \
                debootstrap \
                bridge-utils \
                iproute \
                iptables \
                python3 \
                python3-pip \
                dnsmasq \
                git \
                curl \
                wget
            ;;
        arch)
            pacman -Sy --noconfirm \
                systemd \
                arch-install-scripts \
                bridge-utils \
                iproute2 \
                iptables \
                python \
                python-pip \
                dnsmasq \
                git \
                curl \
                wget
            ;;
        *)
            warn "Unsupported OS: $OS. Attempting generic installation..."
            ;;
    esac
    
    log "Dependencies installed successfully"
}

# Setup application directories
setup_directories() {
    log "Creating application directories..."
    
    mkdir -p /opt/zenithstack/{backend,frontend}
    mkdir -p /var/lib/zenithstack
    mkdir -p /var/log/zenithstack
    mkdir -p /etc/zenithstack
    mkdir -p /var/lib/machines
    mkdir -p /etc/systemd/nspawn
    
    log "Directories created successfully"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    cd /opt/zenithstack/backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    
    log "Python dependencies installed successfully"
}

# Configure networking
configure_network() {
    log "Configuring network..."
    
    # Prompt for network configuration
    echo ""
    info "Network Configuration"
    echo "========================================"
    
    # Check for IPv6 connectivity
    if ping6 -c 1 google.com &> /dev/null; then
        info "Native IPv6 connectivity detected"
        read -p "Use native IPv6 for containers? (y/n): " USE_IPV6
    else
        warn "No native IPv6 connectivity detected"
        USE_IPV6="n"
    fi
    
    # Configure IPv6 if needed
    if [ "$USE_IPV6" != "y" ]; then
        read -p "Configure 6in4 tunnel? (y/n): " USE_6IN4
        if [ "$USE_6IN4" = "y" ]; then
            read -p "Tunnel server IPv4 address: " TUNNEL_SERVER
            read -p "Tunnel client IPv6 address: " TUNNEL_CLIENT
            read -p "Routed IPv6 prefix: " IPV6_PREFIX
            
            # Create sit tunnel configuration
            cat > /etc/systemd/network/sit0.netdev <<EOF
[NetDev]
Name=sit0
Kind=sit

[Tunnel]
Local=$TUNNEL_SERVER
Remote=$TUNNEL_CLIENT
EOF
            
            cat > /etc/systemd/network/sit0.network <<EOF
[Match]
Name=sit0

[Network]
Address=$IPV6_PREFIX
EOF
        else
            read -p "Configure WireGuard tunnel? (y/n): " USE_WG
            if [ "$USE_WG" = "y" ]; then
                if ! command -v wg &> /dev/null; then
                    info "Installing WireGuard..."
                    case $OS in
                        ubuntu|debian)
                            apt-get install -y wireguard
                            ;;
                        fedora|centos|rhel)
                            dnf install -y wireguard-tools
                            ;;
                        arch)
                            pacman -S --noconfirm wireguard-tools
                            ;;
                    esac
                fi
                
                info "WireGuard configuration needs to be done manually"
                info "Place your WireGuard config in /etc/wireguard/wg0.conf"
            fi
        fi
    fi
    
    # Enable IP forwarding
    log "Enabling IP forwarding..."
    cat >> /etc/sysctl.conf <<EOF

# ZenithStack IP forwarding
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF
    sysctl -p
    
    # Configure iptables for NAT
    log "Configuring NAT..."
    iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o $(ip route | grep default | awk '{print $5}') -j MASQUERADE
    
    # Save iptables rules
    case $OS in
        ubuntu|debian)
            apt-get install -y iptables-persistent
            netfilter-persistent save
            ;;
        fedora|centos|rhel)
            service iptables save
            ;;
    esac
    
    log "Network configuration completed"
}

# Create systemd service
create_service() {
    log "Creating systemd service..."
    
    cat > /etc/systemd/system/zenithstack.service <<EOF
[Unit]
Description=ZenithStack Container Management Platform
After=network.target systemd-networkd.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/zenithstack/backend
Environment="ZENITH_HOST=0.0.0.0"
Environment="ZENITH_PORT=8080"
ExecStart=/opt/zenithstack/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable zenithstack.service
    
    log "Systemd service created"
}

# Setup admin credentials
setup_admin() {
    log "Setting up admin credentials..."
    
    read -p "Enter admin username [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    read -s -p "Enter admin password: " ADMIN_PASS
    echo ""
    read -s -p "Confirm admin password: " ADMIN_PASS_CONFIRM
    echo ""
    
    if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
        error "Passwords do not match"
    fi
    
    # Store credentials (in production, this should be hashed)
    cat > /etc/zenithstack/admin.conf <<EOF
ADMIN_USERNAME=$ADMIN_USER
ADMIN_PASSWORD=$ADMIN_PASS
EOF
    chmod 600 /etc/zenithstack/admin.conf
    
    log "Admin credentials configured"
}

# Start the service
start_service() {
    log "Starting ZenithStack service..."
    
    systemctl start zenithstack.service
    
    # Wait for service to start
    sleep 3
    
    if systemctl is-active --quiet zenithstack.service; then
        log "Service started successfully"
    else
        error "Service failed to start. Check logs with: journalctl -u zenithstack.service"
    fi
}

# Display completion message
show_completion() {
    clear
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}║   ${BLUE}ZenithStack Installation Complete!${GREEN}                ║${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Get IP addresses
    IPV4=$(ip -4 addr show | grep inet | grep -v 127.0.0.1 | head -n1 | awk '{print $2}' | cut -d/ -f1)
    IPV6=$(ip -6 addr show | grep inet6 | grep -v ::1 | grep -v fe80 | head -n1 | awk '{print $2}' | cut -d/ -f1)
    
    info "Access the WebUI at:"
    echo "  - IPv4: http://$IPV4:8080"
    if [ -n "$IPV6" ]; then
        echo "  - IPv6: http://[$IPV6]:8080"
    fi
    echo ""
    info "Default credentials:"
    echo "  - Username: admin"
    echo "  - Password: admin"
    echo ""
    warn "IMPORTANT: Change the default password immediately!"
    echo ""
    info "Useful commands:"
    echo "  - Check status:  systemctl status zenithstack"
    echo "  - View logs:     journalctl -u zenithstack -f"
    echo "  - Restart:       systemctl restart zenithstack"
    echo ""
    info "Log file: $LOG_FILE"
    echo ""
}

# Main installation flow
main() {
    clear
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║              ZenithStack Installer                     ║"
    echo "║   Self-Hosted Container Management Platform            ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    
    check_root
    detect_system
    
    read -p "Continue with installation? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        info "Installation cancelled"
        exit 0
    fi
    
    install_dependencies
    setup_directories
    
    # Copy application files
    log "Copying application files..."
    if [ -d "$(dirname $0)/backend" ]; then
        cp -r "$(dirname $0)/backend"/* /opt/zenithstack/backend/
        cp -r "$(dirname $0)/frontend"/* /opt/zenithstack/frontend/
    else
        warn "Application files not found in script directory"
        warn "Please manually copy files to /opt/zenithstack/"
    fi
    
    install_python_deps
    configure_network
    create_service
    setup_admin
    start_service
    show_completion
}

# Run main installation
main "$@"
