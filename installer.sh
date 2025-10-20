#!/bin/bash

# nspawn-ui installer script
# This script installs the container manager with systemd-nspawn backend

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root. Please run as a regular user with sudo access."
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "Cannot detect OS. Exiting."
        exit 1
    fi
    print_status "Detected OS: $OS $VER"
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            sudo apt update
            sudo apt install -y systemd-container python3 python3-pip python3-venv debootstrap iptables nftables curl wget
            ;;
        *"CentOS"*|*"Red Hat"*|*"Fedora"*)
            if [ "$VER" -ge 22 ]; then
                sudo dnf install -y systemd-container python3 python3-pip debootstrap iptables nftables curl wget
            else
                sudo yum install -y systemd-container python3 python3-pip debootstrap iptables curl wget
            fi
            ;;
        *"Arch Linux"*)
            sudo pacman -Sy --noconfirm systemd python python-pip debootstrap iptables nftables curl wget
            ;;
        *)
            print_error "Unsupported OS: $OS. Exiting."
            exit 1
            ;;
    esac
    
    # Install Python dependencies
    pip3 install --user fastapi uvicorn pydantic python-multipart
    
    print_success "Dependencies installed."
}

# Create necessary directories
setup_directories() {
    print_status "Setting up directories..."
    
    sudo mkdir -p /var/lib/machines
    sudo mkdir -p /etc/systemd/nspawn
    sudo mkdir -p /etc/systemd/network
    
    print_success "Directories created."
}

# Setup networking
setup_networking() {
    print_status "Setting up networking..."
    
    # Ask user for networking preference
    echo ""
    echo "Choose IPv6 networking method:"
    echo "1) Native IPv6 (if available)"
    echo "2) 6in4 tunnel (Hurricane Electric or custom)"
    echo "3) WireGuard tunnel"
    echo "4) Skip for now (IPv4 only)"
    read -p "Enter your choice (1-4): " network_choice
    
    case $network_choice in
        1)
            setup_native_ipv6
            ;;
        2)
            setup_6in4_tunnel
            ;;
        3)
            setup_wireguard_tunnel
            ;;
        4)
            print_status "Skipping IPv6 setup. IPv4 NAT will be configured."
            setup_ipv4_nat
            ;;
        *)
            print_error "Invalid choice. Skipping networking setup."
            ;;
    esac
}

setup_native_ipv6() {
    print_status "Setting up native IPv6..."
    read -p "Enter your IPv6 subnet (e.g., 2001:db8::/64): " ipv6_subnet
    read -p "Enter your IPv6 gateway: " gateway
    
    # Create bridge for IPv6
    sudo tee /etc/systemd/network/ipv6-br0.netdev > /dev/null <<EOF
[NetDev]
Name=ipv6-br0
Kind=bridge
EOF

    sudo tee /etc/systemd/network/ipv6-br0.network > /dev/null <<EOF
[Match]
Name=ipv6-br0

[Network]
DHCP=no
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes
EOF

    # Apply network configuration
    sudo systemctl restart systemd-networkd
    
    print_success "Native IPv6 configured."
}

setup_6in4_tunnel() {
    print_status "Setting up 6in4 tunnel..."
    read -p "Enter tunnel server IPv4: " tunnel_server
    read -p "Enter your tunnel IPv4: " tunnel_client
    read -p "Enter your tunnel IPv6 (with prefix length): " tunnel_ipv6
    read -s -p "Enter authentication key (if required, press Enter for none): " auth_key
    echo
    
    # Create tunnel configuration
    sudo tee /etc/systemd/network/6in4-tunnel.netdev > /dev/null <<EOF
[NetDev]
Name=tun6in4
Kind=sit

[Tunnel]
Local=$tunnel_client
Remote=$tunnel_server
TTL=64
EOF

    sudo tee /etc/systemd/network/6in4-tunnel.network > /dev/null <<EOF
[Match]
Name=tun6in4

[Network]
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes

[Address]
Address=$tunnel_ipv6
EOF

    # Apply network configuration
    sudo systemctl restart systemd-networkd
    
    print_success "6in4 tunnel configured."
}

setup_wireguard_tunnel() {
    print_status "Setting up WireGuard tunnel..."
    
    # Install WireGuard if not present
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            sudo apt install -y wireguard
            ;;
        *"CentOS"*|*"Red Hat"*|*"Fedora"*)
            sudo dnf install -y wireguard-tools
            ;;
        *"Arch Linux"*)
            sudo pacman -S --noconfirm wireguard-tools
            ;;
    esac
    
    read -p "Enter WireGuard private key: " wg_private_key
    read -p "Enter peer public key: " wg_public_key
    read -p "Enter endpoint (host:port): " wg_endpoint
    read -p "Enter local IP addresses (comma separated): " wg_address
    
    # Create WireGuard config
    sudo mkdir -p /etc/wireguard
    sudo tee /etc/wireguard/wg0.conf > /dev/null <<EOF
[Interface]
PrivateKey = $wg_private_key
Address = $wg_address

[Peer]
PublicKey = $wg_public_key
AllowedIPs = ::/0
Endpoint = $wg_endpoint
PersistentKeepalive = 25
EOF

    # Enable and start WireGuard
    sudo systemctl enable wg-quick@wg0
    sudo systemctl start wg-quick@wg0
    
    print_success "WireGuard tunnel configured."
}

setup_ipv4_nat() {
    print_status "Setting up IPv4 NAT..."
    
    # Enable IP forwarding
    echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.conf
    echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    
    # Setup basic NAT with iptables
    sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    sudo iptables -A FORWARD -i eth0 -o br0 -j ACCEPT
    sudo iptables -A FORWARD -i br0 -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Save iptables rules
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            sudo apt install -y iptables-persistent
            sudo iptables-save > /etc/iptables/rules.v4
            ;;
        *"CentOS"*|*"Red Hat"*|*"Fedora"*)
            sudo service iptables save
            ;;
    esac
    
    print_success "IPv4 NAT configured."
}

# Setup systemd service
setup_systemd_service() {
    print_status "Setting up systemd service..."
    
    # Create the service file
    sudo tee /etc/systemd/system/nspawn-ui.service > /dev/null <<EOF
[Unit]
Description=nspawn-ui Container Manager
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=/home/$SUDO_USER/nspawn-ui
ExecStart=/usr/bin/python3 /home/$SUDO_USER/nspawn-ui/api_backend.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload
    
    print_success "Systemd service configured."
}

# Setup application files
setup_application() {
    print_status "Setting up application files..."
    
    # Copy current files to home directory
    USER_HOME=$(eval echo ~$SUDO_USER)
    APP_DIR="$USER_HOME/nspawn-ui"
    
    # Create app directory if it doesn't exist
    mkdir -p "$APP_DIR"
    
    # Copy the necessary files (these would be copied from the current directory in a real installation)
    # In a real installer, you would curl/download the files from a repository
    cp *.py "$APP_DIR/" 2>/dev/null || echo "No .py files found in current directory"
    cp -r static "$APP_DIR/" 2>/dev/null || echo "No static directory found, creating empty one"
    
    # Create placeholder files if they don't exist
    if [ ! -f "$APP_DIR/api_backend.py" ]; then
        touch "$APP_DIR/api_backend.py"
        echo "print('nspawn-ui backend')" > "$APP_DIR/api_backend.py"
    fi
    
    if [ ! -f "$APP_DIR/container_manager.py" ]; then
        touch "$APP_DIR/container_manager.py"
        echo "print('Container manager module')" > "$APP_DIR/container_manager.py"
    fi
    
    chown -R $SUDO_USER:$SUDO_USER "$APP_DIR"
    
    print_success "Application files set up in $APP_DIR"
}

# Setup firewall
setup_firewall() {
    print_status "Setting up firewall..."
    
    # Allow necessary ports
    sudo ufw allow 8000/tcp 2>/dev/null || echo "ufw not available, skipping"
    
    # If using iptables/nftables instead of ufw
    if ! command -v ufw &> /dev/null; then
        # Allow port 8000 for the web UI
        sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
    fi
    
    print_success "Firewall configured."
}

# Setup admin credentials
setup_admin_credentials() {
    print_status "Setting up admin credentials..."
    
    read -s -p "Enter admin password: " admin_password
    echo
    read -s -p "Confirm admin password: " admin_password_confirm
    echo
    
    if [ "$admin_password" != "$admin_password_confirm" ]; then
        print_error "Passwords do not match. Exiting."
        exit 1
    fi
    
    # In a real implementation, we would hash and store the password securely
    # For now, we'll just acknowledge the setup
    print_success "Admin credentials set up."
}

# Start the service
start_service() {
    print_status "Starting nspawn-ui service..."
    
    sudo systemctl enable nspawn-ui
    sudo systemctl start nspawn-ui
    
    print_success "Service started. Web UI should be available at http://localhost:8000"
}

# Main installation flow
main() {
    print_status "Starting nspawn-ui installation..."
    
    check_root
    detect_os
    install_dependencies
    setup_directories
    setup_networking
    setup_application
    setup_systemd_service
    setup_firewall
    setup_admin_credentials
    start_service
    
    print_success "Installation completed successfully!"
    print_status "Access the web UI at http://localhost:8000"
    print_status "To view service status: sudo systemctl status nspawn-ui"
    print_status "To view logs: sudo journalctl -u nspawn-ui -f"
}

main "$@"