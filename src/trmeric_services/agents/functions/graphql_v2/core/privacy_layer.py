"""
Privacy Layer - Enforces Data Access Controls

This module handles privacy-aware query filtering and result anonymization
based on the privacy scope (PUBLIC vs PRIVATE).
"""

from typing import Dict, Any, List, Set
from ..models.query_plan import QueryPlan
from ..models.privacy_models import PrivacyScope
from ..models.graph_schema import GraphSchema
from src.trmeric_api.logging.AppLogger import appLogger
import hashlib


class PrivacyLayer:
    """
    Enforces privacy controls on queries and results.
    
    Features:
    - Filter query plans based on privacy scope
    - Remove sensitive fields from results
    - Anonymize data for PUBLIC scope
    - Add privacy-aware WHERE clauses to GSQL
    """
    
    @staticmethod
    def filter_query_plan(plan: QueryPlan, schema: GraphSchema) -> QueryPlan:
        """
        Filter query plan based on privacy scope and schema.
        
        Args:
            plan: Original query plan
            schema: Graph schema with privacy configuration
            
        Returns:
            Filtered query plan with only allowed attributes
        """
        if plan.privacy_scope == PrivacyScope.PRIVATE:
            # No filtering needed for private scope
            return plan
        
        # PUBLIC scope - filter attributes
        filtered_attributes = {}
        
        for vertex_name, requested_attrs in plan.attributes_to_query.items():
            vertex_schema = schema.get_vertex(vertex_name)
            if not vertex_schema:
                # Vertex not in schema, skip
                continue
            
            # Get allowed attributes for PUBLIC scope
            allowed_attrs = vertex_schema.get_allowed_attributes(PrivacyScope.PUBLIC)
            
            if not requested_attrs:
                # No specific attributes requested, use all allowed
                filtered_attributes[vertex_name] = allowed_attrs
            else:
                # Filter requested attributes to only allowed ones
                filtered_attributes[vertex_name] = [
                    attr for attr in requested_attrs
                    if attr in allowed_attrs
                ]
        
        # Update plan with filtered attributes
        plan.attributes_to_query = filtered_attributes
        
        appLogger.info({
            "function": "PrivacyLayer_filter_query_plan",
            "privacy_scope": plan.privacy_scope.value,
            "filtered_attributes_count": sum(len(attrs) for attrs in filtered_attributes.values())
        })
        
        return plan
    
    @staticmethod
    def add_privacy_filters(plan: QueryPlan) -> Dict[str, Any]:
        """
        Generate additional GSQL WHERE clauses for privacy filtering.
        
        Args:
            plan: Query plan
            
        Returns:
            Dictionary with privacy filter conditions
        """
        privacy_filters = {}
        
        if plan.privacy_scope == PrivacyScope.PUBLIC:
            # Add filter for PUBLIC data only
            # Assumes vertices have a privacy_tier attribute
            privacy_filters["privacy_tier_filter"] = 'v.privacy_tier == "PUBLIC"'
        
        return privacy_filters
    
    @staticmethod
    def anonymize_results(
        results: Dict[str, Any],
        schema: GraphSchema,
        scope: PrivacyScope
    ) -> Dict[str, Any]:
        """
        Anonymize sensitive fields in query results.
        
        Args:
            results: Raw query results
            schema: Graph schema with privacy configuration
            scope: Privacy scope
            
        Returns:
            Anonymized results
        """
        if scope == PrivacyScope.PRIVATE:
            # No anonymization for private scope
            return results
        
        # PUBLIC scope - anonymize sensitive fields
        anonymized = {}
        
        for entity_id, entity_data in results.items():
            anonymized_entity = {}
            
            for key, value in entity_data.items():
                # Determine if this field needs anonymization
                needs_anon = PrivacyLayer._needs_anonymization(key, schema)
                
                if needs_anon and isinstance(value, str):
                    # Anonymize string fields
                    anonymized_entity[key] = PrivacyLayer._anonymize_text(value)
                else:
                    # Keep as-is
                    anonymized_entity[key] = value
            
            anonymized[entity_id] = anonymized_entity
        
        return anonymized
    
    @staticmethod
    def _needs_anonymization(field_name: str, schema: GraphSchema) -> bool:
        """
        Check if a field needs anonymization.
        
        Args:
            field_name: Field name to check
            schema: Graph schema
            
        Returns:
            True if field needs anonymization
        """
        # Common anonymization patterns
        anonymize_patterns = ["title", "name", "description", "comment", "owner"]
        
        for pattern in anonymize_patterns:
            if pattern in field_name.lower():
                return True
        
        return False
    
    @staticmethod
    def _anonymize_text(text: str) -> str:
        """
        Anonymize text by hashing or generic replacement.
        
        Args:
            text: Original text
            
        Returns:
            Anonymized text
        """
        if not text:
            return text
        
        # Simple anonymization: hash-based ID
        # In production, this would be more sophisticated
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"Anonymized_{text_hash}"
    
    @staticmethod
    def get_tenant_filter(tenant_id: int, scope: PrivacyScope) -> str:
        """
        Generate GSQL WHERE clause for tenant isolation.
        
        Args:
            tenant_id: Tenant ID
            scope: Privacy scope
            
        Returns:
            GSQL WHERE clause
        """
        if scope == PrivacyScope.PRIVATE:
            # Filter to only this tenant's data
            return f'v.tenant_id == {tenant_id}'
        else:
            # PUBLIC scope - exclude private data from this tenant
            # (or include only PUBLIC tier data)
            return f'v.privacy_tier == "PUBLIC"'
