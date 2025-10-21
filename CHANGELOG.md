# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - 2025-10-21

#### VPS Creation
- **Full VPS Creation Implementation**: Complete container creation using debootstrap and systemd-nspawn
  - Supports Debian (bookworm, bullseye, sid) and Ubuntu (24.04, 22.04, 20.04)
  - Background task execution for non-blocking creation
  - Automatic SSH server installation and configuration
  - Network configuration with systemd-networkd
  - Resource limits (CPU, memory, disk) via systemd cgroups

#### ARM64 Support
- **Automatic Architecture Detection**: Detects x86_64 and ARM64 architectures
- **Ubuntu Ports Mirror for ARM64**: Automatically uses `http://ports.ubuntu.com/ubuntu-ports` for ARM64 systems
- **Cross-Architecture Support**: Same codebase works on both x86_64 and ARM64

#### Status Tracking
- **Real-Time Progress Updates**: Shows creation progress with detailed status messages
- **Progress Bar**: Visual feedback from 0-100% during VPS creation
- **Status Polling Endpoint**: `GET /api/containers/create-status/{container_id}`
- **10 Progress Stages**:
  1. Architecture detection (10%)
  2. Directory creation (20%)
  3. Base system installation (30%)
  4. Root password setup (60%)
  5. Network configuration (70%)
  6. SSH installation (80%)
  7. WireGuard setup (85%)
  8. nspawn configuration (90%)
  9. Container start (95%)
  10. Completion (100%)

#### WireGuard VPN Support
- **IPv6 Mode Selection**: Choose between Native IPv6, 6in4 Tunnel, or WireGuard
- **Configuration Input**: Large textarea for WireGuard configuration
- **Automatic Installation**: WireGuard packages installed automatically in container
- **Secure Configuration**: Config saved with 0600 permissions to `/etc/wireguard/wg0.conf`
- **Service Auto-Enable**: `wg-quick@wg0` service automatically enabled

#### Network Management Page
- **Bridge Status Display**: Shows network bridge configuration
- **IPv6 Configuration**: Interface for IPv6 mode selection
- **NAT Rules Management**: View and manage port forwarding rules
- **Port Forwarding UI**: Add/delete port forwarding rules via modal dialog
- **Container Selection**: Dropdown to select containers for port forwarding

#### Settings Page
- **System Information**: Display architecture, CPU count, memory, disk space, uptime
- **Storage Visualization**: Disk usage with progress bar
- **User Management**: Password change form
- **System Preferences**: Default resource settings for new containers
- **Advanced Settings**: Refresh distributions, clear logs

#### Documentation
- **VPS Creation Guide** (`docs/VPS_CREATION_GUIDE.md`): Complete user guide
  - VPS creation workflow
  - WireGuard configuration examples
  - ARM64 support details
  - Troubleshooting guide
  - API reference
- **Developer Guide** (`docs/DEVELOPER_GUIDE.md`): Technical documentation
  - Architecture overview
  - Implementation details
  - Testing checklist
  - Development workflow
- **Implementation Summary** (`IMPLEMENTATION_SUMMARY.md`): Feature summary and statistics

#### Backend Changes
- **Container Service** (`backend/services/container_service.py`): New service layer for container operations
- **Status Tracking API** (`backend/api/containers.py`): Background tasks and status endpoints
- **Route Additions** (`backend/main.py`): Routes for /network and /settings pages

#### Frontend Changes
- **Network Page**: Complete UI for network management (`frontend/templates/network.html`, `frontend/static/js/network.js`)
- **Settings Page**: Complete UI for system settings (`frontend/templates/settings.html`, `frontend/static/js/settings.js`)
- **Enhanced VPS Creation**: IPv6 mode selector, WireGuard config input, status display
- **Fixed Navigation**: All pages now link to Network and Settings

### Changed
- **Container Creation**: Now uses actual systemd-nspawn instead of mock response
- **Navigation Links**: Updated all templates to properly link to Network and Settings pages
- **VPS Creation UI**: Added progress tracking and status messages

### Fixed
- **VPS Creation**: Was returning mock data, now creates actual containers
- **Network Page**: Was missing, now fully functional
- **Settings Page**: Was missing, now fully functional
- **Navigation Links**: Were pointing to `#`, now point to actual pages

### Technical Details
- **Lines Changed**: 2,010 lines added/modified
- **Files Changed**: 13 files
- **New Files**: 7 files created
- **Python Code**: All files pass syntax check
- **JavaScript Code**: All files pass syntax check

## [1.0.0] - Initial Release

### Added
- Basic FastAPI backend
- Bootstrap 5 frontend
- JWT authentication
- Dashboard with VPS list
- VPS detail page
- Login page
- Mock container operations (start, stop, delete)
- System information API
- Real-time log streaming (WebSocket)

---

**Note**: Version numbers follow [Semantic Versioning](https://semver.org/).
