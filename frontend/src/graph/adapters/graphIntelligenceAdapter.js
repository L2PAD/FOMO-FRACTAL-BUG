/**
 * Graph Intelligence Adapter
 * 
 * Transforms: /api/graph-intelligence/address/:address response
 * Into: GraphPayload (unified contract)
 */

import { normalizeNodeId, shortenAddress } from '../utils/nodeNormalizer';
import { normalizeEdge, deduplicateEdges } from '../utils/edgeNormalizer';
import { mapNodeType } from '../constants/nodeTypes';
import { EDGE_TYPE_MAP } from '../constants/edgeTypes';

function mapEdgeType(backendType) {
  return EDGE_TYPE_MAP[backendType] || 'transfer';
}

export function adaptGraphIntelligence(snapshot) {
  if (!snapshot) return { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [] };

  const nodes = (snapshot.nodes || []).map(n => {
    const type = mapNodeType(n.type);
    const chain = n.chain || 'unknown';
    const address = n.address || '';

    return {
      id: normalizeNodeId(type, address, chain),
      label: n.displayName || n.label || shortenAddress(address),
      type,
      chain,
      address,
      metadata: n.metadata || {},
    };
  });

  const edges = deduplicateEdges(
    (snapshot.edges || []).map(e => normalizeEdge({
      source: e.fromNodeId,
      target: e.toNodeId,
      direction: e.direction || 'out',
      type: mapEdgeType(e.type),
      chain: e.chain || null,
      amountUsd: e.meta?.amountUsd,
      txHash: e.txHash,
      timestamp: e.timestamp,
      confidence: e.meta?.confidence,
      metadata: e.meta || {},
    }))
  );

  return {
    nodes,
    edges,
    highlightedPath: (snapshot.highlightedPath || []).map(step => step.edgeId || step),
    riskSummary: snapshot.riskSummary || {},
    explain: snapshot.explain || [],
  };
}
