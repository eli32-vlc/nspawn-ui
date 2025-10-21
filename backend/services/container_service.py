"""
Container creation and management service
"""

import subprocess
import os
import platform
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import json
import tempfile

logger = logging.getLogger(__name__)

class ContainerService:
    """Service for managing systemd-nspawn containers"""
    
    def __init__(self):
        self.machines_dir = Path("/var/lib/machines")
        self.nspawn_config_dir = Path("/etc/systemd/nspawn")
        
    def get_architecture(self) -> str:
        """Get the system architecture"""
        arch = platform.machine()
        # Normalize architecture names
        if arch in ["aarch64", "arm64"]:
            return "arm64"
        elif arch in ["x86_64", "amd64"]:
            return "amd64"
        return arch
    
    def get_ubuntu_mirror(self, arch: str) -> str:
        """Get the appropriate Ubuntu mirror based on architecture"""
        if arch == "arm64":
            return "http://ports.ubuntu.com/ubuntu-ports"
        else:
            return "http://archive.ubuntu.com/ubuntu"
    
    def get_debian_mirror(self, arch: str) -> str:
        """Get the appropriate Debian mirror based on architecture"""
        # Debian uses the same mirror for all architectures
        return "http://deb.debian.org/debian"
    
    def create_container(
        self,
        name: str,
        distro: str,
        root_password: str,
        cpu_quota: int = 100,
        memory_mb: int = 512,
        disk_gb: int = 10,
        enable_ssh: bool = True,
        enable_ipv6: bool = True,
        ipv6_mode: Optional[str] = None,
        wireguard_config: Optional[str] = None,
        status_callback = None
    ) -> Dict:
        """
        Create a new container
        
        Args:
            name: Container name
            distro: Distribution in format "distro:version" (e.g., "ubuntu:22.04")
            root_password: Root password for the container
            cpu_quota: CPU quota percentage (100 = 1 core)
            memory_mb: Memory limit in MB
            disk_gb: Disk quota in GB
            enable_ssh: Install and configure SSH server
            enable_ipv6: Enable IPv6 networking
            ipv6_mode: IPv6 mode (native, 6in4, wireguard)
            wireguard_config: WireGuard configuration content
            status_callback: Callback function for status updates
        
        Returns:
            Dict with creation results
        """
        
        def update_status(message: str):
            """Update status via callback"""
            if status_callback:
                status_callback(message)
            logger.info(f"[{name}] {message}")
        
        try:
            # Parse distro
            distro_parts = distro.split(":")
            distro_name = distro_parts[0].lower()
            distro_version = distro_parts[1] if len(distro_parts) > 1 else "latest"
            
            # Get architecture
            arch = self.get_architecture()
            update_status(f"Detected architecture: {arch}")
            
            # Create container directory
            container_dir = self.machines_dir / name
            if container_dir.exists():
                raise Exception(f"Container {name} already exists")
            
            update_status("Creating container directory...")
            container_dir.mkdir(parents=True, exist_ok=True)
            
            # Install base system using debootstrap
            update_status(f"Installing {distro_name} {distro_version} base system...")
            
            if distro_name in ["debian", "ubuntu"]:
                # Get appropriate mirror
                if distro_name == "ubuntu":
                    mirror = self.get_ubuntu_mirror(arch)
                else:
                    mirror = self.get_debian_mirror(arch)
                
                update_status(f"Using mirror: {mirror}")
                
                # For Ubuntu, map version names
                if distro_name == "ubuntu":
                    version_map = {
                        "24.04": "noble",
                        "22.04": "jammy",
                        "20.04": "focal"
                    }
                    suite = version_map.get(distro_version, distro_version)
                else:
                    suite = distro_version
                
                # Run debootstrap
                cmd = [
                    "debootstrap",
                    "--arch=" + arch,
                    suite,
                    str(container_dir),
                    mirror
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                
                if result.returncode != 0:
                    raise Exception(f"debootstrap failed: {result.stderr}")
                
            elif distro_name == "arch":
                # For Arch Linux, we'd need pacstrap which is more complex
                # For now, just indicate it's not fully implemented
                update_status("Arch Linux support is limited")
                raise Exception("Arch Linux containers not fully implemented yet")
            else:
                raise Exception(f"Unsupported distribution: {distro_name}")
            
            # Set root password
            update_status("Setting root password...")
            self._set_root_password(container_dir, root_password)
            
            # Configure networking
            update_status("Configuring network...")
            self._configure_network(container_dir, name, enable_ipv6)
            
            # Install and configure SSH if requested
            if enable_ssh:
                update_status("Installing SSH server...")
                self._install_ssh(container_dir, distro_name)
            
            # Configure IPv6 if requested
            if enable_ipv6 and wireguard_config:
                update_status("Configuring WireGuard...")
                self._configure_wireguard(container_dir, wireguard_config)
            
            # Create systemd-nspawn configuration
            update_status("Creating nspawn configuration...")
            self._create_nspawn_config(
                name,
                cpu_quota,
                memory_mb,
                disk_gb
            )
            
            # Enable and start the container
            update_status("Enabling container service...")
            subprocess.run(
                ["systemctl", "enable", f"systemd-nspawn@{name}.service"],
                capture_output=True,
                check=False
            )
            
            update_status("Starting container...")
            result = subprocess.run(
                ["machinectl", "start", name],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to start container: {result.stderr}")
                # Don't fail here, container is created but not started
            
            update_status("Container created successfully!")
            
            return {
                "success": True,
                "name": name,
                "distro": distro,
                "status": "running" if result.returncode == 0 else "stopped"
            }
            
        except Exception as e:
            update_status(f"Error: {str(e)}")
            # Clean up on failure
            if container_dir.exists():
                logger.error(f"Cleaning up failed container {name}")
                subprocess.run(["rm", "-rf", str(container_dir)], capture_output=True)
            raise
    
    def _set_root_password(self, container_dir: Path, password: str):
        """Set root password in the container"""
        # Ensure tmp directory exists in container
        tmp_dir = container_dir / "tmp"
        tmp_dir.mkdir(exist_ok=True, mode=0o1777)
        
        # Create a script to run in the container
        passwd_script = f"""#!/bin/bash
set -e
echo 'root:{password}' | chpasswd
exit 0
"""
        script_path = tmp_dir / "set_password.sh"
        script_path.write_text(passwd_script)
        script_path.chmod(0o755)
        
        try:
            # Run the script using systemd-nspawn with --quiet and --register=no for non-interactive execution
            result = subprocess.run(
                ["systemd-nspawn", "--quiet", "--register=no", "-D", str(container_dir), "/tmp/set_password.sh"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to set root password. Return code: {result.returncode}")
                logger.error(f"Stdout: {result.stdout}")
                logger.error(f"Stderr: {result.stderr}")
                raise Exception(f"Failed to set root password: {result.stderr}")
                
        finally:
            # Clean up
            if script_path.exists():
                script_path.unlink()
    
    def _configure_network(self, container_dir: Path, name: str, enable_ipv6: bool):
        """Configure container networking"""
        # Create systemd-networkd configuration
        networkd_dir = container_dir / "etc" / "systemd" / "network"
        networkd_dir.mkdir(parents=True, exist_ok=True)
        
        # Host0 interface configuration
        network_config = """[Match]
Name=host0

[Network]
DHCP=yes
"""
        if enable_ipv6:
            network_config += "IPv6AcceptRA=yes\n"
        
        network_file = networkd_dir / "80-container-host0.network"
        network_file.write_text(network_config)
        
        # Enable systemd-networkd
        systemd_dir = container_dir / "etc" / "systemd" / "system" / "multi-user.target.wants"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        
        # Create symlink to enable networkd
        networkd_service = container_dir / "etc" / "systemd" / "system" / "systemd-networkd.service"
        if not networkd_service.exists():
            # Create a relative symlink
            target = Path("../systemd-networkd.service")
            link = systemd_dir / "systemd-networkd.service"
            if not link.exists():
                subprocess.run(
                    ["ln", "-sf", "/lib/systemd/system/systemd-networkd.service",
                     str(link)],
                    check=False
                )
        
        # Configure DNS
        resolv_conf = container_dir / "etc" / "resolv.conf"
        resolv_conf.write_text("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
    
    def _install_ssh(self, container_dir: Path, distro: str):
        """Install and configure SSH server in container"""
        # Ensure tmp directory exists in container
        tmp_dir = container_dir / "tmp"
        tmp_dir.mkdir(exist_ok=True, mode=0o1777)
        
        # Create script to install SSH
        install_script = """#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y openssh-server
systemctl enable ssh
exit 0
"""
        if distro == "arch":
            install_script = """#!/bin/bash
set -e
pacman -Sy --noconfirm openssh
systemctl enable sshd
exit 0
"""
        
        script_path = tmp_dir / "install_ssh.sh"
        script_path.write_text(install_script)
        script_path.chmod(0o755)
        
        # Run the script in the container
        try:
            result = subprocess.run(
                ["systemd-nspawn", "--quiet", "--register=no", "-D", str(container_dir), "/tmp/install_ssh.sh"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.warning(f"SSH installation failed. Return code: {result.returncode}")
                logger.warning(f"Stdout: {result.stdout}")
                logger.warning(f"Stderr: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            logger.warning("SSH installation timed out")
        except Exception as e:
            logger.warning(f"SSH installation error: {str(e)}")
        finally:
            # Clean up
            if script_path.exists():
                script_path.unlink()
        
        # Configure SSH to allow root login
        sshd_config = container_dir / "etc" / "ssh" / "sshd_config"
        if sshd_config.exists():
            config_text = sshd_config.read_text()
            config_text += "\nPermitRootLogin yes\nPasswordAuthentication yes\n"
            sshd_config.write_text(config_text)
    
    def _configure_wireguard(self, container_dir: Path, wireguard_config: str):
        """Configure WireGuard in the container"""
        # Create wireguard directory
        wg_dir = container_dir / "etc" / "wireguard"
        wg_dir.mkdir(parents=True, exist_ok=True)
        
        # Write wireguard config
        wg_config_file = wg_dir / "wg0.conf"
        wg_config_file.write_text(wireguard_config)
        wg_config_file.chmod(0o600)
        
        # Ensure tmp directory exists in container
        tmp_dir = container_dir / "tmp"
        tmp_dir.mkdir(exist_ok=True, mode=0o1777)
        
        # Install wireguard in container
        install_script = """#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wireguard wireguard-tools
systemctl enable wg-quick@wg0
exit 0
"""
        
        script_path = tmp_dir / "install_wg.sh"
        script_path.write_text(install_script)
        script_path.chmod(0o755)
        
        try:
            result = subprocess.run(
                ["systemd-nspawn", "--quiet", "--register=no", "-D", str(container_dir), "/tmp/install_wg.sh"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.warning(f"WireGuard installation failed. Return code: {result.returncode}")
                logger.warning(f"Stdout: {result.stdout}")
                logger.warning(f"Stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.warning("WireGuard installation timed out")
        except Exception as e:
            logger.warning(f"WireGuard installation error: {str(e)}")
        finally:
            if script_path.exists():
                script_path.unlink()
    
    def _create_nspawn_config(
        self,
        name: str,
        cpu_quota: int,
        memory_mb: int,
        disk_gb: int
    ):
        """Create systemd-nspawn configuration file"""
        config_file = self.nspawn_config_dir / f"{name}.nspawn"
        self.nspawn_config_dir.mkdir(parents=True, exist_ok=True)
        
        # CPU quota: 100% = 1 core = 100000 (CPUQuota in systemd)
        cpu_quota_value = cpu_quota * 1000  # Convert to systemd units
        
        config = f"""[Exec]
Boot=yes
PrivateUsers=yes

[Network]
VirtualEthernet=yes
Bridge=br0

[Files]
Bind=/dev/net/tun

[Resource]
CPUQuota={cpu_quota_value}
MemoryMax={memory_mb}M
"""
        
        config_file.write_text(config)
        logger.info(f"Created nspawn config for {name}")

# Global instance
container_service = ContainerService()
