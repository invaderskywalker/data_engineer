"""
Configuration Management for GraphQL V2

Centralized configuration to avoid hardcoded values throughout the codebase.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class GraphConnectorConfig:
    """TigerGraph connection configuration"""
    host: str
    username: str
    password: str
    restpp_port: int
    secret: str
    graphname: str = ""
    
    
    @classmethod
    def from_env(cls, graphname: str = "") -> "GraphConnectorConfig":
        """Load TigerGraph configuration from environment variables."""
        if not graphname:
            raise ValueError("graphname is required and cannot be empty")
        
        # All configuration must come from environment variables
        host = os.getenv("TG_HOST")
        username = os.getenv("TG_USERNAME")
        password = os.getenv("TG_PASSWORD")
        restpp_port = os.getenv("TG_RESTPP_PORT")
        # TG_SECRET is optional for community/local installs; default to empty string
        secret = os.getenv("TG_SECRET", "")
        
        # Validate required environment variables
        if not host:
            raise ValueError("TG_HOST environment variable is required")
        if not username:
            raise ValueError("TG_USERNAME environment variable is required")
        if not password:
            raise ValueError("TG_PASSWORD environment variable is required")
        if not restpp_port:
            raise ValueError("TG_RESTPP_PORT environment variable is required")
        # if not secret:
        #     raise ValueError("TG_SECRET environment variable is required")
        
        return cls(
            host=host,
            username=username,
            password=password,
            restpp_port=int(restpp_port),
            secret=secret,
            graphname=graphname,
        )


@dataclass
class AgentConfig:
    """General agent configuration"""
    batch_size: int = 5
    enable_privacy_filtering: bool = True
    default_timeout: int = 30  # seconds
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Return agent config (uses legacy defaults)."""
        return cls(
            batch_size=5,
            enable_privacy_filtering=True,
            default_timeout=30,
        )
