import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { ChevronLeft, ChevronRight, Shield, Activity, AlertCircle } from 'lucide-react';
import ForceGraphViewer from './ForceGraphViewer';
import GraphTimeline from './GraphTimeline';
import NodeContextPanel from './NodeContextPanel';
import SmartWalletLeaderboard from './SmartWalletLeaderboard';
import GraphPlaybackControl from './GraphPlaybackControl';
import { useGraphStore } from '../graph/store/graphStore';
import { EDGE_TYPES } from '../graph/constants/edgeTypes';
import { EDGE_COLOR_IN, EDGE_COLOR_OUT } from '../graph/constants/graphColors';
import { applyGraphFilters } from '../graph/utils/graphFilters';
import { useOnchainChain } from '../pages/OnchainV3/context/OnchainChainContext';
import { toast } from 'sonner';

// ── Domain hooks ──
import { useGraphControls } from './graph/hooks/useGraphControls';
import { useIntelligenceEngine } from './graph/hooks/useIntelligenceEngine';
import { useIntelligenceView } from './graph/hooks/useIntelligenceView';
import { useCexFlow } from './graph/hooks/useCexFlow';
import { useGraphLoader } from './graph/hooks/useGraphLoader';
import { useGraphSearch } from './graph/hooks/useGraphSearch';
import { useGraphRelations } from './graph/hooks/useGraphRelations';
import { useHoverState } from './graph/hooks/useHoverState';

// ── UI / Panel components ──
import ModeHUD from './graph/ui/ModeHUD';
import GraphToolbar from './graph/ui/GraphToolbar';
import IntelligencePanel from './graph/panels/IntelligencePanel';
import WalletDetailPanel from './graph/panels/WalletDetailPanel';
import { CexLockedPanel, CexSegmentPanel } from './graph/panels/CexRoutePanel';
import HoverTooltip from './graph/ui/HoverTooltip';

// ── Mode Registry ──
import { resolveMode, MODE_REGISTRY } from './graph/modeRegistry';
import { MODE_LABELS } from './graph/utils';

const CHAIN_ID_TO_KEY = { 1: 'ethereum', 42161: 'arbitrum', 10: 'optimism', 8453: 'base' };
const ALL_CHAINS = ['ethereum', 'arbitrum', 'optimism', 'base'];

const GraphExplorer = ({ colors, initialNodeId = null, nav = null }) => {
  // ── Chain context ──
  const { chainId } = useOnchainChain();
  const selectedChainKey = CHAIN_ID_TO_KEY[chainId] || null;
  const activeChains = useMemo(() => selectedChainKey ? [selectedChainKey] : ALL_CHAINS, [selectedChainKey]);

  // ── Graph store ──
  const { graphData, corridors, highlightedPath, riskSummary, loading, setGraphData, setLoading, setMode, clearGraph, timeRange } = useGraphStore();

  // ── Domain hooks ──
  const controls = useGraphControls();
  const { intelligence, setIntelligence, marketContext, setMarketContext, clearIntelligence } = useIntelligenceEngine();
  const { expandedWalletSignal, setExpandedWalletSignal } = useIntelligenceView();
  const { fetchEntityGraph, fetchDiscoveryGraph } = useGraphLoader(activeChains);

  // ── Entity / Mode / Level state (orchestrator glue) ──
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [graphMode, setGraphMode] = useState(null);
  const [graphLevel, setGraphLevel] = useState(null);

  // ── Derived: filtered graph ──
  const filteredGraph = useMemo(() => {
    const activeEdgeTypes = Object.entries(controls.edgeTypeFilters).filter(([, v]) => v).map(([k]) => k);
    const allEdgeTypesActive = activeEdgeTypes.length === Object.keys(EDGE_TYPES).length;
    let graph = graphData;
    if (!allEdgeTypesActive) {
      graph = applyGraphFilters(graph, { nodeTypes: [], edgeTypes: activeEdgeTypes });
    }
    const { start, end } = timeRange;
    if (start || end) {
      const filteredEdges = graph.edges.filter(e => {
        const ts = e.timestamp;
        if (!ts) return true;
        if (start && ts < start) return false;
        if (end && ts > end) return false;
        return true;
      });
      const activeNodeIds = new Set();
      filteredEdges.forEach(e => {
        activeNodeIds.add(typeof e.source === 'object' ? e.source.id : e.source);
        activeNodeIds.add(typeof e.target === 'object' ? e.target.id : e.target);
      });
      graph = { nodes: graph.nodes.filter(n => activeNodeIds.has(n.id)), edges: filteredEdges };
    }
    return graph;
  }, [graphData, controls.edgeTypeFilters, timeRange]);

  const nodeDataMap = useMemo(() => {
    const map = new Map();
    (filteredGraph.nodes || []).forEach(n => map.set(n.id, n));
    return map;
  }, [filteredGraph.nodes]);

  // ── CEX Flow domain ──
  const cex = useCexFlow(filteredGraph.edges, nodeDataMap);

  // ── Mode Registry context ──
  const modeCtx = useMemo(() => ({
    intelligence, marketContext,
    expandedWalletSignal, setExpandedWalletSignal,
    cexFlow: cex,
  }), [intelligence, marketContext, expandedWalletSignal, setExpandedWalletSignal, cex]);

  const modeResolved = useMemo(() => resolveMode(graphMode, modeCtx), [graphMode, modeCtx]);
  const activeIntelligence = modeResolved && !modeResolved.config.bypassIntelligence
    ? (modeResolved.data.activeIntelligence || []) : [];

  // ── Search (does NOT own entity — reports via callback) ──
  const search = useGraphSearch({
    onSelectEntity: useCallback((entity) => setSelectedEntity(entity), []),
  });

  // ── Relations (does NOT own entity — receives entityId) ──
  const rels = useGraphRelations({
    entityId: selectedEntity?.id || null,
    fallbackEdges: filteredGraph.edges,
    onNavigateToEntity: useCallback((entity) => {
      setSelectedEntity(entity);
      search.setQuery(entity.label);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search.setQuery]),
  });

  // ── Context panel, Route focus ──
  const [contextNode, setContextNode] = useState(null);
  const [activeRoute, setActiveRoute] = useState(null);
  const [isRouteFocus, setIsRouteFocus] = useState(false);

  // ── Hover tooltip (isolated domain) ──
  const hover = useHoverState(nodeDataMap);

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // ORCHESTRATION: Data loading + Mode switching
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  const loadGraphForEntity = useCallback(async (entityId, mode = graphMode, level = graphLevel) => {
    setLoading(true);
    const { data, dataMode } = await fetchEntityGraph(entityId, mode, level);
    setMode(dataMode);
    setGraphData(data);
    setLoading(false);
  }, [setGraphData, setLoading, setMode, graphMode, graphLevel, fetchEntityGraph]);

  const handleModeChange = useCallback(async (newMode) => {
    if (!newMode || newMode === 'all') {
      setGraphMode(null);
      cex.setIsCexFlowMode(false);
      cex.setCexRoutes([]);
      clearIntelligence();
      setExpandedWalletSignal(null);
      if (selectedEntity) loadGraphForEntity(selectedEntity.id, null, graphLevel);
      return;
    }
    if (newMode !== 'cex_flow') {
      cex.setIsCexFlowMode(false);
      cex.setCexRoutes([]);
    }
    if (selectedEntity) {
      setLoading(true);
      const { data: result, dataMode } = await fetchEntityGraph(selectedEntity.id, newMode, graphLevel);
      setLoading(false);
      const hasData = result && result.nodes && result.nodes.length > 1 && result.edges && result.edges.length > 0;
      if (!hasData) {
        toast.error(`No ${MODE_LABELS[newMode] || newMode} data for this address`, {
          description: 'Staying on the current view', duration: 4000,
          style: { background: '#1e293b', color: '#f1f5f9', border: '1px solid rgba(239,68,68,0.3)', fontFamily: "'Gilroy', sans-serif" },
          classNames: { description: '!text-slate-300' },
        });
        return;
      }
      setGraphMode(newMode);
      setMode(dataMode);
      setGraphData(result);
      setIntelligence(result.intelligence || []);
      setMarketContext(result.market_context || null);
      if (newMode === 'cex_flow') {
        const routes = result.cexRoutes || [];
        cex.setCexRoutes(routes);
        cex.setIsCexFlowMode(true);
        if (routes.length > 0) {
          const flaggedCount = routes.filter(r => (r.wash_score || 0) > 0).length;
          const desc = flaggedCount > 0
            ? `${routes.length} corridor${routes.length > 1 ? 's' : ''}, ${flaggedCount} with wash signals`
            : `Exchange-to-exchange corridors highlighted`;
          toast.success(`CEX Flow: ${routes.length} route${routes.length > 1 ? 's' : ''} found`, {
            description: desc, duration: 3000,
            style: { background: '#1e293b', color: '#f1f5f9', border: '1px solid rgba(34,197,94,0.4)', fontFamily: "'Gilroy', sans-serif" },
            classNames: { description: '!text-slate-300' },
          });
        } else {
          toast.info(`CEX Flow: no exchange-to-exchange routes found`, {
            description: 'Only one exchange in this graph', duration: 3000,
            style: { background: '#1e293b', color: '#f1f5f9', border: '1px solid rgba(59,130,246,0.3)', fontFamily: "'Gilroy', sans-serif" },
            classNames: { description: '!text-slate-300' },
          });
        }
      }
    } else if (newMode && newMode !== 'all') {
      setLoading(true);
      try {
        const data = await fetchDiscoveryGraph(newMode);
        if (data && data.nodes.length > 0) {
          setGraphMode(newMode);
          setGraphData(data);
          setIntelligence(data.intelligence || []);
          setMarketContext(data.market_context || null);
          if (newMode === 'cex_flow') {
            const routes = data.cexRoutes || [];
            cex.setCexRoutes(routes);
            cex.setIsCexFlowMode(true);
          }
        } else {
          toast.error(`No ${MODE_LABELS[newMode] || newMode} data found`, { duration: 3000 });
        }
      } finally {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEntity, loadGraphForEntity, graphLevel]);

  // ── Effects: initial load, entity load, chain reload ──
  useEffect(() => {
    if (!initialNodeId) return;
    const init = async () => {
      setLoading(true);
      setMode('address');
      const { data } = await fetchEntityGraph(initialNodeId, graphMode, graphLevel);
      setGraphData(data);
      setSelectedEntity({ id: initialNodeId, label: initialNodeId.split(':')[1] || initialNodeId, type: initialNodeId.split(':')[0] || 'wallet' });
      search.setQuery(initialNodeId.split(':')[1] || initialNodeId);
      setLoading(false);
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialNodeId]);

  useEffect(() => {
    if (selectedEntity) loadGraphForEntity(selectedEntity.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEntity]);

  useEffect(() => {
    const reloadForChain = async () => {
      if (selectedEntity) {
        loadGraphForEntity(selectedEntity.id);
      } else if (graphMode && graphMode !== 'all') {
        handleModeChange(graphMode);
      }
    };
    reloadForChain();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChainKey]);

  // ── Mode lifecycle (onEnter/onExit) ──
  const prevModeRef = useRef(null);
  useEffect(() => {
    const prev = prevModeRef.current;
    if (prev && prev !== graphMode && MODE_REGISTRY[prev]?.onExit) {
      MODE_REGISTRY[prev].onExit(modeCtx);
    }
    if (graphMode && graphMode !== prev && MODE_REGISTRY[graphMode]?.onEnter) {
      MODE_REGISTRY[graphMode].onEnter(modeCtx);
    }
    prevModeRef.current = graphMode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphMode]);

  // ── Mode hotkeys ──
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      const key = e.key.toUpperCase();
      const entry = Object.entries(MODE_REGISTRY).find(([, v]) => v.hotkey === key);
      if (entry) {
        e.preventDefault();
        const [modeId] = entry;
        handleModeChange(graphMode === modeId ? null : modeId);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphMode, handleModeChange]);

  // ── Navigation (orchestrator mediates between domains) ──
  const navigateToNode = useCallback((nodeId) => {
    const existing = (filteredGraph.nodes || []).find(n => n.id === nodeId);
    const rawLabel = existing?.fullName || existing?.label || (nodeId.includes(':') ? nodeId.split(':').slice(1).join(':') : nodeId);
    const label = rawLabel.replace(/_/g, ' ');
    setSelectedEntity({ id: nodeId, label, type: nodeId.split(':')[0] || 'wallet' });
    search.setQuery(label);
    setContextNode(null);
  }, [filteredGraph.nodes, search]);

  const handleDrillDown = useCallback((nodeId, targetPage) => {
    if (!nav) return;
    const nodeType = nodeId.split(':')[0];
    const addr = nodeId.includes(':') ? nodeId.split(':')[1] : nodeId;
    if (targetPage === 'wallet' || nodeType === 'wallet') nav.onOpenWallet?.(addr);
    else if (targetPage === 'entity' || nodeType === 'entity' || nodeType === 'exchange') nav.onOpenEntity?.(addr);
    else if (targetPage === 'token' || nodeType === 'token') nav.onOpenToken?.(addr);
    else navigateToNode(nodeId);
  }, [nav, navigateToNode]);

  const handleCorridorClick = useCallback((corridor) => {
    if (corridor.source) {
      const label = corridor.source_label || corridor.source;
      setSelectedEntity({ id: corridor.source, label, type: corridor.source.split(':')[0] || 'dex' });
      search.setQuery(label);
    }
  }, [search]);

  // ── Route focus ──
  const handleRouteClick = useCallback((route) => {
    if (route?.sample_path?.length >= 2) { setActiveRoute(route); setIsRouteFocus(true); }
  }, []);
  const handleCloseRouteFocus = useCallback(() => { setActiveRoute(null); setIsRouteFocus(false); }, []);

  useEffect(() => {
    if (!isRouteFocus) return;
    const handleEsc = (e) => { if (e.key === 'Escape') handleCloseRouteFocus(); };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isRouteFocus, handleCloseRouteFocus]);

  // ── Orchestrator helpers ──
  const clearSelection = useCallback(() => {
    setSelectedEntity(null);
    search.clearSearch();
    setContextNode(null);
    clearGraph();
  }, [search, clearGraph]);

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // RENDER
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  const { isGraphFullscreen, graphContainerRef, showFilters, setShowFilters, edgeTypeFilters, setEdgeTypeFilters,
    resetFilters, toggleGraphFullscreen, showLeaderboard, setShowLeaderboard, showPlayback, setShowPlayback,
    playbackHighlights, setPlaybackHighlights, handlePlaybackActive, activeToolPanel, setActiveToolPanel } = controls;

  return (
    <div data-testid="graph-explorer" style={{ width: '100%' }}>
      {/* Search Bar */}
      <div className="mb-4 relative" style={{ flexShrink: 0 }}>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              data-testid="graph-search-input" type="text" value={search.query}
              onChange={(e) => search.setQuery(e.target.value)} onKeyDown={search.handleKeyDown}
              onFocus={search.openSuggestions}
              onBlur={search.closeSuggestionsDelayed}
              placeholder="Enter address (0x...) or entity name..."
              className="w-full pl-4 pr-4 py-3 rounded-xl border transition-all"
              style={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', color: '#0f172a' }}
              autoComplete="off"
            />
            {search.query && (
              <button onClick={search.clearSearch}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xl">x</button>
            )}
            {search.showSuggestions && search.suggestions.length > 0 && (
              <div data-testid="search-suggestions-dropdown" style={{
                position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '4px',
                backgroundColor: 'rgba(15, 23, 42, 0.98)', border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '12px', overflow: 'hidden', zIndex: 50,
                boxShadow: '0 10px 40px rgba(0,0,0,0.5)', backdropFilter: 'blur(12px)',
                maxHeight: '320px', overflowY: 'auto',
              }}>
                {search.suggestions.map((item, idx) => (
                  <button key={item.node_id || idx} data-testid={`suggestion-item-${idx}`}
                    onMouseDown={(e) => { e.preventDefault(); search.acceptSuggestion(item); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '10px',
                      width: '100%', padding: '10px 14px', textAlign: 'left',
                      backgroundColor: 'transparent', border: 'none', cursor: 'pointer',
                      borderBottom: idx < search.suggestions.length - 1 ? '1px solid rgba(148, 163, 184, 0.08)' : 'none',
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(139, 92, 246, 0.1)'}
                    onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <span style={{ fontSize: '10px', fontWeight: 600, color: '#94a3b8', backgroundColor: 'rgba(148, 163, 184, 0.1)', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase', minWidth: '44px', textAlign: 'center' }}>{item.type}</span>
                    <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 500 }}>{(item.label || '').replace(/_/g, ' ')}</span>
                    {item.chain && item.chain !== 'ethereum' && (
                      <span style={{ color: '#475569', fontSize: '10px', marginLeft: 'auto' }}>{item.chain}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button data-testid="graph-search-btn"
            onClick={() => search.topSuggestion ? search.acceptSuggestion() : search.executeSearch()}
            disabled={!search.query.trim() || search.isResolving}
            className="px-6 py-3 rounded-xl font-medium transition-all flex items-center gap-2 disabled:opacity-50"
            style={{ backgroundColor: '#10b981', color: 'white' }}>
            {search.isResolving && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            Search
          </button>
        </div>
      </div>

      {/* Selected Entity Badge */}
      {selectedEntity && (
        <div className="mb-4 flex items-center gap-2">
          <span className="text-sm text-slate-400">Showing graph for:</span>
          <span className="px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2" style={{ backgroundColor: '#6366f1', color: 'white' }}>
            {selectedEntity.label}
            <button onClick={clearSelection} className="hover:opacity-70">x</button>
          </span>
        </div>
      )}

      {/* Graph Container */}
      <div className="flex flex-col gap-4">
        <div
          ref={graphContainerRef}
          className={`${isGraphFullscreen ? '' : 'rounded-2xl'} border overflow-visible relative`}
          style={{ backgroundColor: '#0a0e1a', borderColor: 'rgba(100,116,139,0.15)', height: isGraphFullscreen ? '100vh' : 'calc(100vh - 290px)', minHeight: '400px' }}
          onMouseMove={hover.handleMouseMove}
        >
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center" style={{ backgroundColor: 'rgba(10, 14, 26, 0.8)' }}>
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {!loading && filteredGraph.nodes?.length === 0 && (
            <div data-testid="graph-empty-state" className="absolute inset-0 z-10 flex flex-col items-center justify-center" style={{ backgroundColor: 'rgba(10, 14, 26, 0.85)' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                <line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
              <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: '12px', fontWeight: 500 }}>
                {selectedEntity ? `No graph data for ${selectedChainKey ? selectedChainKey.charAt(0).toUpperCase() + selectedChainKey.slice(1) : 'this network'}` : 'Enter an address or entity name to explore the graph'}
              </p>
              <p style={{ color: '#475569', fontSize: '12px', marginTop: '4px' }}>
                {selectedEntity ? 'Try switching to another network' : 'Use the search bar above to start'}
              </p>
            </div>
          )}

          {/* Fullscreen Search Bar */}
          {isGraphFullscreen && (
            <div data-testid="fullscreen-search-container" style={{
              position: "absolute", top: "12px", zIndex: 12,
              left: "400px", right: "220px",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", maxWidth: "480px", width: "100%" }}>
                <div style={{ position: "relative", flex: 1 }}>
                <input data-testid="fullscreen-search-input" type="text" value={search.query}
                  onChange={(e) => search.setQuery(e.target.value)} onKeyDown={search.handleKeyDown}
                  onFocus={search.openSuggestions}
                  onBlur={search.closeSuggestionsDelayed}
                  placeholder="Search address or entity..."
                  style={{ width: "100%", padding: "8px 36px 8px 14px", borderRadius: "8px", border: "1px solid rgba(148, 163, 184, 0.2)", backgroundColor: "rgba(15, 23, 42, 0.9)", color: "#f1f5f9", fontSize: "13px", fontWeight: 500, backdropFilter: "blur(12px)", outline: "none" }}
                  autoComplete="off"
                />
                {search.query && (
                  <button data-testid="fullscreen-search-clear" onClick={search.clearSearch}
                    style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: "14px" }}>x</button>
                )}
                {search.showSuggestions && search.suggestions.length > 0 && (
                  <div data-testid="fullscreen-search-suggestions" style={{
                    position: "absolute", top: "100%", left: 0, right: 0, marginTop: "4px",
                    backgroundColor: "rgba(15, 23, 42, 0.98)", border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: "10px", overflow: "hidden", zIndex: 100,
                    boxShadow: "0 10px 40px rgba(0,0,0,0.6)", backdropFilter: "blur(12px)",
                    maxHeight: "280px", overflowY: "auto",
                  }}>
                    {search.suggestions.map((item, idx) => (
                      <button key={item.node_id || idx} data-testid={`fs-suggestion-${idx}`}
                        onMouseDown={(e) => { e.preventDefault(); search.acceptSuggestion(item); }}
                        style={{
                          display: "flex", alignItems: "center", gap: "8px",
                          width: "100%", padding: "8px 12px", textAlign: "left",
                          backgroundColor: "transparent", border: "none", cursor: "pointer",
                          borderBottom: idx < search.suggestions.length - 1 ? "1px solid rgba(148, 163, 184, 0.08)" : "none",
                          transition: "background-color 0.1s",
                        }}
                        onMouseEnter={e => e.currentTarget.style.backgroundColor = "rgba(139, 92, 246, 0.1)"}
                        onMouseLeave={e => e.currentTarget.style.backgroundColor = "transparent"}
                      >
                        <span style={{ fontSize: "9px", fontWeight: 600, color: "#94a3b8", backgroundColor: "rgba(148, 163, 184, 0.1)", padding: "2px 5px", borderRadius: "3px", textTransform: "uppercase" }}>{item.type}</span>
                        <span style={{ color: "#f1f5f9", fontSize: "12px", fontWeight: 500 }}>{(item.label || '').replace(/_/g, ' ')}</span>
                        {item.chain && item.chain !== 'ethereum' && (
                          <span style={{ color: "#475569", fontSize: "10px", marginLeft: "auto" }}>{item.chain}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button data-testid="fullscreen-search-btn"
                onClick={() => search.topSuggestion ? search.acceptSuggestion() : search.executeSearch()}
                disabled={!search.query.trim() || search.isResolving}
                style={{ padding: "8px 16px", borderRadius: "8px", border: "none", backgroundColor: "#10b981", color: "white", cursor: "pointer", fontSize: "13px", fontWeight: 600, whiteSpace: "nowrap", opacity: (!search.query.trim() || search.isResolving) ? 0.5 : 1, display: "flex", alignItems: "center", gap: "6px" }}>
                {search.isResolving && <div style={{ width: "12px", height: "12px", border: "2px solid white", borderTop: "2px solid transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />}
                Search
              </button>
              </div>
            </div>
          )}

          {/* Filter + Fullscreen buttons */}
          <div style={{ position: "absolute", top: "12px", right: "12px", zIndex: 11, display: "flex", alignItems: "center", gap: "8px" }}>
            <div style={{ position: "relative" }}>
              <button data-testid="graph-filter-btn" onClick={() => setShowFilters(!showFilters)}
                style={{
                  backgroundColor: showFilters ? "rgba(139, 92, 246, 0.8)" : "rgba(30, 41, 59, 0.8)",
                  border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "8px",
                  padding: "9.5px 12px", color: "#f8fafc", cursor: "pointer",
                  display: "flex", alignItems: "center", gap: "8px",
                  fontSize: "14px", fontWeight: 500, backdropFilter: "blur(10px)", transition: "all 0.2s ease",
                }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                </svg>
                <span>Filter</span>
              </button>
              {showFilters && (
                <div data-testid="graph-filter-panel" style={{
                  position: "absolute", top: "48px", right: 0,
                  backgroundColor: "rgba(15, 23, 42, 0.98)", border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: "12px", padding: "12px", minWidth: "200px", maxWidth: "240px",
                  maxHeight: "400px", overflowY: "auto", backdropFilter: "blur(10px)",
                  boxShadow: "0 10px 40px rgba(0,0,0,0.5)", zIndex: 1000,
                }}>
                  <div style={{ marginBottom: "10px" }}>
                    <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "4px", fontWeight: 600 }}>RELATION TYPES</div>
                    {Object.entries(edgeTypeFilters).map(([type, enabled]) => (
                      <label key={type} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 2px", cursor: "pointer" }}>
                        <input type="checkbox" checked={enabled}
                          onChange={(e) => setEdgeTypeFilters(prev => ({ ...prev, [type]: e.target.checked }))}
                          style={{ width: "12px", height: "12px", accentColor: "#10b981" }} />
                        <span style={{ color: "#e2e8f0", fontSize: "11px", textTransform: "capitalize" }}>{EDGE_TYPES[type]?.label || type}</span>
                      </label>
                    ))}
                  </div>
                  <div style={{ padding: "6px 4px", borderTop: "1px solid rgba(148, 163, 184, 0.1)" }}>
                    <div style={{ fontSize: "10px", color: "#64748b", marginBottom: "4px", fontWeight: 600 }}>DIRECTION</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px" }}>
                      <span style={{ display: "inline-block", width: "12px", height: "2px", backgroundColor: EDGE_COLOR_IN }} />
                      <span style={{ color: "#94a3b8", fontSize: "11px" }}>Incoming</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ display: "inline-block", width: "12px", height: "2px", backgroundColor: EDGE_COLOR_OUT }} />
                      <span style={{ color: "#94a3b8", fontSize: "11px" }}>Outgoing</span>
                    </div>
                  </div>
                  <div style={{ borderTop: "1px solid rgba(148, 163, 184, 0.1)", paddingTop: "10px", marginTop: "8px" }}>
                    <button data-testid="filter-reset-btn" onClick={resetFilters} style={{
                      width: "100%", padding: "6px", backgroundColor: "transparent",
                      border: "1px solid rgba(139, 92, 246, 0.3)", borderRadius: "5px",
                      color: "#a78bfa", fontSize: "11px", cursor: "pointer",
                    }}>Reset All</button>
                  </div>
                </div>
              )}
            </div>
            <button data-testid="graph-fullscreen-toolbar-btn" onClick={toggleGraphFullscreen}
              style={{
                backgroundColor: isGraphFullscreen ? "rgba(139, 92, 246, 0.8)" : "rgba(30, 41, 59, 0.8)",
                border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "8px",
                padding: "9.5px 12px", color: "#f8fafc", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "8px",
                fontSize: "14px", fontWeight: 500, backdropFilter: "blur(10px)", transition: "all 0.2s ease",
              }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {isGraphFullscreen
                  ? <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
                  : <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
                }
              </svg>
              <span>{isGraphFullscreen ? 'Exit' : 'Fullscreen'}</span>
            </button>
          </div>

          {/* Graph Toolbar */}
          <GraphToolbar
            graphMode={graphMode} onModeChange={handleModeChange}
            activeToolPanel={activeToolPanel} setActiveToolPanel={setActiveToolPanel}
            showLeaderboard={showLeaderboard} setShowLeaderboard={setShowLeaderboard}
            showPlayback={showPlayback} setShowPlayback={setShowPlayback}
            filteredGraphEdgesCount={filteredGraph.edges?.length || 0}
            selectedEntityId={selectedEntity?.id || null}
            onCorridorClick={handleCorridorClick} onRouteClick={handleRouteClick}
            onPlaybackToggle={() => { setShowPlayback(!showPlayback); if (showPlayback) { handlePlaybackActive(false); setPlaybackHighlights(null); } }}
          />

          {/* Canvas */}
          <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 'inherit' }}>
            <ForceGraphViewer
              graphData={filteredGraph}
              corridors={corridors}
              highlightedPath={highlightedPath}
              playbackHighlights={playbackHighlights}
              onNodeNavigate={navigateToNode}
              onNodeHover={hover.handleNodeHover}
              centerNodeId={selectedEntity?.id || null}
              hideFullscreen
              dimmed={isRouteFocus || cex.isCexFlowMode}
              activeRoute={activeRoute}
              cexRoutes={cex.isCexFlowMode ? cex.cexRoutes : []}
              onCexRouteLock={cex.handleCexRouteLock}
              cexUnlockTrigger={cex.cexUnlockTrigger}
            />

            {/* Mode HUDs */}
            <ModeHUD
              graphMode={graphMode} isCexFlowMode={cex.isCexFlowMode}
              isRouteFocus={isRouteFocus} activeRoute={activeRoute}
              cexRoutes={cex.cexRoutes} activeIntelligence={activeIntelligence}
              onCloseRouteFocus={handleCloseRouteFocus}
              onCloseCexFlow={() => { cex.setIsCexFlowMode(false); cex.setCexRoutes([]); setGraphMode(null); }}
              onCloseIntelMode={() => { setGraphMode(null); clearIntelligence(); }}
            />

            {/* CEX Locked Route Panel (bypassIntelligence — explicit rendering) */}
            {cex.lockedCexData && cex.isCexFlowMode && (
              <CexLockedPanel
                lockedCexData={cex.lockedCexData}
                expandedCluster={cex.expandedCluster}
                isPathsCollapsed={cex.isPathsCollapsed}
                onUnlock={cex.handleCexRouteUnlock}
                setExpandedCluster={cex.setExpandedCluster}
                setIsPathsCollapsed={cex.setIsPathsCollapsed}
              />
            )}

            {/* CEX Segment Analysis Panel */}
            {cex.expandedCluster && cex.lockedCexData && cex.isCexFlowMode && (
              <CexSegmentPanel
                expandedCluster={cex.expandedCluster}
                lockedCexData={cex.lockedCexData}
                copiedAddr={cex.copiedAddr}
                hideWeakLinks={cex.hideWeakLinks}
                setHideWeakLinks={cex.setHideWeakLinks}
                onClose={cex.handleCloseCluster}
                onCopyAddr={cex.handleCopyAddr}
              />
            )}

            {/* Intelligence Panel — driven by Mode Registry */}
            {modeResolved && !modeResolved.config.bypassIntelligence && activeIntelligence.length > 0 && !cex.lockedCexData && (
              <IntelligencePanel
                graphMode={graphMode}
                modeLabel={modeResolved.config.title}
                activeIntelligence={activeIntelligence}
                marketContext={modeResolved.data.marketContext}
                expandedWalletSignal={modeResolved.data.expandedWalletSignal}
                setExpandedWalletSignal={modeResolved.data.setExpandedWalletSignal}
                onClose={() => setGraphMode(null)}
              />
            )}

            {/* Wallet Detail Panel */}
            {expandedWalletSignal && (
              <WalletDetailPanel
                expandedWalletSignal={expandedWalletSignal}
                onClose={() => setExpandedWalletSignal(null)}
              />
            )}

            {/* Temporal Timeline */}
            <GraphTimeline style={{ position: 'absolute', bottom: '16px', left: '50%', transform: 'translateX(-50%)', zIndex: 10 }} />
          </div>

          {/* Node Context Panel */}
          {contextNode && (
            <NodeContextPanel
              nodeId={contextNode.id} nodeType={contextNode.type}
              onClose={() => setContextNode(null)}
              onNavigate={navigateToNode}
              onDrillDown={nav ? handleDrillDown : null}
            />
          )}

          {/* Leaderboard */}
          {showLeaderboard && !contextNode && (
            <SmartWalletLeaderboard onNavigate={navigateToNode} />
          )}

          {/* Playback Control */}
          {showPlayback && (
            <GraphPlaybackControl
              nodeId={selectedEntity?.id || ''}
              seeds={!selectedEntity && graphData?.nodes?.length ? graphData.nodes.slice(0, 20).map(n => n.id).join(',') : ''}
              onHighlightsChange={setPlaybackHighlights}
              onActiveChange={handlePlaybackActive}
            />
          )}

          {/* Hover Tooltip */}
          <HoverTooltip node={hover.hoveredNode} position={hover.position} />
        </div>

        {/* Risk Summary */}
        {selectedEntity && riskSummary && Object.keys(riskSummary).length > 0 && (
          <div className="rounded-2xl border overflow-hidden" style={{ backgroundColor: colors.background, borderColor: colors.border }}>
            <div className="p-4 border-b flex items-center gap-2" style={{ borderColor: colors.border }}>
              <Shield className="w-5 h-5 text-amber-400" />
              <h3 className="text-lg font-semibold" style={{ color: colors.text }}>Risk Analysis</h3>
              {riskSummary.score !== undefined && (
                <span className={`ml-auto px-3 py-1 rounded-full text-sm font-medium ${
                  riskSummary.score > 0.7 ? 'bg-red-400/20 text-red-400' :
                  riskSummary.score > 0.4 ? 'bg-amber-400/20 text-amber-400' : 'bg-emerald-400/20 text-emerald-400'
                }`}>Risk: {(riskSummary.score * 100).toFixed(0)}%</span>
              )}
            </div>
            <div className="p-4">
              {riskSummary.reasons?.map((reason, idx) => (
                <div key={idx} className="flex items-start gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                  <span className="text-sm" style={{ color: colors.textSecondary }}>{reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Relations Table — driven by useGraphRelations */}
        {selectedEntity && (
          <div className="rounded-2xl border overflow-hidden" style={{ backgroundColor: colors.background, borderColor: colors.border }}>
            <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: colors.border }}>
              <h4 className="text-sm font-medium flex items-center gap-2" style={{ color: colors.text }}>
                <Activity className="w-4 h-4 text-violet-400" /> Relations for {selectedEntity.label}
              </h4>
              <span className="text-xs text-slate-400">{rels.relations.length} relations</span>
            </div>
            <div className="overflow-auto" style={{ maxHeight: '200px' }}>
              {rels.loading ? (
                <div className="flex items-center justify-center py-8"><div className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" /></div>
              ) : rels.relations.length === 0 ? (
                <div className="flex items-center justify-center py-8 text-slate-500 text-sm">No relations found</div>
              ) : (
                <table className="w-full">
                  <thead className="sticky top-0" style={{ backgroundColor: colors.background }}>
                    <tr className="text-xs text-slate-400 border-b" style={{ borderColor: colors.border }}>
                      <th className="text-left p-3 w-20">Type</th>
                      <th className="text-left p-3">Entity</th>
                      <th className="text-left p-3">Relation</th>
                      <th className="text-left p-3 w-20">Direction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rels.paginatedRelations.map((rel, idx) => (
                      <tr key={rel.id || idx} className="border-b hover:bg-slate-800/50 cursor-pointer" style={{ borderColor: colors.border }} onClick={() => rels.navigateToEntity(rel)}>
                        <td className="p-3"><span className="text-xs text-slate-400 capitalize">{rel.type}</span></td>
                        <td className="p-3"><span className="text-sm font-medium" style={{ color: colors.text }}>{rel.entity}</span></td>
                        <td className="p-3 text-xs text-slate-400">{rel.relation}</td>
                        <td className="p-3">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${rel.direction === 'in' ? 'text-emerald-400 bg-emerald-400/10' : 'text-red-400 bg-red-400/10'}`}>
                            {rel.direction === 'in' ? 'IN' : 'OUT'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            {rels.totalPages > 1 && (
              <div className="p-3 border-t flex items-center justify-between" style={{ borderColor: colors.border }}>
                <div className="flex items-center gap-1">
                  <button onClick={() => rels.setPage(p => Math.max(1, p - 1))} disabled={rels.page === 1} className="p-1 rounded hover:bg-slate-700 disabled:opacity-50"><ChevronLeft className="w-4 h-4 text-slate-400" /></button>
                  {[...Array(Math.min(5, rels.totalPages))].map((_, i) => (
                    <button key={i + 1} onClick={() => rels.setPage(i + 1)}
                      className={`w-7 h-7 rounded text-xs ${rels.page === i + 1 ? 'bg-emerald-500 text-white' : 'text-slate-400 hover:bg-slate-700'}`}>{i + 1}</button>
                  ))}
                  <button onClick={() => rels.setPage(p => Math.min(rels.totalPages, p + 1))} disabled={rels.page === rels.totalPages} className="p-1 rounded hover:bg-slate-700 disabled:opacity-50"><ChevronRight className="w-4 h-4 text-slate-400" /></button>
                </div>
                <span className="text-xs text-slate-500">{(rels.page - 1) * 10 + 1} - {Math.min(rels.page * 10, rels.relations.length)} of {rels.relations.length}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphExplorer;
