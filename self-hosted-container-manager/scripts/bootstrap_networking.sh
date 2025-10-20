#!/bin/bash

# This script installs and configures networking settings for the self-hosted container manager.
# It sets up dual-stack networking (IPv4 and IPv6) and configures necessary network interfaces.

set -e

# Function to configure IPv4 and IPv6
configure_network() {
    local interface=$1
    local ipv4_address=$2
    local ipv6_address=$3

    echo "Configuring network interface: $interface"
    
    # Configure IPv4
    ip addr add $ipv4_address dev $interface
    ip link set dev $interface up

    # Configure IPv6
    ip -6 addr add $ipv6_address dev $interface
}

# Main script execution
main() {
    # Define network interface and addresses
    local interface="veth0"
    local ipv4_address="192.168.1.100/24"
    local ipv6_address="fd00::100/64"

    # Create the network interface
    ip link add $interface type veth

    # Configure the network
    configure_network $interface $ipv4_address $ipv6_address

    echo "Networking configured successfully."
}

main "$@"