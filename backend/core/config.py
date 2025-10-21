"""
Configuration management for ZenithStack
"""

import os
from pathlib import Path
from typing import Optional

class Settings:
    """Application settings and configuration"""
    
    # Application settings
    APP_NAME: str = "ZenithStack"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("ZENITH_DEBUG", "false").lower() == "true"
    
    # Server settings
    HOST: str = os.getenv("ZENITH_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("ZENITH_PORT", "8080"))
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = Path(os.getenv("ZENITH_DATA_DIR", "/var/lib/zenithstack"))
    LOG_DIR: Path = Path(os.getenv("ZENITH_LOG_DIR", "/var/log/zenithstack"))
    CONFIG_DIR: Path = Path(os.getenv("ZENITH_CONFIG_DIR", "/etc/zenithstack"))
    
    # Container settings
    MACHINES_DIR: Path = Path("/var/lib/machines")
    NSPAWN_CONFIG_DIR: Path = Path("/etc/systemd/nspawn")
    
    # Network settings
    DEFAULT_BRIDGE: str = "br0"
    IPV4_SUBNET: str = "10.0.0.0/24"
    IPV4_GATEWAY: str = "10.0.0.1"
    IPV6_PREFIX: Optional[str] = os.getenv("ZENITH_IPV6_PREFIX", None)
    
    # Resource limits defaults
    DEFAULT_CPU_QUOTA: int = 100  # 100% = 1 CPU core
    DEFAULT_MEMORY_MB: int = 512
    DEFAULT_DISK_GB: int = 10
    
    # Security settings
    SECRET_KEY: str = os.getenv("ZENITH_SECRET_KEY", "change-me-in-production")
    ADMIN_USERNAME: str = os.getenv("ZENITH_ADMIN_USER", "admin")
    ADMIN_PASSWORD_HASH: str = os.getenv("ZENITH_ADMIN_PASSWORD_HASH", "")
    
    # Database settings
    DATABASE_URL: str = os.getenv("ZENITH_DATABASE_URL", f"sqlite:///{DATA_DIR}/zenithstack.db")
    
    # DNS settings
    DNS_SERVERS: list = ["8.8.8.8", "1.1.1.1"]
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist"""
        for directory in [cls.DATA_DIR, cls.LOG_DIR, cls.CONFIG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

settings = Settings()
