# Self-Hosted Container Manager

This project provides a self-hosted container management solution using `systemd-nspawn` as the backend. It features a Bootstrap-based WebUI for managing containers, networking, and logs, with support for dual-stack networking, Docker-in-CT, nested containers, and SSH setup.

## Features

- **Container Management**: Create, start, stop, and remove containers easily through the WebUI.
- **Networking**: Configure networking settings, including dual-stack (IPv4 and IPv6) support.
- **Logs**: Access logs and metadata for each container.
- **Docker-in-CT**: Run Docker inside containers for additional flexibility.
- **Nested Containers**: Support for running containers within containers.
- **SSH Setup**: Easily set up SSH access within containers for remote management.

## Project Structure

- **backend/**: Contains the FastAPI backend service.
- **frontend/**: Contains the React-based frontend application.
- **infrastructure/**: Contains systemd service and template configurations.
- **scripts/**: Contains utility scripts for managing containers and networking.
- **docs/**: Contains documentation for architecture, networking, and operations.

## Getting Started

### Prerequisites

- Ubuntu 24.04.2 LTS
- Python 3.8 or higher
- Node.js and npm for the frontend

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd self-hosted-container-manager
   ```

2. Set up the backend:
   - Navigate to the `backend` directory and install dependencies:
     ```
     cd backend
     pip install -r requirements.txt
     ```

3. Set up the frontend:
   - Navigate to the `frontend` directory and install dependencies:
     ```
     cd frontend
     npm install
     ```

4. Start the backend service:
   ```
   sudo systemctl start nestctl.service
   ```

5. Start the frontend application:
   ```
   cd frontend
   npm start
   ```

## Usage

Access the WebUI at `http://localhost:3000` to manage your containers and networking settings.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.