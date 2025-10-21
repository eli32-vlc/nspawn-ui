# VPS Creation and Feature Updates

## Overview
This update implements full VPS creation functionality, adds Network and Settings pages, and includes support for ARM64 architecture and WireGuard VPN configuration.

## New Features

### 1. VPS Creation
VPS creation now works with real systemd-nspawn containers using debootstrap.

**Supported Distributions:**
- Debian (bookworm, bullseye, sid)
- Ubuntu (24.04, 22.04, 20.04)

**Supported Architectures:**
- x86_64 (amd64)
- ARM64 (aarch64)

**Key Features:**
- Automatic architecture detection
- ARM64 uses Ubuntu Ports mirror (`http://ports.ubuntu.com/ubuntu-ports`)
- Real-time status updates during creation
- Progress bar showing installation steps
- SSH server installation
- IPv6 configuration options
- WireGuard VPN support

### 2. Network Page
New network management interface accessible from the main navigation.

**Features:**
- Bridge status display
- IPv6 configuration (Native, 6in4 Tunnel, WireGuard)
- NAT and port forwarding rules management
- Container port forwarding configuration

**Access:** Click "Network" in the navigation bar

### 3. Settings Page
System settings and configuration interface.

**Features:**
- System information (architecture, CPU, memory, disk)
- Storage usage visualization
- User password management
- Default resource preferences
- System maintenance tools

**Access:** Click "Settings" in the navigation bar

## VPS Creation Workflow

### Step 1: Basic Configuration
1. Enter VPS name (lowercase, hyphens only)
2. Select distribution (Debian/Ubuntu)
3. Choose version
4. Set root password

### Step 2: Resource Allocation
1. Set CPU quota (25% - 400%)
2. Set memory limit (256MB - 8GB)
3. Set disk quota (5GB - 100GB)

### Step 3: Advanced Options
1. Enable/disable SSH server
2. Enable/disable IPv6
3. **New:** Select IPv6 mode:
   - **Native IPv6:** Use if you have native IPv6 connectivity
   - **6in4 Tunnel:** Use for Hurricane Electric tunnels
   - **WireGuard:** Use for WireGuard VPN-based IPv6

### WireGuard Configuration
When selecting WireGuard as the IPv6 mode:

1. A text area will appear
2. Paste your WireGuard configuration, for example:
   ```
   [Interface]
   PrivateKey = YOUR_PRIVATE_KEY
   Address = YOUR_IPV6_ADDRESS/64
   
   [Peer]
   PublicKey = SERVER_PUBLIC_KEY
   Endpoint = SERVER_IP:PORT
   AllowedIPs = ::/0
   PersistentKeepalive = 25
   ```
3. The configuration will be saved to `/etc/wireguard/wg0.conf` in the container
4. WireGuard will be automatically installed and enabled

### Creation Progress
After clicking "Create VPS", you'll see:
- Progress bar (0-100%)
- Status messages for each step:
  - Architecture detection
  - Directory creation
  - Base system installation (may take 5-10 minutes)
  - Root password configuration
  - Network setup
  - SSH installation
  - WireGuard setup (if enabled)
  - Container start

The entire process may take 10-15 minutes depending on network speed.

## ARM64 Support

### Automatic Detection
The system automatically detects ARM64 architecture and uses the appropriate package repositories.

**ARM64 Mirror:**
- Ubuntu: `http://ports.ubuntu.com/ubuntu-ports`
- Debian: `http://deb.debian.org/debian` (supports all architectures)

### Testing on ARM64
If you're running on an ARM64 system (like Raspberry Pi 4, AWS Graviton, etc.):
1. The system will automatically detect the architecture
2. Ubuntu installations will use the ports mirror
3. All other functionality remains the same

## API Changes

### New Endpoints

**Get Creation Status:**
```
GET /api/containers/create-status/{container_id}
```

Returns:
```json
{
  "status": "installing",
  "message": "Installing ubuntu 22.04 base system...",
  "progress": 30,
  "error": null
}
```

**Create Container (Updated):**
```
POST /api/containers/create
```

New fields:
- `ipv6_mode`: "native", "6in4", or "wireguard"
- `wireguard_config`: WireGuard configuration text (required if ipv6_mode is "wireguard")

## Troubleshooting

### Container Creation Fails
1. Check system logs: `journalctl -u zenithstack -f`
2. Verify debootstrap is installed: `which debootstrap`
3. Check available disk space: `df -h /var/lib/machines`
4. Ensure internet connectivity for package downloads

### ARM64 Mirror Issues
If you encounter errors downloading packages on ARM64:
1. Verify you can reach `http://ports.ubuntu.com`
2. Check DNS resolution: `nslookup ports.ubuntu.com`
3. Verify architecture: `uname -m` (should show aarch64)

### WireGuard Not Working
1. Verify WireGuard configuration syntax
2. Check container logs: `journalctl -u systemd-nspawn@CONTAINER_NAME`
3. Test inside container: `machinectl shell CONTAINER_NAME`
4. Check WireGuard status: `wg show`

## Known Limitations

1. **Arch Linux:** Not fully implemented yet (requires pacstrap)
2. **Resource Limits:** Disk quotas require btrfs or ext4 with quotas enabled
3. **IPv6 6in4:** Configuration UI not yet complete

## Future Enhancements

- Arch Linux support
- Container templates and snapshots
- Automated backups
- Container cloning
- Resource usage graphs
- Web-based terminal access

## Technical Details

### Container Creation Process
1. Detect system architecture
2. Select appropriate package mirror
3. Run debootstrap to create base system
4. Configure root password using systemd-nspawn
5. Set up systemd-networkd for networking
6. Install SSH server (if enabled)
7. Install and configure WireGuard (if enabled)
8. Create systemd-nspawn configuration file
9. Enable and start container service

### Directory Structure
```
/var/lib/machines/CONTAINER_NAME/    # Container root filesystem
/etc/systemd/nspawn/CONTAINER_NAME.nspawn  # Container configuration
```

### Resource Limits
Resource limits are enforced via systemd unit file configuration:
- CPU: CPUQuota parameter (100% = 1 core)
- Memory: MemoryMax parameter
- Disk: File system quotas (when supported)

## Compatibility

**Tested On:**
- Ubuntu 22.04 LTS (x86_64)
- Ubuntu 20.04 LTS (x86_64)
- Debian 12 (Bookworm)

**Should Work On:**
- Ubuntu 24.04 LTS
- ARM64/aarch64 systems
- Any Linux with systemd 239+

**Requirements:**
- systemd 239 or higher
- debootstrap
- systemd-container
- bridge-utils
- Python 3.9+
