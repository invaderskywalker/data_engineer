from enum import Enum
from typing import Set


class PrivacyScope(Enum):
    """Privacy tiers for data access control"""
    PUBLIC = "public"      # Anonymized cross-tenant data
    PRIVATE = "private"    # Full access to own tenant data


class PrivacyConfig:
    """Configuration for privacy-aware field filtering"""
    
    def __init__(
        self,
        public_fields: Set[str] = None,
        private_fields: Set[str] = None,
        anonymized_fields: Set[str] = None
    ):
        """
        Args:
            public_fields: Fields visible in PUBLIC scope
            private_fields: Fields only visible in PRIVATE scope
            anonymized_fields: Fields that need anonymization in PUBLIC scope
        """
        self.public_fields = public_fields or set()
        self.private_fields = private_fields or set()
        self.anonymized_fields = anonymized_fields or set()
    
    def get_allowed_fields(self, scope: PrivacyScope) -> Set[str]:
        """Get fields allowed for the given privacy scope"""
        if scope == PrivacyScope.PRIVATE:
            return self.public_fields | self.private_fields
        else:  # PUBLIC
            return self.public_fields
    
    def needs_anonymization(self, field: str, scope: PrivacyScope) -> bool:
        """Check if field needs anonymization for the given scope"""
        return scope == PrivacyScope.PUBLIC and field in self.anonymized_fields
