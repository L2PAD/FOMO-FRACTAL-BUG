/**
 * Actor Graph Adapter
 * 
 * Transforms: /api/graph response (actor correlation graph)
 * Into: GraphPayload (unified contract)
 */

import { normalizeNodeId } from '../utils/nodeNormalizer';
import { normalizeEdge, deduplicateEdges } from '../utils/edgeNormalizer';
import { mapNodeType } from '../constants/nodeTypes';
import { EDGE_TYPE_MAP } from '../constants/edgeTypes';

function mapEdgeType(backendType) {
  return EDGE_TYPE_MAP[backendType] || 'transfer';
}

export function adaptActorGraph(data) {
  if (!data) return { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [] };

  const nodes = (data.nodes || []).map(n => {
    const type = mapNodeType(n.nodeType || n.type || 'actor');
    return {
      id: n.id || normalizeNodeId(type, n.label || '', 'multi'),
      label: n.label || n.id || '',
      type,
      chain: 'multi',
      address: '',
      metadata: {
        ...(n.metrics || {}),
        actorType: n.actorType,
        source: n.source,
        coverage: n.coverage,
      },
    };
  });

  const edges = deduplicateEdges(
    (data.edges || []).map(e => normalizeEdge({
      source: e.source || e.from,
      target: e.target || e.to,
      direction: 'out',
      type: mapEdgeType(e.edgeType || e.type),
      confidence: e.confidence,
      metadata: {
        ...(e.evidence || {}),
        weight: e.weight,
      },
    }))
  );

  return {
    nodes,
    edges,
    highlightedPath: [],
    riskSummary: {},
    explain: [],
  };
}
