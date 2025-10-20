from typing import List, Dict
import subprocess
import json

class NetworkManager:
    def __init__(self):
        self.containers = {}

    def add_container(self, container_id: str, ip_address: str):
        self.containers[container_id] = ip_address

    def remove_container(self, container_id: str):
        if container_id in self.containers:
            del self.containers[container_id]

    def configure_network(self, container_id: str, ipv4: str, ipv6: str):
        # Example command to configure networking for a container
        command = f"ip netns exec {container_id} ip addr add {ipv4}/24 dev eth0"
        subprocess.run(command, shell=True)
        command = f"ip netns exec {container_id} ip -6 addr add {ipv6}/64 dev eth0"
        subprocess.run(command, shell=True)

    def get_network_info(self) -> Dict[str, str]:
        return self.containers

    def log_network_activity(self, container_id: str, activity: str):
        log_entry = {
            "container_id": container_id,
            "activity": activity
        }
        with open("network_activity.log", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")