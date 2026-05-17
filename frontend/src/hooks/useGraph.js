import { useEffect, useCallback } from 'react';
import { useGraphStore } from '../store/graphStore';
import { graphApi } from '../api/graphApi.js';

export function useGraph() {
  const {
    nodes,
    edges,
    stats,
    searchResults,
    selectedNode,
    neighbors,
    loading,
    searchLoading,
    depth,
    setNodes,
    setEdges,
    setStats,
    setSearchResults,
    setSelectedNode,
    setNeighbors,
    setLoading,
    setSearchLoading,
    setError
  } = useGraphStore();

  const fetchStats = useCallback(async () => {
    try {
      const data = await graphApi.getStats();
      setStats(data);
    } catch (e) {
      console.error('Failed to fetch graph stats:', e);
    }
  }, [setStats]);

  const search = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setSearchLoading(true);
    try {
      const data = await graphApi.search(query);
      setSearchResults(data.results || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setSearchLoading(false);
    }
  }, [setSearchResults, setSearchLoading, setError]);

  const selectNode = useCallback(async (type, id) => {
    setLoading(true);
    try {
      const [nodeData, neighborsData] = await Promise.all([
        graphApi.getNode(type, id),
        graphApi.getNeighbors(type, id, depth)
      ]);
      
      setSelectedNode(nodeData);
      setNeighbors(neighborsData.neighbors || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [depth, setSelectedNode, setNeighbors, setLoading, setError]);

  const loadSubgraph = useCallback(async (nodeType, nodeId) => {
    setLoading(true);
    try {
      const data = await graphApi.getSubgraph(nodeType, nodeId, depth);
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [depth, setNodes, setEdges, setLoading, setError]);

  const rebuild = useCallback(async () => {
    setLoading(true);
    try {
      await graphApi.rebuild();
      await fetchStats();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [fetchStats, setLoading, setError]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    nodes,
    edges,
    stats,
    searchResults,
    selectedNode,
    neighbors,
    loading,
    searchLoading,
    search,
    selectNode,
    loadSubgraph,
    rebuild,
    fetchStats
  };
}

export default useGraph;
