/**
 * Graph Filters (store-level filtering)
 * 
 * Store holds full graph → filters produce derived graph → renderer receives filtered result.
 */

export function applyGraphFilters(graph, filters) {
  if (!graph || !graph.nodes) return { nodes: [], edges: [] };
  if (!filters) return graph;

  // Filter nodes by type
  const activeNodeTypes = filters.nodeTypes || [];
  const filteredNodes = graph.nodes.filter(node => {
    if (activeNodeTypes.length === 0) return true;
    return activeNodeTypes.includes(node.type);
  });

  const nodeIds = new Set(filteredNodes.map(n => n.id));

  // Filter edges: both endpoints must be visible + edge type filter
  const activeEdgeTypes = filters.edgeTypes || [];
  const filteredEdges = graph.edges.filter(edge => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return false;
    if (activeEdgeTypes.length > 0 && !activeEdgeTypes.includes(edge.type)) return false;
    if (filters.minAmountUsd && edge.amountUsd && edge.amountUsd < filters.minAmountUsd) return false;
    return true;
  });

  return { nodes: filteredNodes, edges: filteredEdges };
}

export const DEFAULT_FILTERS = {
  nodeTypes: [],    // empty = show all
  edgeTypes: [],    // empty = show all
  minAmountUsd: 0,
};
