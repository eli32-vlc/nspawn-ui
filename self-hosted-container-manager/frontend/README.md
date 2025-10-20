# Self-Hosted Container Manager Frontend

This project provides a Bootstrap-based WebUI for managing containers, networking, and logs using systemd-nspawn as the backend. 

## Features

- **Container Management**: Create, start, stop, and remove containers.
- **Networking**: Configure dual-stack networking (IPv4 and IPv6).
- **Logs**: View logs and metadata for each container.
- **Docker-in-CT**: Manage Docker instances running inside containers.
- **Nested Containers**: Support for running containers within containers.
- **SSH Setup**: Configure SSH access within containers for remote management.

## Getting Started

### Prerequisites

- Node.js and npm installed on your machine.
- Access to the backend API service.

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd self-hosted-container-manager/frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

### Usage

- Access the WebUI at `http://localhost:3000`.
- Use the interface to manage your containers and networking settings.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.