/**
 * Graph Data Service — unified graph loading entry point
 * 
 * Primary: graph-core projection API (with mode filtering)
 * Fallback: graph-core neighbors API (snapshot → cache → relations → Infura)
 * Legacy: graph-intelligence endpoints
 * 
 * Returns: GraphPayload (unified contract)
 */

import { adaptGraphIntelligence } from '../adapters/graphIntelligenceAdapter';
import { adaptActorGraph } from '../adapters/actorGraphAdapter';
import { adaptEntityInteractions } from '../adapters/entityInteractionAdapter';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Bounded graph params (prevents graph explosion on large datasets)
const GRAPH_BOUNDS = {
  depth: 2,
  limit_nodes: 150,
  limit_edges: 400,
};

// Expansion guard: max nodes/edges per single click-to-expand action
const MAX_EXPAND_PER_CLICK = 50;

/**
 * PRIMARY loader: Arkham-style RENDER endpoint (multi-lane edges)
 * Returns pre-computed curvature/width/opacity/color per edge
 */
async function loadGraphRender(nodeId, graphMode = null, graphLevel = null, chains = null) {
  let url = `${API_URL}/api/graph-core/render/${encodeURIComponent(nodeId)}?depth=${GRAPH_BOUNDS.depth}&limit=${GRAPH_BOUNDS.limit_nodes}`;
  if (graphMode) url += `&mode=${graphMode}`;
  if (graphLevel) url += `&identity_level=${graphLevel}`;
  if (chains) url += `&chains=${encodeURIComponent(chains)}`;

  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const raw = await response.json();
    if (!raw.nodes || raw.nodes.length === 0) return null;

    const nodes = (raw.nodes || []).map(n => {
      let label = n.label || n.entity || '';
      if (label && label.includes(':')) {
        const parts = label.split(':');
        const type = parts[0];
        if (['cluster', 'entity', 'protocol', 'cex', 'wallet', 'token'].includes(type)) {
          label = parts[1] || label;
        }
      }
      if (!label) {
        label = n.address ? `${n.address.slice(0, 6)}...${n.address.slice(-4)}` : n.id;
      }
      return {
        id: n.id || '',
        label,
        type: (n.type || 'wallet').toLowerCase(),
        chain: n.chain || 'ethereum',
        address: (n.address || '').toLowerCase(),
        degree: n.degree || 0,
        totalFlowUsd: n.totalFlowUsd || 0,
        importanceScore: n.importanceScore || 0,
        smartMoneyScore: n.smartMoneyScore || 0,
        riskScore: n.riskScore || 0,
        alphaScore: n.alphaScore || 0,
        capitalInfluenceScore: n.capitalInfluenceScore || 0,
        clusterId: n.clusterId || '',
        actorType: n.actorType || '',
        behavior: n.behavior || '',
        entity: n.entity || '',
        ringColor: n.ring_color || null,
        ringOpacity: n.ring_opacity ?? 0,
        flowState: n.flow_state || 'ROUTING',
        flowCategory: n.flow_category || null,
        metadata: n.metadata || {},
      };
    });

    const nodeIdSet = new Set(nodes.map(n => n.id));
    const edges = (raw.edges || []).map(e => ({
      id: e.id || `${e.source}-${e.target}-lane`,
      source: e.source,
      target: e.target,
      direction: e.direction || 'out',
      type: e.type || 'transfer',
      chain: e.chain || null,
      amountUsd: e.amountUsd || e.volume_usd || 0,
      txCount: e.txCount || e.tx_count || 0,
      // Arkham-style pre-computed render properties (snake_case to match ForceGraphViewer)
      color: e.color || null,
      width: e.width || null,
      opacity: e.opacity || null,
      curvature: e.curvature != null ? e.curvature : null,
      lane_index: e.lane_index ?? e.laneIndex ?? 0,
      lane_count: e.lane_count ?? e.laneCount ?? 1,
      pair_key: e.pair_key || e.pairKey || '',
      corridorId: e.corridorId || '',
      tokenGroup: e.tokenGroup || e.token_group || '',
      flowType: e.flowType || e.flow_type || 'transfer',
      confidence: e.confidence || null,
      tags: e.tags || [],
      metadata: {},
    })).filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));

    return {
      nodes,
      edges,
      corridors: [],
      highlightedPath: [],
      riskSummary: {},
      explain: [],
      meta: raw.meta || {},
      cexRoutes: raw.cex_routes || [],
      intelligence: raw.intelligence || [],
      market_context: raw.market_context || null,
    };
  } catch {
    return null;
  }
}


/**
 * Primary loader: graph-core PROJECTION endpoint
 * Uses the Graph Projection Layer with mode filtering:
 *   Node Compression → Entity Promotion → Route Aggregation → Graph Window
 */
async function loadGraphProjection(nodeId, graphMode = null, graphLevel = null) {
  const { depth, limit_nodes, limit_edges } = GRAPH_BOUNDS;
  let url = `${API_URL}/api/graph-core/project/${encodeURIComponent(nodeId)}?depth=${depth}&max_nodes=${limit_nodes}&max_edges=${limit_edges}`;
  if (graphMode) {
    url += `&mode=${graphMode}`;
  }
  if (graphLevel) {
    url += `&level=${graphLevel}`;
  }

  const response = await fetch(url);
  if (!response.ok) return null;

  const raw = await response.json();
  if (!raw.nodes || raw.nodes.length === 0) return null;

  // Adapt nodes from projection format
  const nodes = (raw.nodes || []).map(n => {
    // Clean label: remove type prefix from typed IDs (cluster:name:chain → name)
    let label = n.label || n.entity || '';
    if (label && label.includes(':')) {
      const parts = label.split(':');
      const type = parts[0];
      if (['cluster', 'entity', 'protocol', 'cex', 'wallet', 'token'].includes(type)) {
        label = parts[1] || label;
      }
    }
    if (!label) {
      label = n.address ? `${n.address.slice(0, 6)}...${n.address.slice(-4)}` : n.id;
    }
    return {
      id: n.id || '',
      label,
      type: (n.type || 'wallet').toLowerCase(),
      chain: n.chain || 'ethereum',
      address: (n.address || '').toLowerCase(),
      degree: n.degree || 0,
      totalFlowUsd: n.totalFlowUsd || 0,
      importanceScore: n.importanceScore || 0,
      smartMoneyScore: n.smartMoneyScore || 0,
      riskScore: n.riskScore || 0,
      alphaScore: n.alphaScore || 0,
      capitalInfluenceScore: n.capitalInfluenceScore || 0,
      clusterId: n.clusterId || '',
      actorType: n.actorType || '',
      behavior: n.behavior || '',
      entity: n.entity || '',
      ringColor: n.ring_color || null,
      ringOpacity: n.ring_opacity ?? 0,
      flowState: n.flow_state || 'NEUTRAL',
      flowCategory: n.flow_category || null,
      metadata: n.metadata || {},
    };
  });

  const nodeIdSet = new Set(nodes.map(n => n.id));

  const edges = (raw.edges || []).map(e => ({
    id: e.id || `${e.source}-${e.target}-${e.type || 'transfer'}`,
    source: e.source,
    target: e.target,
    direction: e.direction || 'out',
    type: e.type || 'transfer',
    chain: e.chain || null,
    amountUsd: e.amountUsd || 0,
    txCount: e.txCount || 0,
    confidence: e.confidence || null,
    tags: e.tags || [],
    flowDirection: e.flowDirection || '',
    signalStrength: e.signalStrength || 0,
    metadata: {},
  })).filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));

  return {
    nodes,
    edges,
    corridors: [],
    highlightedPath: [],
    riskSummary: {},
    explain: [],
    meta: raw.meta || {},
  };
}

/**
 * Secondary loader: graph-core neighbors endpoint
 * Uses the full cascade: snapshot → cache → relations → Infura RPC
 */
async function loadGraphCore(nodeId) {
  const { depth, limit_nodes, limit_edges } = GRAPH_BOUNDS;
  const response = await fetch(
    `${API_URL}/api/graph-core/neighbors/${encodeURIComponent(nodeId)}?depth=${depth}&limit_nodes=${limit_nodes}&limit_edges=${limit_edges}`
  );
  if (!response.ok) return null;

  const raw = await response.json();
  if (!raw.nodes || raw.nodes.length === 0) return null;

  // Adapt nodes: ensure all have proper id, label, type
  const nodes = (raw.nodes || []).map(n => {
    const id = n.id || `${(n.type || 'wallet').toLowerCase()}:${(n.address || '').toLowerCase()}:${(n.chain || 'ethereum').toLowerCase()}`;
    return {
      id,
      label: n.label || n.entity || (n.address ? `${n.address.slice(0, 6)}...${n.address.slice(-4)}` : id),
      type: (n.type || 'wallet').toLowerCase(),
      chain: n.chain || 'ethereum',
      address: (n.address || '').toLowerCase(),
      metadata: {},
    };
  });

  // Build a set of valid node IDs for edge filtering
  const nodeIdSet = new Set(nodes.map(n => n.id));

  // Adapt edges: source/target already in canonical format from backend
  const edges = (raw.edges || []).map(e => ({
    id: e.id || `${e.source}-${e.target}-${e.type || 'transfer'}`,
    source: e.source,
    target: e.target,
    direction: e.direction || 'out',
    type: e.type || 'transfer',
    chain: e.chain || null,
    amountUsd: e.amountUsd || e.total_amount_usd || null,
    timestamp: e.timestamp || null,
    confidence: e.confidence || null,
    tags: e.tags || [],
    metadata: {},
  })).filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));

  return {
    nodes,
    edges,
    corridors: raw.corridors || [],
    highlightedPath: [],
    riskSummary: {},
    explain: [],
  };
}

/**
 * Resolve a search query to a canonical node_id via graph-core
 */
async function resolveNodeId(query) {
  try {
    const response = await fetch(
      `${API_URL}/api/graph-core/resolve?q=${encodeURIComponent(query)}`
    );
    if (!response.ok) return null;
    const data = await response.json();
    if (data.found) return data;
    return null;
  } catch {
    return null;
  }
}

async function loadAddressGraph(identifier) {
  const address = identifier.includes(':') ? identifier.split(':').slice(-2)[0] : identifier;
  const chain = identifier.includes(':') ? identifier.split(':').slice(-1)[0] : 'ethereum';

  const response = await fetch(`${API_URL}/api/graph-intelligence/address/${address}?network=${chain}`);
  if (!response.ok) return null;

  const raw = await response.json();
  return adaptGraphIntelligence(raw.data || raw);
}

async function loadActorGraph() {
  const { depth, limit_nodes, limit_edges } = GRAPH_BOUNDS;
  const response = await fetch(`${API_URL}/api/graph?depth=${depth}&limit_nodes=${limit_nodes}&limit_edges=${limit_edges}`);
  if (!response.ok) return null;

  const raw = await response.json();
  return adaptActorGraph(raw.data || raw);
}

async function loadEntityGraph(identifier) {
  const slug = identifier.includes(':') ? identifier.split(':')[1] : identifier;

  const response = await fetch(`${API_URL}/api/entities/v2/${slug}/interactions`);
  if (!response.ok) return null;

  const raw = await response.json();
  return adaptEntityInteractions(raw.data || raw, slug);
}

/**
 * Discovery loader: finds seed nodes for global mode (no starting address needed)
 * Pipeline: MODE → DISCOVERY → SEED_NODES → RENDER_SEEDS
 */
async function loadGraphDiscovery(graphMode = 'all', chains = null) {
  try {
    // Step 1: Discover seed nodes (pass chain filter so backend returns chain-specific seeds)
    let discoveryUrl = `${API_URL}/api/graph-core/discovery?mode=${graphMode || 'all'}&limit=10`;
    if (chains) {
      // Backend accepts single chain param; use first chain from comma-separated list
      const firstChain = chains.split(',')[0].trim();
      if (firstChain) discoveryUrl += `&chain=${encodeURIComponent(firstChain)}`;
    }
    const discResp = await fetch(discoveryUrl);
    if (!discResp.ok) return null;
    const discovery = await discResp.json();

    if (!discovery.seed_nodes || discovery.seed_nodes.length === 0) return null;

    // Step 2: Render graph around seeds
    let renderUrl = `${API_URL}/api/graph-core/render-seeds?seeds=${encodeURIComponent(discovery.seed_nodes.map(n => n.id).join(','))}&limit=100&max_edges_per_node=30&mode=${graphMode || ''}`;
    if (graphMode === 'cex_flow') renderUrl += '&depth=2';
    if (chains) renderUrl += `&chains=${encodeURIComponent(chains)}`;
    const renderResp = await fetch(renderUrl);
    if (!renderResp.ok) return null;
    const raw = await renderResp.json();

    if (!raw.nodes || raw.nodes.length === 0) return null;

    const nodes = (raw.nodes || []).map(n => {
      let label = n.label || n.entity || '';
      if (label && label.includes(':')) {
        const parts = label.split(':');
        if (['cluster', 'entity', 'protocol', 'cex', 'wallet', 'token'].includes(parts[0])) {
          label = parts[1] || label;
        }
      }
      if (!label) {
        label = n.address ? `${n.address.slice(0, 6)}...${n.address.slice(-4)}` : n.id;
      }
      return {
        id: n.id || '',
        label,
        type: (n.type || 'wallet').toLowerCase(),
        chain: n.chain || 'ethereum',
        address: (n.address || '').toLowerCase(),
        degree: n.degree || 0,
        totalFlowUsd: n.totalFlowUsd || 0,
        importanceScore: n.importanceScore || 0,
        smartMoneyScore: n.smartMoneyScore || 0,
        riskScore: n.riskScore || 0,
        alphaScore: n.alphaScore || 0,
        capitalInfluenceScore: n.capitalInfluenceScore || 0,
        clusterId: n.clusterId || '',
        entity: n.entity || '',
        ringColor: n.ring_color || null,
        ringOpacity: n.ring_opacity ?? 0,
        flowState: n.flow_state || 'ROUTING',
        flowCategory: n.flow_category || null,
        metadata: n.metadata || {},
      };
    });

    const nodeIdSet = new Set(nodes.map(n => n.id));
    const edges = (raw.edges || []).map(e => ({
      id: e.id || `${e.source}-${e.target}-lane`,
      source: e.source,
      target: e.target,
      direction: e.direction || 'out',
      type: e.type || 'transfer',
      chain: e.chain || null,
      amountUsd: e.amountUsd || e.volume_usd || 0,
      txCount: e.txCount || e.tx_count || 0,
      // Arkham-style pre-computed render properties (snake_case to match ForceGraphViewer)
      color: e.color || null,
      width: e.width || null,
      opacity: e.opacity || null,
      curvature: e.curvature != null ? e.curvature : null,
      lane_index: e.lane_index ?? e.laneIndex ?? 0,
      lane_count: e.lane_count ?? e.laneCount ?? 1,
      pair_key: e.pair_key || e.pairKey || '',
      corridorId: e.corridorId || '',
      tokenGroup: e.tokenGroup || e.token_group || '',
      flowType: e.flowType || e.flow_type || 'transfer',
      confidence: e.confidence || null,
      tags: e.tags || [],
      metadata: {},
    })).filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));

    return {
      nodes,
      edges,
      corridors: [],
      highlightedPath: [],
      riskSummary: {},
      explain: [],
      meta: { ...(raw.meta || {}), discovery: discovery.reason, seed_count: discovery.count },
      cexRoutes: raw.cex_routes || [],
      intelligence: raw.intelligence || [],
      market_context: raw.market_context || null,
    };
  } catch {
    return null;
  }
}

export async function loadGraph({ mode, identifier, graphMode = null, graphLevel = null, chains = null }) {
  try {
    let result = null;
    // chains param: comma-separated string, e.g. "ethereum,arbitrum"
    const chainsParam = Array.isArray(chains) ? chains.join(',') : chains;

    // GLOBAL DISCOVERY: No node selected → find seeds automatically
    if (!identifier && graphMode && graphMode !== 'all') {
      result = await loadGraphDiscovery(graphMode, chainsParam);
      if (result && result.nodes.length) {
        return result;
      }
    }

    // EXPLORATION: Node selected → build graph around it
    if (identifier) {
      let nodeId = null;

      if (identifier.includes(':0x') || identifier.match(/^\w+:0x[a-f0-9]+/i)) {
        nodeId = identifier;
      } else if (identifier.startsWith('0x')) {
        nodeId = `wallet:${identifier.toLowerCase()}:ethereum`;
      } else {
        const resolved = await resolveNodeId(identifier);
        if (resolved?.node_id) {
          nodeId = resolved.node_id;
        }
      }

      if (nodeId) {
        // Use Arkham-style render endpoint first (multi-lane edges)
        result = await loadGraphRender(nodeId, graphMode, graphLevel, chainsParam);
        // Early return for render results — backend already limits data,
        // skip MAX_EXPAND_PER_CLICK truncation to preserve multi-edge integrity
        if (result && result.nodes.length) {
          return result;
        }

        // When chains are specified and render returned empty, don't fall back to
        // chain-agnostic endpoints — the render endpoint already filters correctly.
        if (!chainsParam) {
          // Fallback to projection endpoint (no chain filtering)
          result = await loadGraphProjection(nodeId, graphMode, graphLevel);
          if (result && result.nodes.length) {
            return result;
          }

          // Fallback to neighbors if projection returns empty
          result = await loadGraphCore(nodeId);
          if (result && result.nodes.length) {
            return result;
          }
        }
      }
    }

    // Try chain-filtered discovery before legacy fallback (chains-aware path)
    if ((!result || !result.nodes?.length) && chainsParam && !identifier) {
      result = await loadGraphDiscovery(graphMode || 'smart_money', chainsParam);
      if (result && result.nodes.length) return result;
    }

    // When chains are explicitly specified and chain-aware endpoints returned nothing,
    // do NOT fall back to chain-agnostic legacy endpoints — return empty graph.
    // This ensures the graph correctly reflects "no data for this chain".
    if (chainsParam && (!result || !result.nodes?.length)) {
      return { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [], meta: { chains: chainsParam, empty_reason: 'no_data_for_chain' } };
    }

    // Fallback to legacy endpoints (only when no chain filter is active)
    if (!result || (!result.nodes.length && !result.edges.length)) {
      if (mode === 'address') {
        result = await loadAddressGraph(identifier);
      } else if (mode === 'actor') {
        result = await loadActorGraph();
      } else if (mode === 'entity') {
        result = await loadEntityGraph(identifier);
      }
    }

    // Secondary fallback chain (only when no chain filter is active)
    if (!result || (!result.nodes.length && !result.edges.length)) {
      if (mode === 'address') {
        result = await loadActorGraph();
      }
      if ((!result || !result.nodes.length) && mode !== 'entity' && identifier) {
        result = await loadEntityGraph(identifier);
      }
    }

    const payload = result || { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [] };

    // Expansion guard: enforce hard limit on nodes/edges per load
    if (payload.nodes.length > MAX_EXPAND_PER_CLICK) {
      payload.nodes = payload.nodes.slice(0, MAX_EXPAND_PER_CLICK);
      const nodeIds = new Set(payload.nodes.map(n => n.id));
      payload.edges = payload.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
    }

    return payload;
  } catch (err) {
    console.error(`[graphDataService] Failed to load graph (mode=${mode}):`, err);
    return { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [] };
  }
}

/**
 * Expand a single node — uses cached neighbors endpoint
 * Used when user clicks a node to see its connections
 */
export async function expandNode(nodeId) {
  try {
    // Use the cached neighbors endpoint (backend handles cache)
    const response = await fetch(
      `${API_URL}/api/graph-core/neighbors/${encodeURIComponent(nodeId)}?depth=1&limit_nodes=${MAX_EXPAND_PER_CLICK}&limit_edges=${MAX_EXPAND_PER_CLICK * 3}`
    );
    if (!response.ok) return { nodes: [], edges: [] };

    const raw = await response.json();

    // If backend returned cached/built data, adapt it
    if (raw.nodes && raw.nodes.length > 0) {
      const adapted = adaptGraphIntelligence({
        nodes: raw.nodes,
        edges: raw.edges,
      });
      // Pass corridors through from backend (separate from edges)
      adapted.corridors = raw.corridors || [];
      return adapted;
    }

    // Fallback: direct address graph
    const address = nodeId.includes(':') ? nodeId.split(':').slice(-2)[0] : nodeId;
    const chain = nodeId.includes(':') ? nodeId.split(':').slice(-1)[0] : 'ethereum';

    const fallbackRes = await fetch(
      `${API_URL}/api/graph-intelligence/address/${address}?network=${chain}&depth=1&limit_nodes=${MAX_EXPAND_PER_CLICK}&limit_edges=${MAX_EXPAND_PER_CLICK * 3}`
    );
    if (!fallbackRes.ok) return { nodes: [], edges: [] };

    const fallbackRaw = await fallbackRes.json();
    const result = adaptGraphIntelligence(fallbackRaw.data || fallbackRaw);

    // Hard guard: never return more than MAX_EXPAND_PER_CLICK nodes
    if (result.nodes.length > MAX_EXPAND_PER_CLICK) {
      result.nodes = result.nodes.slice(0, MAX_EXPAND_PER_CLICK);
      const nodeIds = new Set(result.nodes.map(n => n.id));
      result.edges = result.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
    }

    return result;
  } catch (err) {
    console.error(`[graphDataService] Failed to expand node ${nodeId}:`, err);
    return { nodes: [], edges: [] };
  }
}

/**
 * Fetch node detail — for context panels
 * Returns: { node, overlays, routes }
 */
export async function fetchNodeDetail(nodeId) {
  try {
    const response = await fetch(
      `${API_URL}/api/graph-core/node/${encodeURIComponent(nodeId)}`
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    console.error(`[graphDataService] Failed to fetch node detail ${nodeId}:`, err);
    return null;
  }
}

/**
 * Fetch capital routes
 */
export async function fetchRoutes(ranking = 'largest', limit = 20) {
  try {
    const response = await fetch(
      `${API_URL}/api/graph-core/routes?ranking=${ranking}&limit=${limit}`
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data.routes || [];
  } catch {
    return [];
  }
}

/**
 * Fetch intelligence overlays for a node
 */
export async function fetchOverlays(nodeId = null, overlayType = null) {
  try {
    let url = `${API_URL}/api/graph-core/overlay?limit=50`;
    if (nodeId) url += `&node_id=${encodeURIComponent(nodeId)}`;
    if (overlayType) url += `&overlay_type=${overlayType}`;
    const response = await fetch(url);
    if (!response.ok) return [];
    const data = await response.json();
    return data.overlays || [];
  } catch {
    return [];
  }
}
