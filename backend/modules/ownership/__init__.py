"""
Ownership Module

Field Ownership & Provider Capability Map
Two-tree architecture (Exchange vs Intel)
"""

from .field_ownership import (
    DataTree,
    FieldOwnership,
    ProviderCapability,
    OwnershipService,
    ownership_service,
    FIELD_OWNERSHIP_MAP,
    PROVIDER_CAPABILITIES
)

__all__ = [
    "DataTree",
    "FieldOwnership",
    "ProviderCapability",
    "OwnershipService",
    "ownership_service",
    "FIELD_OWNERSHIP_MAP",
    "PROVIDER_CAPABILITIES"
]
