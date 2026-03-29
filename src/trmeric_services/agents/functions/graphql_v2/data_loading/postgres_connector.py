"""
PostgreSQL Connector

Manages PostgreSQL database connections for fetching project/roadmap data.
"""

import os
import psycopg2
from dataclasses import dataclass
from typing import Optional
from contextlib import contextmanager


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration."""
    host: str
    database: str
    user: str
    password: str
    port: str = "5432"
    
    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "trmeric-dev"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            port=os.getenv("DB_PORT", "5432"),
        )


class PostgresConnector:
    """
    PostgreSQL database connector.
    
    Provides connection management and context managers for safe resource handling.
    """
    
    def __init__(self, config: PostgresConfig):
        """
        Initialize PostgreSQL connector.
        
        Args:
            config: PostgreSQL configuration
        """
        self.config = config
        self._connection: Optional[psycopg2.extensions.connection] = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """
        Establish connection to PostgreSQL.
        
        Returns:
            PostgreSQL connection object
            
        Raises:
            Exception: If connection fails
        """
        try:
            self._connection = psycopg2.connect(
                host=self.config.host,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
            print(f"Connected to PostgreSQL: {self.config.database}")
            return self._connection
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def disconnect(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            print("Disconnected from PostgreSQL")
            self._connection = None
    
    @contextmanager
    def cursor(self):
        """
        Context manager for database cursor.
        
        Yields:
            Database cursor
            
        Example:
            with connector.cursor() as cursor:
                cursor.execute("SELECT * FROM projects")
                results = cursor.fetchall()
        """
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            raise
        finally:
            cursor.close()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
