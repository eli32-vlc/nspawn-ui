# Self-Hosted Container Manager Backend

This document provides an overview of the backend service for the Self-Hosted Container Manager project. The backend is built using FastAPI and is responsible for managing systemd-nspawn containers, networking, and logs.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Features](#features)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd self-hosted-container-manager/backend
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

## Usage

Once the backend is running, you can access the API at `http://localhost:8000`. Use the provided API endpoints to manage containers, networking, and logs.

## API Endpoints

- **Containers**
  - `POST /containers`: Create a new container.
  - `GET /containers`: List all containers.
  - `GET /containers/{id}`: Get details of a specific container.
  - `PUT /containers/{id}`: Update a container's configuration.
  - `DELETE /containers/{id}`: Remove a container.

- **Networking**
  - `POST /network`: Configure networking settings.
  - `GET /network`: Retrieve current network configurations.

- **Logs**
  - `GET /logs/{id}`: Retrieve logs for a specific container.

## Features

- Dual-stack networking support (IPv4 and IPv6).
- Docker-in-CT functionality for running Docker inside containers.
- Support for nested containers.
- SSH setup for secure access to containers.

For more detailed information, refer to the documentation in the `docs` directory.