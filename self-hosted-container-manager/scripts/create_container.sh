#!/bin/bash

# This script creates a new container based on user input.

# Function to display usage
usage() {
    echo "Usage: $0 <container_name> <image> [options]"
    echo "Options:"
    echo "  --network <network_name>   Specify the network to attach the container to."
    echo "  --dual-stack                Enable dual-stack networking (IPv4 and IPv6)."
    echo "  --ssh                       Set up SSH access in the container."
    exit 1
}

# Check for minimum arguments
if [ "$#" -lt 2 ]; then
    usage
fi

CONTAINER_NAME=$1
IMAGE=$2
NETWORK=""
DUAL_STACK=false
SETUP_SSH=false

# Parse options
shift 2
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --network)
            NETWORK=$2
            shift 2
            ;;
        --dual-stack)
            DUAL_STACK=true
            shift
            ;;
        --ssh)
            SETUP_SSH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Create the container
echo "Creating container '$CONTAINER_NAME' from image '$IMAGE'..."

# Command to create the container using systemd-nspawn
sudo systemd-nspawn -D /var/lib/machines/$CONTAINER_NAME --image=$IMAGE

# Configure networking if specified
if [ -n "$NETWORK" ]; then
    echo "Attaching container to network '$NETWORK'..."
    # Add networking configuration here
fi

# Enable dual-stack networking if specified
if [ "$DUAL_STACK" = true ]; then
    echo "Enabling dual-stack networking for container '$CONTAINER_NAME'..."
    # Add dual-stack configuration here
fi

# Set up SSH if specified
if [ "$SETUP_SSH" = true ]; then
    echo "Setting up SSH access for container '$CONTAINER_NAME'..."
    # Call the SSH setup script
    ./setup_ssh.sh "$CONTAINER_NAME"
fi

echo "Container '$CONTAINER_NAME' created successfully."