#!/bin/bash

# This script sets up SSH access inside the containers.

# Function to create SSH keys if they do not exist
create_ssh_keys() {
    if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
        echo "Generating SSH host keys..."
        ssh-keygen -A
    fi
}

# Function to configure SSH daemon
configure_sshd() {
    echo "Configuring SSH daemon..."
    # Allow root login and password authentication
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
}

# Function to start SSH service
start_sshd() {
    echo "Starting SSH service..."
    service ssh start
}

# Main script execution
create_ssh_keys
configure_sshd
start_sshd

echo "SSH setup completed."