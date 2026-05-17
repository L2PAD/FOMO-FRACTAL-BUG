/**
 * OnChain V2 — RPC Admin Routes
 * ===============================
 * 
 * Admin endpoints for RPC pool configuration.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { rpcPool } from './pool.service.js';
import { RpcConfigModel, RpcHealthSnapshotModel, RpcEndpoint, RpcChainId } from './models.js';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * GET /admin/rpc — Get current RPC config
 */
async function getRpcConfigHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const config = await rpcPool.loadConfig();
    const health = await rpcPool.getHealthStatus();
    
    return {
      ok: true,
      config: {
        version: config.version,
        updatedAt: config.updatedAt,
        updatedBy: config.updatedBy,
        endpoints: config.endpoints.map(ep => ({
          ...ep,
          url: maskUrl(ep.url), // Hide API keys in response
        })),
        settings: config.settings,
      },
      health,
    };
  } catch (error) {
    console.error('[RpcAdmin] Get config error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * PUT /admin/rpc — Update RPC config
 */
async function updateRpcConfigHandler(
  request: FastifyRequest<{
    Body: {
      endpoints: RpcEndpoint[];
      updatedBy?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { endpoints, updatedBy = 'ADMIN' } = request.body;
    
    // Validate endpoints
    if (!Array.isArray(endpoints)) {
      return { ok: false, error: 'endpoints must be an array' };
    }
    
    for (const ep of endpoints) {
      if (!ep.id || !ep.url || !ep.chainId) {
        return { ok: false, error: 'Each endpoint must have id, url, and chainId' };
      }
      if (!ep.url.startsWith('http://') && !ep.url.startsWith('https://')) {
        return { ok: false, error: `Invalid URL for endpoint ${ep.id}` };
      }
    }
    
    const config = await rpcPool.updateConfig(endpoints, updatedBy);
    
    return {
      ok: true,
      config: {
        version: config.version,
        updatedAt: config.updatedAt,
        updatedBy: config.updatedBy,
        endpointCount: config.endpoints.length,
      },
      message: `Config updated to v${config.version}`,
    };
  } catch (error) {
    console.error('[RpcAdmin] Update config error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /admin/rpc/test — Run health check on all endpoints
 */
async function testRpcEndpointsHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const results = await rpcPool.runHealthCheck();
    const status = await rpcPool.getHealthStatus();
    
    return {
      ok: true,
      testedAt: Date.now(),
      results: results.map(r => ({
        id: r.id,
        healthy: r.healthy,
        latencyMs: r.latencyMs,
        lastError: r.lastError,
        disabledUntil: r.disabledUntil,
      })),
      summary: {
        healthyCount: status.healthyCount,
        totalCount: status.totalCount,
        avgLatencyMs: status.avgLatencyMs,
        overallHealthy: status.overallHealthy,
      },
    };
  } catch (error) {
    console.error('[RpcAdmin] Test endpoints error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /admin/rpc/endpoint — Add single endpoint
 */
async function addEndpointHandler(
  request: FastifyRequest<{
    Body: RpcEndpoint;
  }>,
  reply: FastifyReply
) {
  try {
    const endpoint = request.body;
    
    if (!endpoint.id || !endpoint.url || !endpoint.chainId) {
      return { ok: false, error: 'Endpoint must have id, url, and chainId' };
    }
    
    const config = await rpcPool.loadConfig();
    
    // Check for duplicate ID
    if (config.endpoints.some(ep => ep.id === endpoint.id)) {
      return { ok: false, error: `Endpoint with id ${endpoint.id} already exists` };
    }
    
    // Add defaults
    const newEndpoint: RpcEndpoint = {
      provider: 'custom',
      chainName: getChainName(endpoint.chainId),
      enabled: true,
      weight: 5,
      ...endpoint,
    };
    
    const updatedEndpoints = [...config.endpoints, newEndpoint];
    await rpcPool.updateConfig(updatedEndpoints, 'ADMIN');
    
    return {
      ok: true,
      message: `Endpoint ${endpoint.id} added`,
      endpointCount: updatedEndpoints.length,
    };
  } catch (error) {
    console.error('[RpcAdmin] Add endpoint error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * DELETE /admin/rpc/endpoint/:id — Remove endpoint
 */
async function removeEndpointHandler(
  request: FastifyRequest<{
    Params: { id: string };
  }>,
  reply: FastifyReply
) {
  try {
    const { id } = request.params;
    const config = await rpcPool.loadConfig();
    
    const updatedEndpoints = config.endpoints.filter(ep => ep.id !== id);
    
    if (updatedEndpoints.length === config.endpoints.length) {
      return { ok: false, error: `Endpoint ${id} not found` };
    }
    
    await rpcPool.updateConfig(updatedEndpoints, 'ADMIN');
    
    return {
      ok: true,
      message: `Endpoint ${id} removed`,
      endpointCount: updatedEndpoints.length,
    };
  } catch (error) {
    console.error('[RpcAdmin] Remove endpoint error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /admin/rpc/health/history — Get health history
 */
async function getHealthHistoryHandler(
  request: FastifyRequest<{
    Querystring: { limit?: string };
  }>,
  reply: FastifyReply
) {
  try {
    const limit = parseInt(request.query.limit || '20');
    
    const snapshots = await RpcHealthSnapshotModel.find()
      .sort({ timestamp: -1 })
      .limit(limit);
    
    return {
      ok: true,
      count: snapshots.length,
      snapshots: snapshots.map(s => ({
        timestamp: s.timestamp,
        overallHealthy: s.overallHealthy,
        healthyCount: s.healthyCount,
        totalCount: s.totalCount,
        avgLatencyMs: s.avgLatencyMs,
      })),
    };
  } catch (error) {
    console.error('[RpcAdmin] Get health history error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /admin/rpc/test-call — Test specific RPC call
 */
async function testRpcCallHandler(
  request: FastifyRequest<{
    Body: {
      chainId: RpcChainId;
      method: string;
      params?: unknown[];
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, method, params = [] } = request.body;
    
    const start = Date.now();
    const result = await rpcPool.call(chainId, method, params);
    const latencyMs = Date.now() - start;
    
    return {
      ok: true,
      chainId,
      method,
      latencyMs,
      result,
    };
  } catch (error) {
    console.error('[RpcAdmin] Test call error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    // Mask API key in URL path/params
    if (parsed.pathname.length > 20) {
      const parts = parsed.pathname.split('/');
      const lastPart = parts[parts.length - 1];
      if (lastPart.length > 10) {
        parts[parts.length - 1] = lastPart.substring(0, 6) + '***' + lastPart.substring(lastPart.length - 4);
      }
      parsed.pathname = parts.join('/');
    }
    return parsed.toString();
  } catch {
    return url.substring(0, 30) + '***';
  }
}

function getChainName(chainId: RpcChainId): string {
  const names: Record<RpcChainId, string> = {
    1: 'ethereum',
    42161: 'arbitrum',
    10: 'optimism',
    8453: 'base',
    137: 'polygon',
  };
  return names[chainId] || 'unknown';
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function rpcAdminRoutes(fastify: FastifyInstance): Promise<void> {
  // Config management
  fastify.get('/rpc', getRpcConfigHandler);
  fastify.put('/rpc', updateRpcConfigHandler);
  
  // Endpoint management
  fastify.post('/rpc/endpoint', addEndpointHandler);
  fastify.delete('/rpc/endpoint/:id', removeEndpointHandler);
  
  // Health & Testing
  fastify.post('/rpc/test', testRpcEndpointsHandler);
  fastify.post('/rpc/test-call', testRpcCallHandler);
  fastify.get('/rpc/health/history', getHealthHistoryHandler);
  
  console.log('[OnChain V2] RPC Admin routes registered');
}

console.log('[OnChain V2] RPC Admin Routes module loaded');
