#!/usr/bin/env python3

"""
Utility script for nspawn-ui container management
"""

import subprocess
import json
import os
import sys
from pathlib import Path

def run_command(cmd, capture_output=True, check=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e.stderr}")
        return None

def list_machines():
    """List all systemd-nspawn machines"""
    result = run_command("machinectl list --no-legend --no-pager")
    if result:
        machines = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                # Parse machinectl output (name status since cpu memory)
                parts = line.split()
                if len(parts) >= 2:
                    machines.append({
                        'name': parts[0],
                        'status': parts[1]
                    })
        return machines
    return []

def create_container(name, distro="debian", root_password=None):
    """Create a new container"""
    # Define base path for containers
    machines_path = "/var/lib/machines"
    container_path = f"{machines_path}/{name}"
    
    # Create directory if it doesn't exist
    os.makedirs(machines_path, exist_ok=True)
    
    # Validate distro
    valid_distros = ["debian", "ubuntu", "centos", "fedora", "arch"]
    if distro not in valid_distros:
        print(f"Invalid distro: {distro}. Valid options: {', '.join(valid_distros)}")
        return False
    
    # Create container with debootstrap
    if distro in ["debian", "ubuntu"]:
        cmd = f"debootstrap --variant=minbase {distro} {container_path}"
    elif distro in ["centos", "fedora"]:
        cmd = f"yum --releasever=latest --installroot={container_path} --nogpgcheck -y groupinstall minimal"
    else:
        print(f"Distro {distro} not yet supported in this utility")
        return False
    
    print(f"Creating container {name} with distro {distro}...")
    result = run_command(cmd)
    if not result:
        return False
    
    # Set root password if provided
    if root_password:
        password_cmd = f'chroot {container_path} /bin/bash -c "echo root:{root_password} | chpasswd"'
        result = run_command(password_cmd)
        if not result:
            print("Failed to set root password")
            return False
    
    # Basic network setup
    network_cmd = f'chroot {container_path} /bin/bash -c "echo nameserver 8.8.8.8 > /etc/resolv.conf"'
    run_command(network_cmd)  # This is non-critical, so we don't check result
    
    print(f"Container {name} created successfully!")
    return True

def start_container(name):
    """Start a container"""
    cmd = f"machinectl start {name}"
    result = run_command(cmd)
    if result:
        print(f"Container {name} started successfully!")
        return True
    return False

def stop_container(name):
    """Stop a container"""
    cmd = f"machinectl stop {name}"
    result = run_command(cmd)
    if result:
        print(f"Container {name} stopped successfully!")
        return True
    return False

def remove_container(name):
    """Remove a container"""
    cmd = f"machinectl remove {name}"
    result = run_command(cmd)
    if result:
        print(f"Container {name} removed successfully!")
        return True
    return False

def get_container_logs(name):
    """Get logs for a container"""
    cmd = f"machinectl status {name}"
    result = run_command(cmd)
    if result:
        print(result.stdout)
        return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 utils.py <command> [args]")
        print("Commands:")
        print("  list                    - List all containers")
        print("  create <name> [distro] [password] - Create a new container")
        print("  start <name>           - Start a container")
        print("  stop <name>            - Stop a container")
        print("  remove <name>          - Remove a container")
        print("  logs <name>            - Show container logs")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        machines = list_machines()
        print(f"{'Name':<20} {'Status':<10}")
        print("-" * 30)
        for machine in machines:
            print(f"{machine['name']:<20} {machine['status']:<10}")
    
    elif command == "create":
        if len(sys.argv) < 3:
            print("Usage: python3 utils.py create <name> [distro] [password]")
            return
        
        name = sys.argv[2]
        distro = sys.argv[3] if len(sys.argv) > 3 else "debian"
        password = sys.argv[4] if len(sys.argv) > 4 else None
        
        create_container(name, distro, password)
    
    elif command == "start":
        if len(sys.argv) < 3:
            print("Usage: python3 utils.py start <name>")
            return
        
        name = sys.argv[2]
        start_container(name)
    
    elif command == "stop":
        if len(sys.argv) < 3:
            print("Usage: python3 utils.py stop <name>")
            return
        
        name = sys.argv[2]
        stop_container(name)
    
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: python3 utils.py remove <name>")
            return
        
        name = sys.argv[2]
        remove_container(name)
    
    elif command == "logs":
        if len(sys.argv) < 3:
            print("Usage: python3 utils.py logs <name>")
            return
        
        name = sys.argv[2]
        get_container_logs(name)
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()