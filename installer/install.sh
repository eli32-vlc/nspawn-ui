#!/bin/bash

# nspawn-ui installer script
# This script installs nspawn-ui on a Linux system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DIR="/opt/nspawn-ui"
SYSTEMD_SERVICE_DIR="/etc/systemd/system"
USER="nspawn-ui"
MACHINES_DIR="/var/lib/machines"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Function to detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$NAME
        DISTRO_VERSION=$VERSION_ID
    else
        print_error "Cannot detect Linux distribution"
        exit 1
    fi
}

# Function to install dependencies based on distribution
install_dependencies() {
    print_status "Installing dependencies..."
    
    case $DISTRO in
        *"Ubuntu"*|*"Debian"*)
            apt update
            apt install -y systemd-container python3 python3-pip debootstrap machinectl iptables jq curl
            ;;
        *"CentOS"*|*"Red Hat"*|*"AlmaLinux"*|*"Rocky Linux"*|*"Fedora"*)
            if command -v dnf &> /dev/null; then
                dnf install -y systemd-container python3 python3-pip debootstrap iptables jq curl
            elif command -v yum &> /dev/null; then
                yum install -y systemd-container python3 python3-pip debootstrap iptables jq curl
            fi
            ;;
        *"Arch Linux"*)
            pacman -Sy --noconfirm systemd-container python python-pip debootstrap arch-install-scripts jq curl
            ;;
        *)
            print_error "Unsupported distribution: $DISTRO"
            exit 1
            ;;
    esac
}

# Function to create user
create_user() {
    print_status "Creating user: $USER"
    
    if ! id "$USER" &>/dev/null; then
        useradd -r -s /bin/bash -d "$INSTALL_DIR" "$USER"
    fi
}

# Function to create install directory
create_install_dir() {
    print_status "Creating installation directory: $INSTALL_DIR"
    
    mkdir -p "$INSTALL_DIR"
    chown "$USER:$USER" "$INSTALL_DIR"
}

# Function to create machines directory
setup_machines_dir() {
    print_status "Setting up machines directory: $MACHINES_DIR"
    
    mkdir -p "$MACHINES_DIR"
    chown root: "$MACHINES_DIR"
    chmod 755 "$MACHINES_DIR"
}

# Function to copy application files
copy_files() {
    print_status "Copying application files..."
    
    # Copy the actual application files to the installation directory
    # First, make sure the source files exist in the current directory
    if [ ! -d "./api" ] || [ ! -d "./webui" ]; then
        print_error "Source files not found in current directory. Please run this script from the nspawn-ui root directory."
        exit 1
    fi
    
    # Copy API files
    cp -r api "$INSTALL_DIR/"
    
    # Copy webui files
    cp -r webui "$INSTALL_DIR/"
    
    # Copy requirements
    cp requirements.txt "$INSTALL_DIR/"
    
    # Create config directory
    mkdir -p "$INSTALL_DIR/config"
    
    # Create sample config
    cat > "$INSTALL_DIR/config/config.json" << EOF
{
    "api_host": "0.0.0.0",
    "api_port": 8000,
    "webui_path": "/webui",
    "machines_path": "/var/lib/machines"
}
EOF
    
    chown -R "$USER:$USER" "$INSTALL_DIR"
}

# Function to create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    cat > "$SYSTEMD_SERVICE_DIR/nspawn-ui.service" << EOF
[Unit]
Description=nspawn-ui API Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR $INSTALL_DIR/api $INSTALL_DIR/webui $INSTALL_DIR/config $MACHINES_DIR
AmbientCapabilities=CAP_NET_ADMIN CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
}

# Function to set up networking (dual-stack IPv4/IPv6 with bridge)
setup_networking() {
    print_status "Setting up networking configuration..."
    
    # Create network configuration directory
    mkdir -p /etc/systemd/network
    
    # Create a bridge configuration for containers
    cat > /etc/systemd/network/br0.netdev << EOF
[NetDev]
Name=br0
Kind=bridge
EOF

    # Configure the bridge
    cat > /etc/systemd/network/br0.network << EOF
[Match]
Name=br0

[Network]
DHCP=yes
IPForward=ipv4
EOF

    # Create a network configuration for container interfaces
    cat > /etc/systemd/network/ve-*.network << EOF
[Match]
Name=ve-*

[Network]
Bridge=br0
EOF

    # Create default container network settings
    cat > /etc/systemd/nspawn/bridge.conf << EOF
[Network]
Bridge=br0
EOF

    # Enable systemd-networkd
    systemctl enable systemd-networkd
    systemctl restart systemd-networkd
    
    print_status "Bridge network (br0) created successfully"
}

# Function to check and setup IPv6 (if available)
setup_ipv6() {
    print_status "Checking IPv6 connectivity..."
    
    # Check if IPv6 is already available
    if [[ $(curl -s -6 https://api64.ipify.org 2>/dev/null) ]]; then
        print_status "IPv6 is available on this system"
        read -p "Do you want to set up IPv6 for containers? (y/n): " setup_ipv6
        
        if [[ $setup_ipv6 == "y" || $setup_ipv6 == "Y" ]]; then
            enable_native_ipv6
        else
            print_status "IPv6 setup skipped. Containers will only have IPv4 access."
        fi
    else
        print_warning "IPv6 is not available natively on this system."
        setup_ipv6_tunneling
    fi
}

enable_native_ipv6() {
    print_status "Configuring native IPv6..."
    
    # Update the bridge configuration to enable IPv6 forwarding
    cat > /etc/systemd/network/br0.network << EOF
[Match]
Name=br0

[Network]
DHCP=yes
IPForward=both
EOF

    # Configure IPv6 for containers
    cat > /etc/systemd/network/ve-*.network << EOF
[Match]
Name=ve-*

[Network]
Bridge=br0
IPv6AcceptRA=yes
EOF

    systemctl restart systemd-networkd
}

setup_ipv6_tunneling() {
    print_status "Setting up IPv6 tunneling options..."
    
    print_status "Available IPv6 tunneling methods:"
    print_status "1) Hurricane Electric (HE.net) 6in4 tunnel"
    print_status "2) Custom 6in4 tunnel"
    print_status "3) WireGuard tunnel"
    print_status "4) Skip IPv6 setup"
    
    read -p "Select an option (1-4): " ipv6_option
    
    case $ipv6_option in
        1)
            setup_he_tunnel
            ;;
        2)
            setup_custom_tunnel
            ;;
        3)
            setup_wireguard_tunnel
            ;;
        4)
            print_status "IPv6 setup skipped. Containers will only have IPv4 access."
            ;;
        *)
            print_warning "Invalid option. Skipping IPv6 setup."
            ;;
    esac
}

setup_he_tunnel() {
    print_status "Setting up Hurricane Electric 6in4 tunnel..."
    print_status "Please log in to https://tunnelbroker.net to get your tunnel details"
    print_status "You'll need: Server IPv4, Client IPv4, Client IPv6, and Routed /64"
    
    read -p "Enter your tunnel server IPv4: " tunnel_server_ipv4
    read -p "Enter your tunnel client IPv4: " tunnel_client_ipv4
    read -p "Enter your tunnel client IPv6 (e.g., 2001:db8::2/64): " tunnel_client_ipv6
    read -p "Enter the default IPv6 gateway (e.g., 2001:db8::1): " tunnel_gateway_ipv6
    
    # Extract the prefix from the IPv6 address if it's in CIDR format
    tunnel_prefix=$(echo $tunnel_client_ipv6 | cut -d'/' -f1)
    
    # Create tunnel interface using systemd-networkd
    cat > /etc/systemd/network/tun-he.netdev << EOF
[NetDev]
Name=tun-he
Kind=sit

[SIT]
Remote=$tunnel_server_ipv4
Local=$tunnel_client_ipv4
TTL=255
EOF

    cat > /etc/systemd/network/tun-he.network << EOF
[Match]
Name=tun-he

[Network]
Address=$tunnel_client_ipv6
Gateway=$tunnel_gateway_ipv6
IPForward=both
EOF

    # Update bridge to support IPv6
    cat > /etc/systemd/network/br0.network << EOF
[Match]
Name=br0

[Network]
DHCP=yes
IPForward=both
EOF

    # Configure container interfaces to use IPv6
    cat > /etc/systemd/network/ve-*.network << EOF
[Match]
Name=ve-*

[Network]
Bridge=br0
IPv6AcceptRA=yes
EOF

    # Enable and restart systemd-networkd
    systemctl enable systemd-networkd
    systemctl restart systemd-networkd
    
    print_status "HE tunnel configured. Verify with: ip -6 route show"
}

setup_custom_tunnel() {
    print_status "Setting up custom 6in4 tunnel..."
    
    read -p "Enter tunnel server IPv4: " tunnel_server_ipv4
    read -p "Enter tunnel client IPv4: " tunnel_client_ipv4
    read -p "Enter tunnel client IPv6 (e.g., 2001:db8::2/64): " tunnel_client_ipv6
    read -p "Enter IPv6 gateway (e.g., 2001:db8::1): " tunnel_gateway_ipv6
    
    # Create tunnel interface using systemd-networkd
    cat > /etc/systemd/network/tun-custom.netdev << EOF
[NetDev]
Name=tun-custom
Kind=sit

[SIT]
Remote=$tunnel_server_ipv4
Local=$tunnel_client_ipv4
TTL=255
EOF

    cat > /etc/systemd/network/tun-custom.network << EOF
[Match]
Name=tun-custom

[Network]
Address=$tunnel_client_ipv6
Gateway=$tunnel_gateway_ipv6
IPForward=both
EOF

    # Update bridge to support IPv6
    cat > /etc/systemd/network/br0.network << EOF
[Match]
Name=br0

[Network]
DHCP=yes
IPForward=both
EOF

    # Enable and restart systemd-networkd
    systemctl enable systemd-networkd
    systemctl restart systemd-networkd
}

setup_wireguard_tunnel() {
    print_status "Setting up WireGuard tunnel..."
    
    # Install WireGuard if not already installed
    if command -v apt &> /dev/null; then
        apt update && apt install -y wireguard
    elif command -v dnf &> /dev/null; then
        dnf install -y wireguard-tools
    elif command -v yum &> /dev/null; then
        yum install -y wireguard-tools
    elif command -v pacman &> /dev/null; then
        pacman -S --noconfirm wireguard-tools
    fi
    
    read -p "Enter WireGuard server endpoint (host:port): " wg_endpoint
    read -p "Enter WireGuard server public key: " wg_server_pubkey
    read -p "Enter your WireGuard IPv4 address: " wg_ipv4
    read -p "Enter your WireGuard IPv6 address: " wg_ipv6
    read -p "Enter WireGuard private key: " wg_privkey
    
    # Create WireGuard configuration
    mkdir -p /etc/wireguard
    cat > /etc/wireguard/wg0.conf << EOF
[Interface]
PrivateKey = $wg_privkey
Address = $wg_ipv4/32, $wg_ipv6/128
DNS = 8.8.8.8, 8.8.4.4

[Peer]
PublicKey = $wg_server_pubkey
Endpoint = $wg_endpoint
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
    
    # Make the config file secure
    chmod 600 /etc/wireguard/wg0.conf
    
    # Update bridge to support IPv6 forwarding
    cat > /etc/systemd/network/br0.network << EOF
[Match]
Name=br0

[Network]
DHCP=yes
IPForward=both
EOF

    # Enable and start WireGuard
    systemctl enable wg-quick@wg0
    systemctl start wg-quick@wg0
    
    # Enable IP forwarding
    echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.conf
    sysctl -p
    
    # Set up NAT for WireGuard if needed
    iptables -t nat -A POSTROUTING -o wg0 -j MASQUERADE
    iptables -A FORWARD -i wg0 -j ACCEPT
    iptables -A FORWARD -i br0 -o wg0 -j ACCEPT
    iptables -A FORWARD -i wg0 -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    print_status "WireGuard tunnel configured and started"
}

# Function to set up firewall rules for NAT
setup_firewall() {
    print_status "Setting up firewall rules for NAT..."
    
    # Enable IP forwarding
    echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.conf
    
    # Apply immediately
    sysctl -p
    
    # Set up IPv4 NAT rules using iptables
    # Enable masquerading for outbound traffic
    iptables -t nat -A POSTROUTING -o $(ip route | grep default | awk '{print $5}' | head -n 1) -j MASQUERADE
    iptables -A FORWARD -i br0 -o $(ip route | grep default | awk '{print $5}' | head -n 1) -j ACCEPT
    iptables -A FORWARD -i $(ip route | grep default | awk '{print $5}' | head -n 1) -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Set up IPv6 NAT if IPv6 is configured
    if [[ $(ip -6 route show | grep -c "tun-") -gt 0 ]]; then
        ip6tables -t nat -A POSTROUTING -o tun-+ -j MASQUERADE
        ip6tables -A FORWARD -i br0 -o tun-+ -j ACCEPT
        ip6tables -A FORWARD -i tun-+ -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    fi
    
    # Check if iptables-persistent or iptables-services is available to save rules
    if command -v iptables-save &> /dev/null; then
        # Try to save rules to persist across reboots
        if [ -f /etc/debian_version ]; then
            # For Debian/Ubuntu
            if command -v iptables-persistent &> /dev/null; then
                iptables-save > /etc/iptables/rules.v4
            else
                print_warning "Install iptables-persistent to save rules across reboots: apt install iptables-persistent"
            fi
        elif [ -f /etc/redhat-release ]; then
            # For Red Hat/CentOS/Fedora
            if command -v iptables-service &> /dev/null; then
                service iptables save
            else
                print_warning "Install iptables-service to save rules across reboots: yum install iptables-services"
            fi
        else
            # Generic save attempt
            iptables-save > /tmp/rules.v4
            print_warning "Rules saved to /tmp/rules.v4 - please configure persistence for your system"
        fi
    fi
    
    print_status "Firewall rules configured for container NAT"
}

# Function to create virtual environment and install Python dependencies
setup_python_env() {
    print_status "Installing Python dependencies..."
    
    cd "$INSTALL_DIR"
    pip3 install --user -r requirements.txt
    
    # Verify installation
    if python3 -c "import fastapi, uvicorn, pydantic"; then
        print_status "Python dependencies installed successfully"
    else
        print_error "Failed to install Python dependencies"
        exit 1
    fi
}

# Function to start the service
start_service() {
    print_status "Starting nspawn-ui service..."
    systemctl enable nspawn-ui
    systemctl start nspawn-ui
    
    # Wait a moment for the service to start
    sleep 3
    
    # Check if the service is running
    if systemctl is-active --quiet nspawn-ui; then
        local_ip=$(hostname -I | awk '{print $1}')
        print_status "nspawn-ui service started successfully!"
        print_status "WebUI is available at http://$local_ip:8000"
    else
        print_error "nspawn-ui service failed to start"
        systemctl status nspawn-ui
        journalctl -u nspawn-ui -n 50 --no-pager
        exit 1
    fi
}

# Function to display post-installation instructions
show_post_install_info() {
    print_status "Installation completed successfully!"
    print_status ""
    print_status "Access the WebUI at: http://$(hostname -I | awk '{print $1}'):8000"
    print_status ""
    print_status "Useful commands:"
    print_status "  - Check service status: systemctl status nspawn-ui"
    print_status "  - View service logs: journalctl -u nspawn-ui -f"
    print_status "  - List containers: machinectl list"
    print_status "  - Start a container: machinectl start <container-name>"
    print_status "  - Run nspawn-ui utility: python3 $INSTALL_DIR/utils/containers.py"
}

# Main installation process
main() {
    print_status "Starting nspawn-ui installation..."
    
    check_root
    detect_distro
    
    print_status "Detected distribution: $DISTRO $DISTRO_VERSION"
    
    read -p "Continue with installation? (y/n): " confirm
    if [[ $confirm != "y" && $confirm != "Y" ]]; then
        print_status "Installation cancelled"
        exit 0
    fi
    
    create_user
    create_install_dir
    setup_machines_dir
    install_dependencies
    copy_files
    create_systemd_service
    setup_networking
    setup_ipv6
    setup_firewall
    setup_python_env
    start_service
    show_post_install_info
    
    print_status "Installation completed successfully!"
}

# Run main function
main "$@"