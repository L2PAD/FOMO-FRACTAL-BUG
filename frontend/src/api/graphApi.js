import { apiGet, apiPost } from './graphApiClient';

export const graphApi = {
  getStats: () => apiGet('/api/graph/stats'),

  search: (query, limit = 20) => 
    apiGet(`/api/graph/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  getNode: (type, id) => apiGet(`/api/graph/node/${type}/${id}`),

  getNeighbors: (type, id, depth = 1) => 
    apiGet(`/api/graph/neighbors/${type}/${id}?depth=${depth}`),

  getSubgraph: (nodeType, nodeId, depth = 2) =>
    apiGet(`/api/graph/subgraph/${nodeType}/${nodeId}?depth=${depth}`),

  rebuild: () => apiPost('/api/graph/rebuild')
};
