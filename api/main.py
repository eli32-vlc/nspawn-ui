import asyncio
import ipaddress
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="CT Manager API", version="0.2.0")

# Paths and defaults
APP_DIR = Path("/opt/ctmgr")
STATE_DIR = APP_DIR / "state"
CONFIG_PATH = APP_DIR / "config.json"
MACHINES_DIR = Path("/var/lib/machines")
NSPAWN_DIR = Path("/etc/systemd/nspawn")
WEB_DIR = Path(os.getenv("CTMGR_WEB_DIR", "/opt/ctmgr/web"))

DEFAULT_CONFIG = {
    "bridge": "br0",
    "lan4_cidr": "192.168.100.0/24",
    "lan4_gw": "192.168.100.1",
    "wan_iface": "",
    "ipv6_prefix": "",  # example: "2001:db8:abcd:100::/64"
    "nat_backend": "nftables",  # nftables | iptables
    "enable_ndppd": False,
    "ndppd_iface": "",  # upstream iface for proxy, if needed
}

PORTMAPS_PATH = STATE_DIR / "portmaps.json"       # IPv4 DNAT mappings
IPV6_ACLS_PATH = STATE_DIR / "ipv6-acls.json"     # IPv6 inbound ACLs

# Ensure dirs exist
for p in (APP_DIR, STATE_DIR, NSPAWN_DIR, MACHINES_DIR):
    p.mkdir(parents=True, exist_ok=True)

# Static UI mount (/ui -> index.html)
if WEB_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")


# ------------------ Utilities ------------------

def run_cmd(cmd: List[str], check: bool = True) -> str:
    try:
        res = subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}")


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def get_config() -> Dict[str, Any]:
    cfg = load_json(CONFIG_PATH, DEFAULT_CONFIG)
    # Backfill defaults for newly added keys
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    save_json(CONFIG_PATH, cfg)


def machine_exists(name: str) -> bool:
    return (MACHINES_DIR / name).exists()


def get_container_state(name: str) -> str:
    try:
        out = run_cmd(["machinectl", "show", name, "-p", "State"])
        m = re.search(r"State=(\w+)", out)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


def get_container_ips(name: str) -> List[str]:
    ips: List[str] = []
    try:
        out = run_cmd(["machinectl", "status", name])
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Address: "):
                val = line.split("Address: ", 1)[1].strip()
                if val and val not in ips:
                    ips.append(val)
    except Exception:
        pass
    return ips


def write_nspawn_file(name: str, bridge: str, enable_docker_sock: bool, nested: bool) -> None:
    lines = []
    lines.append("[Exec]")
    if nested:
        lines.append("PrivateUsers=keep")
        lines.append("Capability=all")
    lines.append("")
    lines.append("[Network]")
    lines.append(f"Bridge={bridge}")
    lines.append("")
    if enable_docker_sock:
        lines.append("[Files]")
        lines.append("Bind=/var/run/docker.sock")
        lines.append("")
    content = "\n".join(lines) + "\n"
    (NSPAWN_DIR / f"{name}.nspawn").write_text(content)


def debootstrap_container(name: str, distro: str, release: str) -> None:
    root = MACHINES_DIR / name
    root.mkdir(parents=True, exist_ok=True)
    if distro.lower() == "debian":
        mirror = "http://deb.debian.org/debian"
    elif distro.lower() == "ubuntu":
        mirror = "http://ports.ubuntu.com/ubuntu-ports"
    else:
        raise RuntimeError("Unsupported distro. Use 'debian' or 'ubuntu'.")
    run_cmd(["debootstrap", "--arch=amd64", release, str(root), mirror])
    baseline_container_network(name)


def import_tarball_container(name: str, tar_url_or_path: str) -> None:
    root = MACHINES_DIR / name
    root.mkdir(parents=True, exist_ok=True)
    # Support local file or URL
    if re.match(r"^https?://", tar_url_or_path):
        tmp = Path("/tmp") / f"{name}.tar"
        run_cmd(["curl", "-L", "-o", str(tmp), tar_url_or_path])
        run_cmd(["tar", "-C", str(root), "-xf", str(tmp)])
        tmp.unlink(missing_ok=True)
    else:
        run_cmd(["tar", "-C", str(root), "-xf", tar_url_or_path])
    baseline_container_network(name)


def baseline_container_network(name: str) -> None:
    root = MACHINES_DIR / name
    # hostname
    (root / "etc/hostname").write_text(f"{name}\n")
    # resolv.conf
    resolv_src = Path("/etc/resolv.conf")
    if resolv_src.exists():
        shutil.copy2(resolv_src, root / "etc/resolv.conf")
    # networkd DHCPv4 + IPv6 RA
    network_dir = root / "etc/systemd/network"
    network_dir.mkdir(parents=True, exist_ok=True)
    network_conf = """[Match]
Name=host0

[Network]
DHCP=yes
IPv6AcceptRA=yes
"""
    (network_dir / "20-host0.network").write_text(network_conf)
    # Enable services
    run_cmd(["systemd-nspawn", "-D", str(root), "systemctl", "enable", "systemd-networkd"])


def set_root_password(name: str, password: str) -> None:
    root = MACHINES_DIR / name
    cmd = [
        "systemd-nspawn", "-D", str(root), "bash", "-lc",
        f"echo 'root:{password.replace(\"'\", \"'\\''\")}' | chpasswd",
    ]
    run_cmd(cmd)


def install_ssh(name: str) -> None:
    root = MACHINES_DIR / name
    run_cmd(["systemd-nspawn", "-D", str(root), "bash", "-lc", "apt-get update"])
    run_cmd(["systemd-nspawn", "-D", str(root), "bash", "-lc", "DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server"])
    run_cmd([
        "systemd-nspawn", "-D", str(root), "bash", "-lc",
        "sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config",
    ])
    run_cmd(["systemd-nspawn", "-D", str(root), "bash", "-lc", "systemctl enable ssh"])


def machinectl_action(action: str, name: str) -> None:
    if action not in ("start", "poweroff", "reboot", "terminate"):
        raise ValueError("Invalid action")
    run_cmd(["machinectl", action, name])


def enable_autostart(name: str, enabled: bool) -> None:
    unit = f"systemd-nspawn@{name}.service"
    if enabled:
        run_cmd(["systemctl", "enable", unit])
    else:
        run_cmd(["systemctl", "disable", unit])


def update_container_network_file(name: str, static_ipv4: Optional[str], static_ipv6: Optional[str]) -> None:
    root = MACHINES_DIR / name
    net_file = root / "etc/systemd/network/20-host0.network"
    content = ["[Match]\nName=host0\n\n[Network]"]
    # IPv4
    if static_ipv4:
        ipaddress.IPv4Interface(static_ipv4)  # validate
        content.append(f"Address={static_ipv4}")
        content.append("DHCP=no")
    else:
        content.append("DHCP=yes")
    # IPv6
    if static_ipv6:
        ipaddress.IPv6Interface(static_ipv6)
        content.append(f"Address={static_ipv6}")
        content.append("IPv6AcceptRA=no")
    else:
        content.append("IPv6AcceptRA=yes")
    net_file.write_text("\n".join(content) + "\n")


def get_ct_ipv4(name: str) -> Optional[str]:
    ips = get_container_ips(name)
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip.split("/")[0]) if "/" in ip else ipaddress.ip_address(ip)
            if isinstance(addr, ipaddress.IPv4Address):
                return str(addr)
        except Exception:
            continue
    return None


# ------------------ Models ------------------

class CreateContainerRequest(BaseModel):
    name: str
    method: Literal["debootstrap", "import"] = "debootstrap"
    # debootstrap
    distro: str = "debian"
    release: str = "bookworm"
    # tarball import
    tarball: Optional[str] = None
    root_password: str
    enable_ssh: bool = True
    enable_docker_sock: bool = False
    nested: bool = True
    autostart: bool = False


class NetworkUpdateRequest(BaseModel):
    static_ipv4: Optional[str] = Field(None, description="CIDR, e.g., 192.168.100.10/24")
    static_ipv6: Optional[str] = Field(None, description="CIDR, e.g., 2001:db8:abcd:100::10/64")
    bridge: Optional[str] = None
    restart: bool = False


class NATBackendRequest(BaseModel):
    backend: Literal["iptables", "nftables"]


class PortMapRequest(BaseModel):
    action: Literal["add", "remove"]
    name: str
    protocol: Literal["tcp", "udp"] = "tcp"
    host_port: int
    ct_port: int
    # Optional override, otherwise we detect ct IPv4
    ct_ip: Optional[str] = None


class IPv6ACLRequest(BaseModel):
    action: Literal["add", "remove"]
    name: str
    protocol: Literal["tcp", "udp"] = "tcp"
    dport: int
    ct_ipv6: Optional[str] = None


class IPv6NativeConfig(BaseModel):
    ipv6_prefix: str  # e.g., 2001:db8:abcd:100::/64


class Setup6in4Request(BaseModel):
    local_ipv4: str
    server_ipv4: str
    client_ipv6: str    # your tunnel endpoint v6
    server_ipv6: str    # HE server v6
    routed_prefix: str  # your routed /64 or larger


class SetupWireGuardRequest(BaseModel):
    interface: str = "wg0"
    config: str        # full wg-quick config contents
    routed_prefix: str


# ------------------ API: Containers ------------------

@app.get("/api/containers")
def list_containers():
    out = run_cmd(["machinectl", "list", "--no-legend", "--no-pager"])
    containers = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        name = parts[0]
        state = get_container_state(name)
        ips = get_container_ips(name)
        containers.append({"name": name, "state": state, "ips": ips})
    return {"containers": containers}


@app.post("/api/containers")
def create_container(req: CreateContainerRequest):
    name = req.name.strip()
    if not name or not re.match(r"^[a-zA-Z0-9_.-]+$", name):
        raise HTTPException(status_code=400, detail="Invalid container name")
    if machine_exists(name):
        raise HTTPException(status_code=409, detail="Container already exists")

    cfg = get_config()
    try:
        if req.method == "debootstrap":
            debootstrap_container(name, req.distro, req.release)
        elif req.method == "import":
            if not req.tarball:
                raise HTTPException(status_code=400, detail="tarball is required for method=import")
            import_tarball_container(name, req.tarball)
        else:
            raise HTTPException(status_code=400, detail="Unsupported method")

        write_nspawn_file(name, cfg["bridge"], req.enable_docker_sock, req.nested)
        set_root_password(name, req.root_password)
        if req.enable_ssh:
            install_ssh(name)
        if req.autostart:
            enable_autostart(name, True)
        return {"status": "created", "name": name}
    except Exception as e:
        # Cleanup on failure
        try:
            shutil.rmtree(MACHINES_DIR / name, ignore_errors=True)
            f = NSPAWN_DIR / f"{name}.nspawn"
            if f.exists():
                f.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/start")
def start_container(name: str):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        machinectl_action("start", name)
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/stop")
def stop_container(name: str):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        machinectl_action("poweroff", name)
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/restart")
def restart_container(name: str):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        machinectl_action("reboot", name)
        return {"status": "restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/containers/{name}")
def delete_container(name: str):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        state = get_container_state(name)
        if state == "running":
            machinectl_action("poweroff", name)
        shutil.rmtree(MACHINES_DIR / name, ignore_errors=True)
        f = NSPAWN_DIR / f"{name}.nspawn"
        if f.exists():
            f.unlink()
        # Also remove autostart symlink
        try:
            enable_autostart(name, False)
        except Exception:
            pass
        # Remove any port mappings / ACLs for this CT
        remove_ct_from_portmaps_and_acls(name)
        apply_firewall()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/ssh/setup")
def setup_ssh(name: str, req: Dict[str, Optional[str]]):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        install_ssh(name)
        if req and req.get("root_password"):
            set_root_password(name, req["root_password"] or "")
        return {"status": "ssh_configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/autostart")
def set_autostart(name: str, enabled: bool = Body(..., embed=True)):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        enable_autostart(name, enabled)
        return {"status": "ok", "enabled": enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{name}/network")
def update_container_network(name: str, req: NetworkUpdateRequest):
    if not machine_exists(name):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        if req.bridge:
            nspawn_file = NSPAWN_DIR / f"{name}.nspawn"
            if not nspawn_file.exists():
                write_nspawn_file(name, req.bridge, False, True)
            else:
                txt = nspawn_file.read_text()
                txt = re.sub(r"(?m)^\s*Bridge=.*$", f"Bridge={req.bridge}", txt) if "Bridge=" in txt else txt + f"\n[Network]\nBridge={req.bridge}\n"
                nspawn_file.write_text(txt)
        update_container_network_file(name, req.static_ipv4, req.static_ipv6)
        if req.restart:
            try:
                machinectl_action("poweroff", name)
            except Exception:
                pass
            machinectl_action("start", name)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------ API: Networking and Firewall ------------------

@app.get("/api/network/config")
def get_network_config():
    cfg = get_config()
    return cfg


@app.post("/api/network/config")
def set_network_config(cfg_partial: Dict[str, Any]):
    cfg = get_config()
    cfg.update({k: v for k, v in cfg_partial.items() if k in DEFAULT_CONFIG})
    save_config(cfg)
    # Apply IPv6 RA prefix on br0 if provided
    if cfg.get("ipv6_prefix"):
        set_br0_ipv6_prefix(cfg["ipv6_prefix"])
    return {"status": "ok", "config": cfg}


def set_br0_ipv6_prefix(prefix: str):
    # Configure systemd-networkd RA on br0
    net = Path("/etc/systemd/network/10-br0.network")
    text = net.read_text() if net.exists() else "[Match]\nName=br0\n\n[Network]\n"
    if "IPv6SendRA=" in text:
        text = re.sub(r"(?m)^IPv6SendRA=.*$", "IPv6SendRA=yes", text)
    else:
        text = text.replace("[Network]\n", "[Network]\nIPv6SendRA=yes\n")
    # Inject or replace [IPv6Prefix]
    if "[IPv6Prefix]" in text:
        text = re.sub(r"(?ms)\[IPv6Prefix\].*?Prefix=.*?\n", f"[IPv6Prefix]\nPrefix={prefix}\n", text)
    else:
        text += f"\n[IPv6Prefix]\nPrefix={prefix}\n"
    net.write_text(text)
    run_cmd(["systemctl", "restart", "systemd-networkd"])


@app.post("/api/network/nat/backend")
def switch_nat_backend(req: NATBackendRequest):
    cfg = get_config()
    cfg["nat_backend"] = req.backend
    save_config(cfg)
    apply_firewall()
    return {"status": "ok", "backend": req.backend}


@app.post("/api/network/ports")
def manage_portmap(req: PortMapRequest):
    if not machine_exists(req.name):
        raise HTTPException(status_code=404, detail="Container not found")
    if req.action == "add":
        # resolve ct_ip if not provided
        ct_ip = req.ct_ip or get_ct_ipv4(req.name)
        if not ct_ip:
            raise HTTPException(status_code=400, detail="Container IPv4 not found; start container or specify ct_ip")
        # persist
        maps = load_json(PORTMAPS_PATH, [])
        # idempotent: remove duplicates
        maps = [m for m in maps if not (m["protocol"] == req.protocol and m["host_port"] == req.host_port)]
        maps.append({"name": req.name, "protocol": req.protocol, "host_port": req.host_port, "ct_port": req.ct_port, "ct_ip": ct_ip})
        save_json(PORTMAPS_PATH, maps)
    else:
        maps = load_json(PORTMAPS_PATH, [])
        maps = [m for m in maps if not (m["protocol"] == req.protocol and m["host_port"] == req.host_port)]
        save_json(PORTMAPS_PATH, maps)
    apply_firewall()
    return {"status": "ok", "portmaps": load_json(PORTMAPS_PATH, [])}


@app.post("/api/network/ipv6-acl")
def manage_ipv6_acl(req: IPv6ACLRequest):
    if not machine_exists(req.name):
        raise HTTPException(status_code=404, detail="Container not found")
    if req.ct_ipv6:
        try:
            ipaddress.IPv6Address(req.ct_ipv6)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ct_ipv6")
    acls = load_json(IPV6_ACLS_PATH, [])
    if req.action == "add":
        if not req.ct_ipv6:
            # Try to find a v6 address
            v6 = None
            for ip in get_container_ips(req.name):
                try:
                    addr = ipaddress.ip_address(ip.split("/")[0]) if "/" in ip else ipaddress.ip_address(ip)
                    if isinstance(addr, ipaddress.IPv6Address):
                        v6 = str(addr)
                        break
                except Exception:
                    pass
            if not v6:
                raise HTTPException(status_code=400, detail="ct_ipv6 not found; specify ct_ipv6 explicitly")
            req.ct_ipv6 = v6
        # idempotent
        acls = [a for a in acls if not (a["protocol"] == req.protocol and a["dport"] == req.dport and a["ct_ipv6"] == req.ct_ipv6)]
        acls.append({"name": req.name, "protocol": req.protocol, "dport": req.dport, "ct_ipv6": req.ct_ipv6})
    else:
        acls = [a for a in acls if not (a["protocol"] == req.protocol and a["dport"] == req.dport and (not req.ct_ipv6 or a["ct_ipv6"] == req.ct_ipv6))]
    save_json(IPV6_ACLS_PATH, acls)
    apply_firewall()
    return {"status": "ok", "ipv6_acls": load_json(IPV6_ACLS_PATH, [])}


def current_wan_iface() -> str:
    cfg = get_config()
    if cfg.get("wan_iface"):
        return cfg["wan_iface"]
    # try detect
    out = run_cmd(["ip", "route", "show", "default"])
    m = re.search(r"default via [^ ]+ dev (\S+)", out)
    if m:
        cfg["wan_iface"] = m.group(1)
        save_config(cfg)
        return cfg["wan_iface"]
    return ""


def apply_firewall():
    cfg = get_config()
    if cfg["nat_backend"] == "nftables":
        render_nft_rules(cfg)
        # Apply
        run_cmd(["nft", "-f", "/etc/nftables.d/ctmgr.nft"])
        # Ensure service enabled
        run_cmd(["systemctl", "enable", "--now", "ctmgr-nft-apply.service"])
        # Disable iptables nat unit if exists
        run_cmd(["systemctl", "disable", "--now", "ctmgr-nat.service"], check=False)
    else:
        # iptables: ensure masquerade and DNAT rules
        ensure_iptables_nat(cfg)
        # Disable nft apply
        run_cmd(["systemctl", "disable", "--now", "ctmgr-nft-apply.service"], check=False)


def ensure_iptables_nat(cfg: Dict[str, Any]):
    wan = current_wan_iface()
    lan = cfg["lan4_cidr"]
    # Masquerade
    run_cmd(["iptables", "-t", "nat", "-C", "POSTROUTING", "-s", lan, "-o", wan, "-j", "MASQUERADE"], check=False)
    if subprocess.call(["iptables", "-t", "nat", "-C", "POSTROUTING", "-s", lan, "-o", wan, "-j", "MASQUERADE"]) != 0:
        run_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", lan, "-o", wan, "-j", "MASQUERADE"])
    # DNAT port maps
    maps = load_json(PORTMAPS_PATH, [])
    for m in maps:
        rule = ["-t", "nat", "-C", "PREROUTING", "-p", m["protocol"], "--dport", str(m["host_port"]), "-j", "DNAT", "--to-destination", f"{m['ct_ip']}:{m['ct_port']}"]
        if subprocess.call(["iptables"] + rule) != 0:
            run_cmd(["iptables", "-t", "nat", "-A", "PREROUTING", "-p", m["protocol"], "--dport", str(m["host_port"]), "-j", "DNAT", "--to-destination", f"{m['ct_ip']}:{m['ct_port']}"])
        # Accept forward
        fwd_rule = ["-C", "FORWARD", "-p", m["protocol"], "-d", m["ct_ip"], "--dport", str(m["ct_port"]), "-j", "ACCEPT"]
        if subprocess.call(["iptables"] + fwd_rule) != 0:
            run_cmd(["iptables", "-A", "FORWARD", "-p", m["protocol"], "-d", m["ct_ip"], "--dport", str(m["ct_port"]), "-j", "ACCEPT"])


def render_nft_rules(cfg: Dict[str, Any]):
    # Build nftables config with IPv4 NAT and IPv6 ACLs (forward policy drop)
    wan = current_wan_iface()
    br = cfg["bridge"]
    lan4 = ipaddress.ip_network(cfg["lan4_cidr"])
    maps = load_json(PORTMAPS_PATH, [])
    acls = load_json(IPV6_ACLS_PATH, [])

    lines = []
    lines.append("# Autogenerated by CT Manager")
    lines.append("flush ruleset")
    lines.append("")
    lines.append("table inet ctmgr_filter {")
    lines.append("  chain forward {")
    lines.append("    type filter hook forward priority 0; policy drop;")
    lines.append("    ct state established,related accept")
    # Allow LAN out to WAN and back
    if wan:
        lines.append(f"    iifname \"{br}\" oifname \"{wan}\" accept")
        lines.append(f"    iifname \"{wan}\" oifname \"{br}\" ct state related,established accept")
    # IPv4 DNAT accept rules
    for m in maps:
        proto = m["protocol"]
        dport = m["ct_port"]
        ct_ip = m["ct_ip"]
        lines.append(f"    ip daddr {ct_ip} {proto} dport {dport} accept")
    # IPv6 inbound ACLs
    for a in acls:
        proto = a["protocol"]
        dport = a["dport"]
        v6 = a["ct_ipv6"]
        lines.append(f"    ip6 daddr {v6} {proto} dport {dport} accept")
    # ICMPv6 is important for PMTU/ND
    lines.append("    meta l4proto ipv6-icmp accept")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("table ip ctmgr_nat {")
    lines.append("  chain prerouting { type nat hook prerouting priority -100; }")
    lines.append("  chain postrouting { type nat hook postrouting priority 100; }")
    # Masquerade for LAN to WAN
    if wan:
        lines.append(f"  chain postrouting {{")
        lines.append(f"    ip saddr {lan4.with_prefixlen} oifname \"{wan}\" masquerade")
        lines.append(f"  }}")
    # DNATs
    if maps:
        lines.append("  chain prerouting {")
        lines.append("    type nat hook prerouting priority -100;")
        for m in maps:
            proto = m["protocol"]
            host_port = m["host_port"]
            ct_ip = m["ct_ip"]
            ct_port = m["ct_port"]
            lines.append(f"    {proto} dport {host_port} dnat to {ct_ip}:{ct_port}")
        lines.append("  }")
    lines.append("}")
    Path("/etc/nftables.d").mkdir(parents=True, exist_ok=True)
    Path("/etc/nftables.d/ctmgr.nft").write_text("\n".join(lines) + "\n")


def remove_ct_from_portmaps_and_acls(name: str):
    maps = load_json(PORTMAPS_PATH, [])
    maps = [m for m in maps if m["name"] != name]
    save_json(PORTMAPS_PATH, maps)
    acls = load_json(IPV6_ACLS_PATH, [])
    acls = [a for a in acls if a["name"] != name]
    save_json(IPV6_ACLS_PATH, acls)


# ------------------ API: IPv6 methods ------------------

@app.post("/api/network/ipv6/native")
def setup_ipv6_native(cfg: IPv6NativeConfig):
    # Validate prefix
    ipaddress.IPv6Network(cfg.ipv6_prefix, strict=False)
    set_br0_ipv6_prefix(cfg.ipv6_prefix)
    conf = get_config()
    conf["ipv6_prefix"] = cfg.ipv6_prefix
    save_config(conf)
    return {"status": "ok", "ipv6_prefix": cfg.ipv6_prefix}


@app.post("/api/network/ipv6/6in4")
def setup_6in4(req: Setup6in4Request):
    # Install ifupdown if not present (non-fatal if already installed)
    run_cmd(["bash", "-lc", "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ifupdown"], check=False)
    # Write interfaces stanza
    Path("/etc/network/interfaces.d").mkdir(parents=True, exist_ok=True)
    text = f"""auto he-ipv6
iface he-ipv6 inet6 v4tunnel
  address {req.client_ipv6}
  netmask 64
  endpoint {req.server_ipv4}
  local {req.local_ipv4}
  ttl 255
  gateway {req.server_ipv6}
"""
    Path("/etc/network/interfaces.d/he-ipv6").write_text(text)
    # Bring up
    run_cmd(["ifup", "he-ipv6"])
    # Route routed prefix to br0
    run_cmd(["ip", "-6", "route", "replace", req.routed_prefix, "dev", get_config()["bridge"]])
    # Advertise prefix on br0
    set_br0_ipv6_prefix(req.routed_prefix)
    conf = get_config()
    conf["ipv6_prefix"] = req.routed_prefix
    save_config(conf)
    return {"status": "ok"}


@app.post("/api/network/ipv6/wireguard")
def setup_wireguard(req: SetupWireGuardRequest):
    # Install wireguard
    run_cmd(["bash", "-lc", "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard"], check=False)
    Path("/etc/wireguard").mkdir(parents=True, exist_ok=True)
    conf_path = Path(f"/etc/wireguard/{req.interface}.conf")
    conf_path.write_text(req.config)
    run_cmd(["systemctl", "enable", f"wg-quick@{req.interface}"])
    run_cmd(["systemctl", "restart", f"wg-quick@{req.interface}"])
    # Route routed prefix to br0
    run_cmd(["ip", "-6", "route", "replace", req.routed_prefix, "dev", get_config()["bridge"]])
    # Advertise prefix on br0
    set_br0_ipv6_prefix(req.routed_prefix)
    cfg = get_config()
    cfg["ipv6_prefix"] = req.routed_prefix
    save_config(cfg)
    return {"status": "ok"}


@app.post("/api/network/ndppd")
def setup_ndppd(enable: bool = Body(..., embed=True), upstream_iface: Optional[str] = Body(None, embed=True)):
    # Install ndppd if enabling
    cfg = get_config()
    cfg["enable_ndppd"] = enable
    if upstream_iface:
        cfg["ndppd_iface"] = upstream_iface
    save_config(cfg)
    if enable:
        run_cmd(["bash", "-lc", "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ndppd"], check=False)
        br = cfg["bridge"]
        prefix = cfg.get("ipv6_prefix", "")
        if not prefix:
            raise HTTPException(status_code=400, detail="Set ipv6_prefix first")
        text = f"""proxy {upstream_iface or 'eth0'} {{
  rule {prefix} {{
    static
    iface {br}
  }}
}}
"""
        Path("/etc/ndppd.conf").write_text(text)
        run_cmd(["systemctl", "enable", "--now", "ndppd"])
    else:
        run_cmd(["systemctl", "disable", "--now", "ndppd"], check=False)
    return {"status": "ok", "enable_ndppd": enable}


# ------------------ Logs and root ------------------

@app.get("/api/containers/{name}/logs")
def get_logs(name: str, lines: int = 200):
    if lines < 1 or lines > 5000:
        lines = 200
    try:
        out = run_cmd(["journalctl", "-M", name, "-n", str(lines), "-o", "short-iso"])
        return JSONResponse({"logs": out})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/logs/{name}")
async def ws_logs(websocket: WebSocket, name: str):
    await websocket.accept()
    proc = await asyncio.create_subprocess_exec(
        "journalctl", "-M", name, "-f", "-n", "50", "-o", "short-iso",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                await asyncio.sleep(0.2)
                continue
            await websocket.send_text(line.decode(errors="ignore"))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass


@app.get("/")
def root_redirect():
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "CT Manager API is running. UI not found."}
