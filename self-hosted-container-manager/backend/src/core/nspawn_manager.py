from pathlib import Path
import subprocess
import json

class NspawnManager:
    def __init__(self, container_name):
        self.container_name = container_name
        self.container_path = Path(f"/var/lib/machines/{container_name}")

    def create_container(self, template_path):
        subprocess.run(["systemd-nspawn", "--register", "--directory", str(self.container_path), "--template", template_path])

    def start_container(self):
        subprocess.run(["systemd-nspawn", "-D", str(self.container_path), "--boot"])

    def stop_container(self):
        subprocess.run(["systemctl", "stop", f"machine-{self.container_name}.scope"])

    def remove_container(self):
        subprocess.run(["machinectl", "remove", self.container_name])

    def exec_command(self, command):
        subprocess.run(["systemd-nspawn", "-D", str(self.container_path)] + command)

    def get_logs(self):
        log_path = self.container_path / "var/log/syslog"
        with open(log_path, 'r') as log_file:
            return log_file.readlines()

    def setup_networking(self, network_config):
        with open(self.container_path / "etc/systemd/network/10-static.network", 'w') as net_file:
            net_file.write("[Match]\nName=eth0\n\n[Network]\nAddress={}\nNetmask={}\nGateway={}\n".format(
                network_config['address'], network_config['netmask'], network_config['gateway']
            ))
        subprocess.run(["systemctl", "restart", "systemd-networkd"])

    def setup_ssh(self):
        subprocess.run(["systemctl", "enable", "ssh"], cwd=str(self.container_path))
        subprocess.run(["systemctl", "start", "ssh"], cwd=str(self.container_path))

    def dual_stack_networking(self, ipv4_config, ipv6_config):
        self.setup_networking(ipv4_config)
        self.setup_networking(ipv6_config)

    def docker_in_container(self):
        self.exec_command(["apt-get", "install", "-y", "docker.io"])
        self.exec_command(["systemctl", "start", "docker"])