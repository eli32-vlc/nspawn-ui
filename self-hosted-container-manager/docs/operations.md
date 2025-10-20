# Operational Guidelines for Self-Hosted Container Manager

## Overview

This document provides operational guidelines for managing the self-hosted container manager using systemd-nspawn as the backend. It covers the essential commands and procedures for container management, networking configurations, and log retrieval.

## Container Management

### Creating a Container

To create a new container, use the following command:

```bash
./scripts/create_container.sh <container_name>
```

Replace `<container_name>` with the desired name for your container.

### Starting a Container

To start an existing container, execute:

```bash
sudo systemd-nspawn -D /var/lib/machines/<container_name>
```

### Stopping a Container

To stop a running container, use:

```bash
sudo machinectl stop <container_name>
```

### Removing a Container

To remove a container, first stop it, then run:

```bash
sudo machinectl remove <container_name>
```

## Networking Configuration

### Dual-Stack Networking

To configure dual-stack networking (IPv4 and IPv6), ensure your network configuration file is set up correctly. You can modify the network settings in the `infrastructure/templates/network.netdev` file.

### Assigning IP Addresses

You can assign IP addresses to your containers by editing the respective configuration files or using the API endpoints provided in the backend.

## Docker-in-CT

To enable Docker support within a container, ensure that the `docker_in_ct.py` script is properly configured. You can start Docker inside the container by executing:

```bash
sudo systemd-nspawn -D /var/lib/machines/<container_name> --bind=/var/run/docker.sock:/var/run/docker.sock
```

## SSH Setup

To set up SSH access inside a container, run the following script:

```bash
./scripts/setup_ssh.sh <container_name>
```

This will configure SSH access, allowing you to connect to the container using SSH.

## Log Retrieval

To retrieve logs from a specific container, you can use the logs API endpoint or access the logs directly from the container's filesystem:

```bash
sudo journalctl -u <container_name>.service
```

## Conclusion

These operational guidelines provide a foundation for managing your self-hosted container manager. For further details, refer to the specific documentation for each component and the API usage instructions in the backend README.