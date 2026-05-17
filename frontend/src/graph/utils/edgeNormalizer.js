/**
 * Edge Normalizer
 * 
 * Deterministic edge ID + full edge contract.
 * ID format: source-target-txHash (or source-target-type if no txHash)
 */

export function normalizeEdge(edge) {
  const id = edge.id || `${edge.source}-${edge.target}-${edge.txHash || edge.type || 'unknown'}`;

  return {
    id,
    source: edge.source,
    target: edge.target,
    direction: edge.direction || 'out',
    type: edge.type || 'transfer',
    chain: edge.chain || null,
    amountUsd: edge.amountUsd || null,
    txHash: edge.txHash || null,
    timestamp: edge.timestamp || null,
    confidence: edge.confidence || null,
    metadata: edge.metadata || {},
  };
}

export function deduplicateEdges(edges) {
  const seen = new Set();
  return edges.filter(edge => {
    if (seen.has(edge.id)) return false;
    seen.add(edge.id);
    return true;
  });
}
