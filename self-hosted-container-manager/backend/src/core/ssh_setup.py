import os
import subprocess

def setup_ssh(container_name, ssh_port=22):
    container_path = f"/var/lib/machines/{container_name}"

    # Check if the container exists
    if not os.path.exists(container_path):
        raise FileNotFoundError(f"Container {container_name} does not exist.")

    # Install OpenSSH server in the container
    subprocess.run(["systemd-nspawn", "-M", container_name, "--", "apt", "update"], check=True)
    subprocess.run(["systemd-nspawn", "-M", container_name, "--", "apt", "install", "-y", "openssh-server"], check=True)

    # Configure SSH to listen on the specified port
    sshd_config_path = os.path.join(container_path, "etc/ssh/sshd_config")
    with open(sshd_config_path, "a") as sshd_config:
        sshd_config.write(f"\nPort {ssh_port}\n")

    # Start the SSH service in the container
    subprocess.run(["systemd-nspawn", "-M", container_name, "--", "systemctl", "enable", "ssh"], check=True)
    subprocess.run(["systemd-nspawn", "-M", container_name, "--", "systemctl", "start", "ssh"], check=True)

    print(f"SSH setup completed for container {container_name} on port {ssh_port}.")