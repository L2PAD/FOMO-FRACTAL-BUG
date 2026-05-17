"""
Endpoint Validator
==================

Validates discovered endpoints and scores them.
"""

import httpx
import asyncio
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

from .models import DiscoveredEndpoint, EndpointStatus, CapabilityType
from .schema_detector import SchemaDetector

logger = logging.getLogger(__name__)


class EndpointValidator:
    """
    Validates discovered API endpoints.
    """
    
    def __init__(self):
        self.schema_detector = SchemaDetector()
        self.timeout = 15
    
    async def validate_endpoint(
        self, 
        endpoint: DiscoveredEndpoint,
        proxy_url: Optional[str] = None
    ) -> DiscoveredEndpoint:
        """
        Validate an endpoint and update its status.
        
        Args:
            endpoint: Endpoint to validate
            proxy_url: Optional proxy for request
            
        Returns:
            Updated endpoint with validation results
        """
        endpoint.status = EndpointStatus.VALIDATING
        endpoint.last_checked = datetime.now(timezone.utc)
        
        try:
            start_time = datetime.now(timezone.utc)
            
            async with httpx.AsyncClient(
                timeout=self.timeout,
                proxy=proxy_url
            ) as client:
                response = await client.request(
                    method=endpoint.method,
                    url=endpoint.url
                )
                
                latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                endpoint.latency_ms = latency
                
                # Check status
                if response.status_code == 200:
                    endpoint.status = EndpointStatus.ACTIVE
                    endpoint.last_success = datetime.now(timezone.utc)
                    
                    # Analyze schema
                    try:
                        data = response.json()
                        schema = self.schema_detector.detect_from_response(data)
                        endpoint.response_schema = schema.fields
                        endpoint.capabilities = [schema.detected_capability]
                        
                        # Update scores
                        endpoint.data_quality_score = schema.confidence
                        endpoint.stability_score = 1.0  # Initial score
                        endpoint.overall_score = (
                            endpoint.stability_score * 0.5 +
                            endpoint.data_quality_score * 0.3 +
                            (1.0 - min(latency / 5000, 1.0)) * 0.2  # Latency score
                        )
                    except Exception as e:
                        logger.warning(f"Schema detection failed: {e}")
                
                elif response.status_code == 401:
                    endpoint.status = EndpointStatus.ACTIVE
                    endpoint.requires_auth = True
                    endpoint.auth_type = "api_key"
                    
                elif response.status_code == 403:
                    endpoint.status = EndpointStatus.BLOCKED
                    endpoint.requires_auth = True
                    
                elif response.status_code == 429:
                    endpoint.status = EndpointStatus.DEGRADED
                    # Rate limited - still valid
                    
                else:
                    endpoint.status = EndpointStatus.DEAD
                
        except httpx.TimeoutException:
            endpoint.status = EndpointStatus.DEAD
            endpoint.latency_ms = self.timeout * 1000
            
        except Exception as e:
            endpoint.status = EndpointStatus.DEAD
            logger.error(f"Validation error for {endpoint.url}: {e}")
        
        return endpoint
    
    async def batch_validate(
        self, 
        endpoints: list,
        proxy_url: Optional[str] = None,
        concurrency: int = 5
    ) -> list:
        """
        Validate multiple endpoints concurrently.
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def validate_with_semaphore(endpoint):
            async with semaphore:
                return await self.validate_endpoint(endpoint, proxy_url)
        
        tasks = [validate_with_semaphore(ep) for ep in endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validated = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                endpoints[i].status = EndpointStatus.DEAD
                validated.append(endpoints[i])
            else:
                validated.append(result)
        
        return validated
    
    def calculate_score(self, endpoint: DiscoveredEndpoint) -> float:
        """
        Calculate overall endpoint score.
        
        Components:
        - Stability (40%): Based on success rate
        - Latency (30%): Lower is better
        - Data quality (30%): Schema detection confidence
        """
        stability = endpoint.success_rate if endpoint.success_rate else 0.5
        
        latency_score = 1.0
        if endpoint.latency_ms:
            latency_score = max(0, 1.0 - (endpoint.latency_ms / 5000))
        
        quality = endpoint.data_quality_score
        
        return (
            stability * 0.4 +
            latency_score * 0.3 +
            quality * 0.3
        )
