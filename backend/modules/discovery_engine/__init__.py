"""
API Discovery Engine
====================

Automatic discovery of API endpoints from websites.
Uses Playwright for network capture and endpoint detection.

Pipeline:
1. Crawl domain
2. Detect API (network capture)
3. Validate endpoints
4. Auto-register provider
5. Create dynamic parser

Capabilities:
- Network interception (XHR, fetch, GraphQL)
- Endpoint pattern detection (/api/, /v1/, /graphql)
- Schema analysis and capability detection
- Auto provider registration
"""

from .models import (
    DiscoveredEndpoint, EndpointSchema, DiscoveryJob,
    EndpointStatus, CapabilityType
)
from .engine import DiscoveryEngine
from .validator import EndpointValidator
from .schema_detector import SchemaDetector

__all__ = [
    'DiscoveredEndpoint',
    'EndpointSchema',
    'DiscoveryJob',
    'EndpointStatus',
    'CapabilityType',
    'DiscoveryEngine',
    'EndpointValidator',
    'SchemaDetector'
]
