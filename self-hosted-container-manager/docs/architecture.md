# Self-Hosted Container Manager Architecture

## Overview

The Self-Hosted Container Manager is designed to provide an efficient and user-friendly interface for managing systemd-nspawn containers. It leverages a Bootstrap-based WebUI for seamless interaction with the backend services, which are built using FastAPI. The architecture supports advanced features such as dual-stack networking, Docker-in-CT, nested containers, and SSH setup.

## Components

### 1. Backend

The backend is responsible for handling API requests and managing container operations. It consists of the following key modules:

- **API Module**: 
  - `containers.py`: Manages container lifecycle operations (create, start, stop, remove).
  - `networking.py`: Handles network configuration, including IPv4 NAT and IPv6 assignments.
  - `logs.py`: Provides access to container logs and metadata.

- **Core Module**:
  - `docker_in_ct.py`: Facilitates Docker support within the containers.
  - `nspawn_manager.py`: Manages the lifecycle and configuration of systemd-nspawn containers.
  - `network_manager.py`: Configures networking settings for the containers.
  - `ssh_setup.py`: Sets up SSH access within the containers.

### 2. Frontend

The frontend is built using React and provides a Bootstrap-based user interface for interacting with the backend. Key components include:

- **Container List**: Displays the status and IPs of all containers.
- **Logs View**: Shows logs for selected containers.
- **Network Configuration Form**: Allows users to configure network settings for containers.

### 3. Infrastructure

The infrastructure includes systemd service and socket definitions to ensure the backend API starts on boot and listens for incoming requests. It also contains templates for container and network configurations.

### 4. Networking

The system supports dual-stack networking, allowing both IPv4 and IPv6 configurations. The networking setup is managed through scripts that automate the installation and configuration of necessary settings.

### 5. Docker-in-CT

The architecture supports running Docker inside the containers, enabling users to manage additional containerized applications seamlessly.

### 6. SSH Setup

SSH access is configured within the containers, allowing for remote management and interaction with the containerized environments.

## Conclusion

The Self-Hosted Container Manager provides a comprehensive solution for managing systemd-nspawn containers with a focus on usability and advanced networking capabilities. The architecture is modular, allowing for easy extension and maintenance as new features are developed.