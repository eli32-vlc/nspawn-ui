# Networking Setup and Configuration for Self-Hosted Container Manager

This document outlines the networking setup and configurations for the self-hosted container manager using systemd-nspawn. It includes details on dual-stack networking, Docker-in-CT, nested containers, and SSH setup.

## Dual-Stack Networking

The container manager supports dual-stack networking, allowing both IPv4 and IPv6 addresses to be assigned to containers. This is achieved through the following steps:

1. **Network Configuration**: Ensure that the network configuration files are set up correctly. The `network.netdev` template in the `infrastructure/templates` directory should define both IPv4 and IPv6 settings.

2. **Container Networking**: When creating a new container, specify the desired IP addresses in the container configuration. The `network_manager.py` module handles the assignment of these addresses.

3. **Testing Connectivity**: After setting up the network, test connectivity from the host to the container using both IPv4 and IPv6 addresses. Use tools like `ping` and `curl` to verify that the containers are reachable.

## Docker-in-CT

The container manager allows running Docker inside containers (Docker-in-CT). This feature is useful for isolating Docker environments. To set this up:

1. **Install Docker**: Ensure that Docker is installed in the container. The `docker_in_ct.py` module manages the installation and configuration of Docker within the container.

2. **Container Configuration**: When creating a container, enable Docker support by specifying the appropriate flags in the `create_container.sh` script.

3. **Accessing Docker**: Once Docker is set up, you can access it from within the container using standard Docker commands. Ensure that the Docker daemon is running.

## Nested Containers

The container manager supports nested containers, allowing you to run systemd-nspawn containers within other containers. To enable this feature:

1. **Configuration**: Modify the container configuration to allow nested virtualization. This can be done by setting the appropriate flags in the `container.nspawn` template.

2. **Resource Management**: Ensure that the host system has sufficient resources (CPU, memory) to support nested containers.

3. **Testing**: Create a container that runs another container and verify that it operates correctly. Use the `nspawn_manager.py` module to manage these nested containers.

## SSH Setup

Setting up SSH access inside containers is crucial for remote management. Follow these steps:

1. **SSH Installation**: Use the `setup_ssh.sh` script to install and configure SSH within the container. This script ensures that the SSH service is enabled and running.

2. **Key Management**: Manage SSH keys for secure access. You can configure public key authentication by adding your public key to the `~/.ssh/authorized_keys` file inside the container.

3. **Testing SSH Access**: After setting up SSH, test the connection from the host to the container using the command:
   ```
   ssh user@container-ip
   ```

By following these guidelines, you can effectively manage networking for your self-hosted container manager, ensuring robust connectivity and functionality for your containers.