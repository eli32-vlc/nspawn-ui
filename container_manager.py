import subprocess
import os
import json
import pwd
from typing import Optional, Dict, List
import time

class ContainerManager:
    """
    Container manager for systemd-nspawn containers with full management capabilities
    """
    
    def __init__(self):
        self.machines_dir = "/var/lib/machines"
        self.nspawn_config_dir = "/etc/systemd/nspawn"
        self.network_dir = "/etc/systemd/network"
        
        # Ensure required directories exist
        os.makedirs(self.machines_dir, exist_ok=True)
        os.makedirs(self.nspawn_config_dir, exist_ok=True)
        
    def list_containers(self) -> List[Dict]:
        """
        List all containers with their status, IPs, and resource usage
        """
        containers = []
        
        # Get machine status
        try:
            result = subprocess.run(['machinectl', 'list', '--no-legend'], 
                                  capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        name = parts[0]
                        state = parts[1].lower()
                        
                        # Get more details for each container
                        details = self._get_container_details(name)
                        containers.append({
                            'name': name,
                            'state': state,
                            'ipv4': details.get('ipv4'),
                            'ipv6': details.get('ipv6'),
                            'os': details.get('os', 'Unknown'),
                            'ram': details.get('ram', 'Unknown'),
                            'disk': details.get('disk', 'Unknown')
                        })
        except subprocess.CalledProcessError:
            # If machinectl fails, try to list directories in machines_dir
            for item in os.listdir(self.machines_dir):
                if os.path.isdir(os.path.join(self.machines_dir, item)):
                    # Check if container is running
                    is_running = self._is_container_running(item)
                    containers.append({
                        'name': item,
                        'state': 'running' if is_running else 'stopped',
                        'ipv4': 'N/A',
                        'ipv6': 'N/A',
                        'os': 'Unknown',
                        'ram': 'N/A',
                        'disk': 'N/A'
                    })
        
        return containers
    
    def _is_container_running(self, name: str) -> bool:
        """Check if a container is currently running"""
        try:
            result = subprocess.run(['machinectl', 'status', name], 
                                  capture_output=True, text=True)
            return 'State: running' in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def _get_container_details(self, name: str) -> Dict:
        """Get detailed information about a container"""
        details = {}
        
        # Try to get more information using machinectl show
        try:
            result = subprocess.run(['machinectl', 'show', name], 
                                  capture_output=True, text=True, check=True)
            
            for line in result.stdout.split('\n'):
                if 'Service=' in line:
                    details['os'] = line.split('=')[1] if '=' in line else 'Unknown'
                elif 'MemoryCurrent=' in line:
                    mem_bytes = line.split('=')[1] if '=' in line else '0'
                    if mem_bytes != '0':
                        details['ram'] = f"{int(mem_bytes) / (1024**2):.2f} MB"
                    else:
                        details['ram'] = 'N/A'
        except subprocess.CalledProcessError:
            pass
        
        # Get network information if container is running
        if self._is_container_running(name):
            try:
                result = subprocess.run(['machinectl', 'status', name], 
                                      capture_output=True, text=True)
                
                # Extract IP information from the status output
                for line in result.stdout.split('\n'):
                    if 'Addresses:' in line:
                        # Parse IP addresses from the line
                        addr_part = line.split('Addresses:')[1].strip()
                        parts = addr_part.split()
                        
                        ipv4 = None
                        ipv6 = None
                        
                        for part in parts:
                            if ':' in part and not part.startswith('['):  # IPv6
                                if not ipv6:
                                    ipv6 = part
                            elif '.' in part and not part.startswith('['):  # IPv4
                                if not ipv4:
                                    ipv4 = part
                        
                        details['ipv4'] = ipv4
                        details['ipv6'] = ipv6
                        break
            except subprocess.CalledProcessError:
                pass
        
        return details
    
    def create_container(self, name: str, distribution: str, release: str = "latest", 
                        root_password: Optional[str] = None, ipv4: Optional[str] = None,
                        ipv6: Optional[str] = None, cpu_limit: Optional[int] = None,
                        memory_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> str:
        """
        Create a new container with specified parameters
        """
        # Validate container name
        if not name or not name.replace('-', '').replace('_', '').isalnum():
            raise ValueError("Invalid container name. Use alphanumeric characters, hyphens, and underscores only.")
        
        # Check if container already exists
        if os.path.exists(f"{self.machines_dir}/{name}"):
            raise ValueError(f"Container {name} already exists")
        
        # Create the container using debootstrap
        cmd = [
            'debootstrap',
            '--variant=minbase',
            f'--include=systemd,vim,openssh-server,curl,wget,sudo,supervisor',
            release if release != 'latest' else 'stable',
            f'{self.machines_dir}/{name}',
            f'http://deb.debian.org/debian' if distribution == 'debian' else 
            f'http://archive.ubuntu.com/ubuntu' if distribution == 'ubuntu' else
            f'https://download.fedoraproject.org/pub/fedora/linux/releases/38/Everything/x86_64/os/'
        ]
        
        # Handle different distributions
        if distribution == 'arch':
            # For Arch, we need to use pacstrap instead of debootstrap
            cmd = ['pacstrap', '-c', f'{self.machines_dir}/{name}', 
                   'base', 'systemd', 'vim', 'openssh', 'curl', 'wget', 'sudo']
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create container {name}: {str(e)}")
        
        # Set root password if provided
        if root_password:
            self._set_root_password(name, root_password)
        
        # Setup SSH if needed
        self._setup_ssh_in_container(name)
        
        # Configure resource limits if provided
        if cpu_limit or memory_limit or storage_limit:
            self._configure_resource_limits(name, cpu_limit, memory_limit, storage_limit)
        
        # Setup networking configuration
        if ipv4 or ipv6:
            self._configure_container_networking(name, ipv4, ipv6)
        
        # Enable Docker-in-CT if needed by bind mounting docker socket
        self._setup_docker_in_container(name)
        
        # Enable nested containers capabilities
        self._setup_nested_containers(name)
        
        # Create .nspawn configuration file
        self._create_nspawn_config(name, cpu_limit, memory_limit, storage_limit)
        
        return f"Container {name} created successfully"
    
    def _set_root_password(self, name: str, password: str):
        """Set root password in the container"""
        # This is a simplified approach. In practice, you might need to chroot or use systemd-nspawn exec
        container_path = f"{self.machines_dir}/{name}"
        
        # Create a script to change the password
        script_content = f"""#!/bin/bash
chroot {container_path} /bin/bash -c "echo 'root:{password}' | chpasswd"
"""
        
        script_path = f"/tmp/set_password_{name}.sh"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
        
        try:
            subprocess.run(['bash', script_path], check=True)
        finally:
            os.remove(script_path)
    
    def _setup_ssh_in_container(self, name: str):
        """Setup SSH in the container"""
        container_path = f"{self.machines_dir}/{name}"
        
        # Ensure ssh directory exists and has proper permissions
        ssh_dir = f"{container_path}/etc/ssh"
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o755, exist_ok=True)
        
        # Generate host keys if they don't exist
        host_key_files = [
            f"{ssh_dir}/ssh_host_rsa_key",
            f"{ssh_dir}/ssh_host_ecdsa_key", 
            f"{ssh_dir}/ssh_host_ed25519_key"
        ]
        
        for key_file in host_key_files:
            if not os.path.exists(key_file):
                subprocess.run([
                    'chroot', container_path,
                    'ssh-keygen', '-f', key_file.replace(container_path, ''), 
                    '-N', '', '-t', 
                    'rsa' if 'rsa' in key_file else 'ecdsa' if 'ecdsa' in key_file else 'ed25519'
                ], check=False)  # Don't fail if ssh-keygen is not available
        
        # Ensure SSH service is enabled
        subprocess.run([
            'chroot', container_path,
            'systemctl', 'enable', 'ssh'
        ], check=False)  # Continue even if systemctl fails
    
    def _configure_resource_limits(self, name: str, cpu_limit: Optional[int] = None,
                                 memory_limit: Optional[int] = None, 
                                 storage_limit: Optional[int] = None):
        """Configure resource limits for the container"""
        # This would create systemd slice configurations
        slice_content = "[Slice]\n"
        
        if cpu_limit:
            slice_content += f"CPUQuota={cpu_limit}%\n"
        
        if memory_limit:
            slice_content += f"MemoryMax={memory_limit}M\n"
        
        # Storage limit would need to be handled differently (e.g., with quotas)
        # For now, we'll note it as a TODO
        if storage_limit:
            # Note: Storage limits are complex and would require quota filesystems
            print(f"Note: Storage limit of {storage_limit}MB requested for {name}, implementation needed")
        
        # Write slice configuration
        slice_file = f"/etc/systemd/system/machine-{name}.slice"
        with open(slice_file, 'w') as f:
            f.write(slice_content)
        
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
    
    def _configure_container_networking(self, name: str, ipv4: Optional[str] = None, 
                                      ipv6: Optional[str] = None):
        """Configure networking for the container"""
        # This would set up the container's network configuration
        # For systemd-nspawn, we use .nspawn files
        nspawn_file = f"{self.nspawn_config_dir}/{name}.nspawn"
        
        with open(nspawn_file, 'w') as f:
            f.write("[Network]\n")
            if ipv4:
                f.write(f"VirtualEthernet=yes\n")  # This enables networking
                # We'll need to configure this further based on how networking is set up
            else:
                f.write("VirtualEthernet=yes\n")  # Default to virtual ethernet
            
            # Additional network configuration would go here
            f.write("[Exec]\n")
            if ipv4:
                f.write(f"Environment=STATIC_IPV4={ipv4}\n")
            if ipv6:
                f.write(f"Environment=STATIC_IPV6={ipv6}\n")
    
    def _setup_docker_in_container(self, name: str):
        """Enable Docker support in the container"""
        # Create symlink to docker socket if it exists
        docker_socket = "/var/run/docker.sock"
        container_docker_socket = f"{self.machines_dir}/{name}/var/run/docker.sock"
        
        if os.path.exists(docker_socket):
            # Ensure the directory exists
            container_docker_dir = os.path.dirname(container_docker_socket)
            os.makedirs(container_docker_dir, exist_ok=True)
            
            # Create a bind mount for the docker socket
            # This would need to be done when starting the container
            pass
    
    def _setup_nested_containers(self, name: str):
        """Enable nested container capabilities"""
        nspawn_file = f"{self.nspawn_config_dir}/{name}.nspawn"
        
        # Append to the existing .nspawn file or create a new one
        with open(nspawn_file, 'a') as f:
            f.write("\n[Exec]\n")
            f.write("# Enable capabilities needed for nested containers\n")
            f.write("Capability=all\n")
            f.write("NoNewPrivileges=no\n")
            
            f.write("\n[Files]\n")
            f.write("# Enable user namespaces for nested containers\n")
            f.write("EnableUserNamespaces=yes\n")
            f.write("PrivateUsers=keep\n")
    
    def _create_nspawn_config(self, name: str, cpu_limit: Optional[int], 
                            memory_limit: Optional[int], storage_limit: Optional[int]):
        """Create the .nspawn configuration file for the container"""
        nspawn_file = f"{self.nspawn_config_dir}/{name}.nspawn"
        
        with open(nspawn_file, 'w') as f:
            f.write(f"# Configuration for container {name}\n")
            f.write("[Exec]\n")
            f.write("Boot=yes\n")  # Boot a full system in the container
            
            if cpu_limit:
                f.write(f"CPUQuota={cpu_limit}%\n")
            
            if memory_limit:
                f.write(f"MemoryMax={memory_limit}M\n")
            
            f.write("\n[Files]\n")
            f.write("EnableHome=yes\n")
            
            f.write("\n[Network]\n")
            f.write("VirtualEthernet=yes\n")
    
    def start_container(self, name: str) -> str:
        """Start a container"""
        try:
            subprocess.run(['machinectl', 'start', name], check=True)
            return f"Container {name} started successfully"
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start container {name}: {str(e)}")
    
    def stop_container(self, name: str) -> str:
        """Stop a container"""
        try:
            subprocess.run(['machinectl', 'stop', name], check=True)
            return f"Container {name} stopped successfully"
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to stop container {name}: {str(e)}")
    
    def restart_container(self, name: str) -> str:
        """Restart a container"""
        self.stop_container(name)
        time.sleep(2)  # Wait a bit before starting again
        return self.start_container(name)
    
    def remove_container(self, name: str) -> str:
        """Remove a container"""
        # First stop the container if it's running
        if self._is_container_running(name):
            self.stop_container(name)
            time.sleep(2)  # Give it time to stop
        
        # Then remove it
        try:
            subprocess.run(['machinectl', 'remove', name], check=True)
            return f"Container {name} removed successfully"
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to remove container {name}: {str(e)}")
    
    def get_container_logs(self, name: str) -> str:
        """Get container logs"""
        try:
            # Using journalctl to get logs for the container
            result = subprocess.run([
                'journalctl', '-m', f'MACHINE={name}', '-o', 'short-iso'
            ], capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError:
            # If journalctl fails, try getting logs from the container's systemd
            try:
                result = subprocess.run([
                    'machinectl', 'shell', '-q', f'{name}#', 'journalctl', '--no-pager'
                ], capture_output=True, text=True, timeout=10)
                return result.stdout
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # If all else fails, return a default message
                return f"No logs available for container {name}"
    
    def get_networking_info(self) -> Dict:
        """Get current networking configuration"""
        network_info = {}
        
        # Get network interfaces
        try:
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, check=True)
            network_info['interfaces'] = result.stdout
        except subprocess.CalledProcessError:
            network_info['interfaces'] = 'Error getting interface info'
        
        # Get routing information
        try:
            result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True, check=True)
            network_info['routes'] = result.stdout
        except subprocess.CalledProcessError:
            network_info['routes'] = 'Error getting route info'
        
        # Get IPv6 tunnel status if exists
        try:
            result = subprocess.run(['ip', '-6', 'tunnel', 'show'], capture_output=True, text=True)
            network_info['ipv6_tunnels'] = result.stdout
        except subprocess.CalledProcessError:
            network_info['ipv6_tunnels'] = 'No IPv6 tunnels found or error getting info'
        
        # Get bridge configuration
        try:
            result = subprocess.run(['brctl', 'show'], capture_output=True, text=True)
            network_info['bridges'] = result.stdout
        except subprocess.CalledProcessError:
            network_info['bridges'] = 'Bridge utils not available or no bridges configured'
        
        return network_info
    
    def setup_networking(self, network_type: str, config: Dict) -> str:
        """Setup networking based on type and configuration"""
        if network_type == 'native':
            return self._setup_native_ipv6(config)
        elif network_type == '6in4':
            return self._setup_6in4_tunnel(config)
        elif network_type == 'wireguard':
            return self._setup_wireguard_tunnel(config)
        else:
            raise ValueError(f"Unsupported network type: {network_type}")
    
    def _setup_native_ipv6(self, config: Dict) -> str:
        """Setup native IPv6 networking"""
        ipv6_subnet = config.get('ipv6_subnet')
        gateway = config.get('gateway')
        
        if not ipv6_subnet or not gateway:
            raise ValueError("IPv6 subnet and gateway are required for native IPv6 setup")
        
        # Create bridge with IPv6 configuration
        bridge_config = f"""
[NetDev]
Name=ipv6-br0
Kind=bridge

[Network]
DHCP=no
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes

[IPv6Address]
Address={ipv6_subnet}
Gateway={gateway}
"""
        
        config_file = f"{self.network_dir}/ipv6-br0.network"
        with open(config_file, 'w') as f:
            f.write(bridge_config)
        
        # Restart systemd-networkd to apply changes
        subprocess.run(['systemctl', 'restart', 'systemd-networkd'], check=True)
        
        return "Native IPv6 networking configured"
    
    def _setup_6in4_tunnel(self, config: Dict) -> str:
        """Setup 6in4 tunnel networking"""
        tunnel_server = config.get('tunnel_server')
        tunnel_client = config.get('tunnel_client')
        tunnel_ipv6 = config.get('tunnel_ipv6')
        
        if not all([tunnel_server, tunnel_client, tunnel_ipv6]):
            raise ValueError("tunnel_server, tunnel_client, and tunnel_ipv6 are required for 6in4 setup")
        
        # Create tunnel configuration
        tunnel_config = f"""
[NetDev]
Name=tun6in4
Kind=sit

[Tunnel]
Local={tunnel_client}
Remote={tunnel_server}
TTL=64

[Network]
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes

[Address]
Address={tunnel_ipv6}
"""
        
        config_file = f"{self.network_dir}/6in4-tunnel.network"
        with open(config_file, 'w') as f:
            f.write(tunnel_config)
        
        # Restart systemd-networkd to apply changes
        subprocess.run(['systemctl', 'restart', 'systemd-networkd'], check=True)
        
        return "6in4 tunnel networking configured"
    
    def _setup_wireguard_tunnel(self, config: Dict) -> str:
        """Setup WireGuard tunnel networking"""
        private_key = config.get('private_key')
        public_key = config.get('public_key')
        endpoint = config.get('endpoint')
        address = config.get('address')
        
        if not all([private_key, public_key, endpoint, address]):
            raise ValueError("private_key, public_key, endpoint, and address are required for WireGuard setup")
        
        # Create directory if it doesn't exist
        wg_dir = "/etc/wireguard"
        os.makedirs(wg_dir, exist_ok=True)
        
        # Create WireGuard configuration
        wg_config = f"""
[Interface]
PrivateKey = {private_key}
Address = {address}

[Peer]
PublicKey = {public_key}
AllowedIPs = ::/0
Endpoint = {endpoint}
PersistentKeepalive = 25
"""
        
        config_file = f"{wg_dir}/wg0.conf"
        with open(config_file, 'w') as f:
            f.write(wg_config)
        
        # Set proper permissions
        os.chmod(config_file, 0o600)
        
        # Enable and start WireGuard
        subprocess.run(['systemctl', 'enable', 'wg-quick@wg0'], check=True)
        subprocess.run(['systemctl', 'start', 'wg-quick@wg0'], check=True)
        
        return "WireGuard tunnel networking configured"
    
    def setup_ssh(self, container_name: str, ssh_config: Dict) -> str:
        """Setup SSH inside a container"""
        # This would customize SSH configuration within the container
        container_path = f"{self.machines_dir}/{container_name}"
        ssh_dir = f"{container_path}/etc/ssh"
        
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o755, exist_ok=True)
        
        # Setup SSH authorized keys if provided
        authorized_keys = ssh_config.get('authorized_keys')
        if authorized_keys:
            ssh_user = ssh_config.get('user', 'root')
            user_home = f"{container_path}/root" if ssh_user == 'root' else f"{container_path}/home/{ssh_user}"
            
            # Create .ssh directory for the user
            user_ssh_dir = f"{user_home}/.ssh"
            os.makedirs(user_ssh_dir, mode=0o700, exist_ok=True)
            
            # Write authorized keys
            auth_keys_file = f"{user_ssh_dir}/authorized_keys"
            with open(auth_keys_file, 'w') as f:
                f.write('\n'.join(authorized_keys) + '\n')
            
            # Set proper permissions
            os.chmod(auth_keys_file, 0o600)
            os.chmod(user_ssh_dir, 0o700)
            
            # Change ownership to the SSH user
            uid = pwd.getpwnam(ssh_user).pw_uid
            os.chown(user_ssh_dir, uid, -1)
            os.chown(auth_keys_file, uid, -1)
        
        # Additional SSH configuration could be added here
        return f"SSH configured for container {container_name}"