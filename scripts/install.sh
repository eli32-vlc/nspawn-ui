#!/bin/bash

# Installer script for nspawn-ui

# --- Check for root privileges ---
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# --- Install Dependencies (Debian-based) ---
echo "Installing dependencies..."
apt-get update
apt-get install -y systemd-container debootstrap python3 python3-pip

# --- Install Python Dependencies ---
echo "Installing Python dependencies..."
pip3 install fastapi uvicorn python-jose[cryptography] passlib[bcrypt] cryptography

# --- Networking Setup ---
echo "Configuring networking..."
read -p "Enter the IPv6 prefix for the bridge and containers (e.g., 2001:db8:1::/64): " ipv6_prefix

chmod +x scripts/setup_network.sh
./scripts/setup_network.sh "$ipv6_prefix"

# Install and configure radvd
echo "Installing and configuring radvd..."
apt-get install -y radvd

cat > /etc/radvd.conf << EOL
interface br0
{
    AdvSendAdvert on;
    AdvManagedFlag on;
    AdvOtherConfigFlag on;
    prefix $ipv6_prefix
    {
        AdvOnLink on;
        AdvAutonomous on;
        AdvRouterAddr on;
    };
};
EOL

systemctl enable radvd
systemctl start radvd
echo "radvd configured and started."
# --- Deploy WebUI and API ---
echo "Deploying WebUI and API..."

# Create directories
WEBUI_DIR="/var/www/nspawn-ui"
API_DIR="/opt/nspawn-ui"
mkdir -p $WEBUI_DIR
mkdir -p $API_DIR

# Copy files
cp -r frontend/* $WEBUI_DIR
cp -r backend $API_DIR

echo "WebUI deployed to $WEBUI_DIR"
echo "API deployed to $API_DIR"

# --- Create Initial Admin Credentials ---
echo "Creating initial admin credentials..."
read -p "Enter admin username: " admin_user
read -s -p "Enter admin password: " admin_password
echo

# Create users.json
python3 -c "import json; from passlib.context import CryptContext; pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto'); print(json.dumps({'$admin_user': pwd_context.hash('$admin_password')}))" > $API_DIR/users.json

echo "Admin credentials created."

# --- Configure systemd Service ---
echo "Configuring systemd service for the API..."
read -p "Enter the VM's IPv4 address (e.g., 192.168.2.27) to bind the WebUI to: " vm_ipv4_address

cat > /etc/systemd/system/nspawn-ui.service << EOL
[Unit]
Description=nspawn-ui API
After=network.target

[Service]
User=root
WorkingDirectory=$API_DIR/backend
ExecStart=/usr/bin/python3 -m uvicorn main:app --host $vm_ipv4_address --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable nspawn-ui.service
systemctl start nspawn-ui.service

echo "systemd service created and started."

echo "Installation complete."
