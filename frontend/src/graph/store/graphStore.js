/**
 * Unified Graph Store
 * 
 * Central state for the graph visualization.
 * All data sources feed into this store through adapters.
 * 
 * Store holds FULL graph.
 * Filtering produces derived graph via graphFilters.js.
 */

import { create } from 'zustand';
import { applyGraphFilters, DEFAULT_FILTERS } from '../utils/graphFilters';

export const useGraphStore = create((set, get) => ({
  // Graph mode: which data source is active
  mode: 'address', // 'address' | 'actor' | 'entity'

  // Full graph data (unified format from adapters)
  graphData: { nodes: [], edges: [] },
  corridors: [],
  highlightedPath: [],
  riskSummary: {},
  explain: [],

  // Temporal layer
  timeRange: { start: null, end: null },

  // Filters
  filters: { ...DEFAULT_FILTERS },

  // Selection
  selectedNode: null,
  centerNodeId: null,

  // Loading
  loading: false,
  error: null,

  // === Derived: filtered graph (includes temporal filter) ===
  getFilteredGraph: () => {
    const state = get();
    let graph = applyGraphFilters(state.graphData, state.filters);

    // Apply temporal filter if time range is set
    const { start, end } = state.timeRange;
    if (start || end) {
      const filteredEdges = graph.edges.filter(e => {
        const ts = e.timestamp;
        if (!ts) return true; // keep edges without timestamp
        if (start && ts < start) return false;
        if (end && ts > end) return false;
        return true;
      });
      // Recompute nodes from filtered edges
      const activeNodeIds = new Set();
      filteredEdges.forEach(e => {
        activeNodeIds.add(e.source);
        activeNodeIds.add(e.target);
      });
      const filteredNodes = graph.nodes.filter(n => activeNodeIds.has(n.id));
      graph = { nodes: filteredNodes, edges: filteredEdges };
    }

    return graph;
  },

  // === Actions ===
  setGraphData: (data) => set({
    graphData: { nodes: data.nodes || [], edges: data.edges || [] },
    corridors: data.corridors || [],
    highlightedPath: data.highlightedPath || [],
    riskSummary: data.riskSummary || {},
    explain: data.explain || [],
    error: null,
  }),

  setTimeRange: (range) => set({ timeRange: range }),
  clearTimeRange: () => set({ timeRange: { start: null, end: null } }),

  setMode: (mode) => set({ mode }),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setCenterNodeId: (id) => set({ centerNodeId: id }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),

  setFilters: (updates) => set((state) => ({
    filters: { ...state.filters, ...updates },
  })),

  resetFilters: () => set({ filters: { ...DEFAULT_FILTERS } }),

  clearGraph: () => set({
    graphData: { nodes: [], edges: [] },
    corridors: [],
    highlightedPath: [],
    riskSummary: {},
    explain: [],
    timeRange: { start: null, end: null },
    selectedNode: null,
    centerNodeId: null,
    error: null,
  }),
}));
