/**
 * Entity Interaction Adapter
 * 
 * Transforms: /api/entities/v2/{slug}/interactions response
 * Into: GraphPayload (unified contract)
 */

import { normalizeNodeId } from '../utils/nodeNormalizer';
import { normalizeEdge, deduplicateEdges } from '../utils/edgeNormalizer';

export function adaptEntityInteractions(data, centerSlug) {
  if (!data) return { nodes: [], edges: [], highlightedPath: [], riskSummary: {}, explain: [] };

  const interactions = data.interactions || data.data || [];
  const nodes = [];
  const edges = [];
  const nodeSet = new Set();

  const centerId = normalizeNodeId('wallet', centerSlug, 'multi');
  nodes.push({
    id: centerId,
    label: centerSlug,
    type: 'wallet',
    chain: 'multi',
    address: '',
    metadata: {},
  });
  nodeSet.add(centerId);

  interactions.forEach((interaction, idx) => {
    const rawType = interaction.type === 'exchange' ? 'exchange' :
                    interaction.type === 'token' ? 'token' :
                    interaction.type === 'dex' ? 'exchange' : 'wallet';

    const targetId = interaction.entityId || interaction.id ||
      normalizeNodeId(rawType, interaction.name || `entity_${idx}`, interaction.chain || 'multi');

    if (!nodeSet.has(targetId)) {
      nodes.push({
        id: targetId,
        label: interaction.name || interaction.label || targetId,
        type: rawType,
        chain: interaction.chain || 'multi',
        address: interaction.address || '',
        metadata: interaction.metadata || {},
      });
      nodeSet.add(targetId);
    }

    edges.push(normalizeEdge({
      source: centerId,
      target: targetId,
      direction: interaction.direction || 'out',
      type: interaction.interactionType || 'transfer',
      amountUsd: interaction.volumeUsd || interaction.amountUsd,
      metadata: {
        txCount: interaction.txCount,
        lastInteraction: interaction.lastInteraction,
      },
    }));
  });

  return {
    nodes,
    edges: deduplicateEdges(edges),
    highlightedPath: [],
    riskSummary: {},
    explain: [],
  };
}
