# nspawn-vps - Self-Hosted Container Management Platform

A production-grade, self-hosted container orchestration platform leveraging systemd-nspawn as the containerization engine with a modern Bootstrap 5 WebUI. The system provides enterprise-level container management with advanced networking capabilities, cross-architecture support, and real-time monitoring capabilities.

## Features

- Container management via systemd-nspawn
- Modern Bootstrap 5 WebUI
- Real-time container monitoring
- Cross-architecture support (arm64/x86_64)
- IPv4 and IPv6 networking
- Resource allocation controls
- SSH configuration automation
- Nested container support
- Docker-in-container capabilities

## Prerequisites

- Linux system with systemd-nspawn support
- Root privileges for installation
- Python 3.9+ installed

## Installation

Run the automated installer:

```bash
sudo ./install.sh
```

## Usage

After installation, access the WebUI at:

- IPv4: http://[YOUR_SERVER_IP]:8080
- IPv6: http://[YOUR_SERVER_IPV6]:8080