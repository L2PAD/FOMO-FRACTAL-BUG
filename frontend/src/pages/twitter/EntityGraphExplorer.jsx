import React, { useState, useEffect, useCallback } from 'react';
import { Activity, TrendingUp, AlertCircle, Zap, BarChart3, Globe, Users, Wallet, Code2, Hash, Shield } from 'lucide-react';
import ForceGraphViewer from './EntityForceGraph';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TYPE_COLORS = {
  token: '#f59e0b',
  project: '#3b82f6',
  protocol: '#8b5cf6',
  fund: '#10b981',
  person: '#ec4899',
  twitter_account: '#06b6d4',
  chain: '#6366f1',
  developer: '#14b8a6',
  wallet: '#6b7280',
  exchange: '#ef4444',
  cex: '#ef4444',
};

const TYPE_ICONS = {
  token: Hash,
  project: Globe,
  protocol: Code2,
  fund: Wallet,
  person: Users,
  twitter_account: Users,
  chain: Globe,
  developer: Code2,
  exchange: BarChart3,
  cex: BarChart3,
};

const GraphExplorer = ({ colors }) => {
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [relations, setRelations] = useState([]);
  const [loadingRelations, setLoadingRelations] = useState(false);
  const [graphStats, setGraphStats] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [signalStats, setSignalStats] = useState(null);
  const [resolutionStats, setResolutionStats] = useState(null);
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [activePanel, setActivePanel] = useState('radar');

  const loadGraphIntelligence = useCallback(async () => {
    setLoadingIntelligence(true);
    try {
      const [statsRes, radarRes, signalsRes, resolutionRes] = await Promise.all([
        fetch(`${API_URL}/api/graph/stats`),
        fetch(`${API_URL}/api/radar`),
        fetch(`${API_URL}/api/graph-signals/stats`),
        fetch(`${API_URL}/api/graph/resolution/stats`)
      ]);
      if (statsRes.ok) setGraphStats(await statsRes.json());
      if (radarRes.ok) setRadarData(await radarRes.json());
      if (signalsRes.ok) setSignalStats(await signalsRes.json());
      if (resolutionRes.ok) setResolutionStats(await resolutionRes.json());
    } catch (err) {
      console.error('Failed to load intelligence:', err);
    } finally {
      setLoadingIntelligence(false);
    }
  }, []);

  useEffect(() => { loadGraphIntelligence(); }, [loadGraphIntelligence]);

  const getSuggestions = useCallback(async (query) => {
    if (!query || query.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    setIsSearching(true);
    try {
      const res = await fetch(`${API_URL}/api/graph/entities/search?q=${encodeURIComponent(query)}&limit=6`);
      if (res.ok) {
        const data = await res.json();
        setSuggestions(data.results || []);
        setShowSuggestions((data.results || []).length > 0);
      }
    } catch { setSuggestions([]); }
    finally { setIsSearching(false); }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => getSuggestions(searchQuery), 200);
    return () => clearTimeout(timer);
  }, [searchQuery, getSuggestions]);

  const executeSearch = async () => {
    const query = searchQuery.trim();
    if (!query) return;
    setIsResolving(true);
    setSearchError(null);
    try {
      const res = await fetch(`${API_URL}/api/graph/search/advanced?q=${encodeURIComponent(query)}&auto_create=true`);
      if (res.ok) {
        const data = await res.json();
        if (data.found && data.entity) {
          setSelectedEntity(data.entity);
          loadRelations(data.entity);
        } else {
          setSearchError(`"${query}" not found`);
          if (data.suggestions?.length) {
            setSearchError(`"${query}" not found. Try: ${data.suggestions.map(s => s.label).join(', ')}`);
          }
        }
      }
    } catch { setSearchError('Search failed'); }
    finally { setIsResolving(false); }
  };

  const loadRelations = async (entity) => {
    if (!entity) return;
    setLoadingRelations(true);
    try {
      const [entityType, ...rest] = entity.id.split(':');
      const entityName = rest.join(':');
      const res = await fetch(`${API_URL}/api/graph/edges/${entityType}/${entityName}?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setRelations(data.edges || []);
      }
    } catch { setRelations([]); }
    finally { setLoadingRelations(false); }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      setShowSuggestions(false);
      executeSearch();
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const selectSuggestion = async (s) => {
    setSearchQuery(s.label);
    setSuggestions([]);
    setShowSuggestions(false);
    // Execute search directly with the selected entity
    setIsResolving(true);
    setSearchError(null);
    try {
      const res = await fetch(`${API_URL}/api/graph/search/advanced?q=${encodeURIComponent(s.label)}&auto_create=true`);
      if (res.ok) {
        const data = await res.json();
        if (data.found && data.entity) {
          setSelectedEntity(data.entity);
          loadRelations(data.entity);
        }
      }
    } catch { setSearchError('Search failed'); }
    finally { setIsResolving(false); }
  };

  const StatCard = ({ label, value, sub, color }) => (
    <div data-testid={`stat-${label.toLowerCase().replace(/\s/g,'-')}`} className="px-3 py-2" style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
      <div className="text-xs" style={{ color: '#64748b' }}>{label}</div>
      <div className="text-lg font-semibold" style={{ color: color || '#f1f5f9' }}>{value}</div>
      {sub && <div className="text-xs" style={{ color: '#475569' }}>{sub}</div>}
    </div>
  );

  const graphActive = !!selectedEntity;

  return (
    <div data-testid="graph-explorer" className="flex flex-col">

      {/* Search Bar — light theme, dropdown suggestions */}
      <div className="px-6 py-4">
        <div className="relative flex gap-2 max-w-[1600px] mx-auto">
          <div className="relative flex-1">
            <input
              data-testid="graph-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setSearchError(null); }}
              onKeyDown={handleKeyDown}
              onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
              onBlur={() => { setTimeout(() => setShowSuggestions(false), 200); }}
              placeholder="Search entity: Solana, BTC, a16z, Vitalik..."
              className="w-full px-4 py-3 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:border-gray-300"
            />
            {searchQuery && (
              <button onClick={() => { setSearchQuery(''); setSuggestions([]); setShowSuggestions(false); setSelectedEntity(null); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-lg">×</button>
            )}

            {/* Dropdown suggestions */}
            {showSuggestions && suggestions.length > 0 && (
              <div data-testid="search-suggestions" className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg overflow-hidden" style={{ zIndex: 50 }}>
                {suggestions.map((s, i) => (
                  <button key={s.id || i}
                    data-testid={`suggestion-${i}`}
                    onMouseDown={(e) => { e.preventDefault(); selectSuggestion(s); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
                  >
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: TYPE_COLORS[s.type] || '#6b7280' }} />
                    <span className="text-sm text-gray-900 font-medium">{s.label}</span>
                    <span className="text-xs text-gray-400">{s.type}</span>
                    {s.source && <span className="text-xs text-gray-300 ml-auto">{s.source}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button data-testid="graph-search-btn" onClick={executeSearch} disabled={isResolving || !searchQuery.trim()}
            className="px-6 py-3 text-sm font-medium rounded-lg transition-colors disabled:opacity-40"
            style={{ background: '#10b981', color: '#fff' }}>
            {isResolving ? '...' : 'Search'}
          </button>
        </div>
        {searchError && <div className="text-xs mt-1 px-1 max-w-[1600px] mx-auto text-red-500">{searchError}</div>}

        {selectedEntity && (
          <div className="flex items-center gap-2 text-xs mt-2 max-w-[1600px] mx-auto text-gray-500">
            <div className="w-2 h-2 rounded-full" style={{ background: TYPE_COLORS[selectedEntity.type] || '#6b7280' }} />
            <span className="text-gray-800 font-medium">{selectedEntity.label}</span>
            <span className="text-gray-400">({selectedEntity.type})</span>
            <span className="text-gray-300">·</span>
            <span>{relations.length} edges</span>
          </div>
        )}
      </div>

      {/* Graph + Intelligence — dark block */}
      <div className="mx-4 rounded-xl overflow-hidden" style={{ background: '#0a0e1a' }}>

        {/* Graph Canvas or Empty State */}
        {graphActive ? (
          <div data-testid="graph-container" style={{ height: 500, position: 'relative' }}>
            <ForceGraphViewer
              centerEntity={selectedEntity?.id || null}
              onEntitySelect={(entity) => {
                if (entity?.id) {
                  setSelectedEntity(entity);
                  setSearchQuery(entity.label || entity.id.split(':').pop());
                  loadRelations(entity);
                }
              }}
              colors={{ ...TYPE_COLORS, background: '#0a0e1a', text: '#e2e8f0', edge: '#1e293b', edgeHighlight: '#f59e0b' }}
            />
          </div>
        ) : (
          <div data-testid="graph-empty-state" className="flex flex-col items-center justify-center" style={{ height: 340 }}>
            <div className="w-16 h-16 mb-4 rounded-full flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.04)' }}>
              <Globe className="w-7 h-7" style={{ color: '#334155' }} />
            </div>
            <div className="text-sm font-medium" style={{ color: '#475569' }}>Knowledge Graph</div>
            <div className="text-xs mt-1" style={{ color: '#334155' }}>Enter an asset above to explore its connections</div>
          </div>
        )}

        {/* Intelligence Panel Tabs */}
        <div className="flex gap-1 px-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          {[
            { key: 'radar', label: 'Radar', icon: Zap },
            { key: 'signals', label: 'Signals', icon: TrendingUp },
            { key: 'graph', label: 'Graph Health', icon: Activity },
            { key: 'edges', label: 'Edges', icon: BarChart3 },
          ].map(tab => (
            <button key={tab.key} data-testid={`tab-${tab.key}`}
              onClick={() => setActivePanel(tab.key)}
              className="flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors"
              style={{
                color: activePanel === tab.key ? '#f1f5f9' : '#64748b',
                borderBottom: activePanel === tab.key ? '2px solid #f1f5f9' : '2px solid transparent',
                background: 'transparent',
              }}>
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
          <button data-testid="intelligence-refresh" onClick={loadGraphIntelligence}
            className="ml-auto px-2 py-1 text-xs" style={{ color: '#475569' }}>
            {loadingIntelligence ? '...' : '↻'}
          </button>
        </div>

        {/* Panel Content */}
        <div className="px-4 pb-4">

          {/* Panel: Radar */}
          {activePanel === 'radar' && radarData && (
            <div data-testid="panel-radar" className="grid grid-cols-3 gap-3 pt-3">
              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3">
                <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>HOT TOKENS</div>
                <div className="flex flex-col gap-1">
                  {(radarData.hot_tokens || []).slice(0, 8).map((t, i) => (
                    <div key={i} className="flex justify-between items-center text-xs py-0.5 cursor-pointer"
                      onClick={() => { setSearchQuery(t.token.replace('token:','')); }}
                      style={{ color: '#cbd5e1' }}>
                      <span>{t.token.replace('token:','')}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: '#475569' }}>{t.signal_count}sig</span>
                        <span className="font-medium" style={{ color: t.strength > 50 ? '#10b981' : '#f59e0b' }}>{t.strength}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3">
                <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>FUND PRESSURE</div>
                <div className="flex flex-col gap-1">
                  {(radarData.fund_pressure || []).slice(0, 8).map((f, i) => (
                    <div key={i} className="flex justify-between items-center text-xs py-0.5 cursor-pointer"
                      onClick={() => { setSearchQuery(f.label); }}
                      style={{ color: '#cbd5e1' }}>
                      <span className="truncate max-w-[120px]">{f.label}</span>
                      <span className="font-medium" style={{ color: f.strength > 50 ? '#10b981' : '#f59e0b' }}>{f.strength}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3">
                <div className="text-xs font-medium mb-2 flex items-center gap-1" style={{ color: '#f87171' }}>
                  <AlertCircle className="w-3 h-3" /> PRE-PUMP ALERTS
                </div>
                <div className="flex flex-col gap-1">
                  {(radarData.pre_pumps || []).slice(0, 8).map((p, i) => (
                    <div key={i} className="flex justify-between items-center text-xs py-0.5 cursor-pointer"
                      onClick={() => { setSearchQuery(p.token.replace('token:','')); }}
                      style={{ color: '#cbd5e1' }}>
                      <span>{p.token.replace('token:','')}</span>
                      <span className="font-medium" style={{ color: '#f87171' }}>{p.score}</span>
                    </div>
                  ))}
                  {(!radarData.pre_pumps?.length) && <div className="text-xs" style={{ color: '#334155' }}>No alerts</div>}
                </div>
              </div>
            </div>
          )}

          {/* Panel: Signals */}
          {activePanel === 'signals' && signalStats && (
            <div data-testid="panel-signals" className="grid grid-cols-5 gap-3 pt-3">
              <StatCard label="Total Signals" value={signalStats.total_signals_logged || 0} color="#3b82f6" />
              <StatCard label="Token Signals" value={signalStats.token_signals || 0} color="#f59e0b" />
              <StatCard label="Fund Signals" value={signalStats.fund_signals || 0} color="#10b981" />
              <StatCard label="Signal Edges" value={signalStats.signal_edges || 0} color="#8b5cf6" />
              <StatCard label="Active Funds" value={signalStats.active_funds || 0} color="#ec4899" />
              {signalStats.by_type && Object.entries(signalStats.by_type).map(([type, count]) => (
                <StatCard key={type} label={type} value={count} color="#64748b" />
              ))}
            </div>
          )}

          {/* Panel: Graph Health */}
          {activePanel === 'graph' && (
            <div data-testid="panel-graph" className="grid grid-cols-2 gap-3 pt-3">
              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3">
                <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>NODE TYPES</div>
                <div className="flex flex-col gap-1">
                  {graphStats?.nodes_by_type && Object.entries(graphStats.nodes_by_type).slice(0, 10).map(([type, count]) => {
                    const Icon = TYPE_ICONS[type] || Shield;
                    return (
                      <div key={type} className="flex justify-between items-center text-xs py-0.5" style={{ color: '#cbd5e1' }}>
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full" style={{ background: TYPE_COLORS[type] || '#6b7280' }} />
                          <Icon className="w-3 h-3" style={{ color: TYPE_COLORS[type] || '#6b7280' }} />
                          <span>{type}</span>
                        </div>
                        <span style={{ color: '#64748b' }}>{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3">
                <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>EDGE TYPES</div>
                <div className="flex flex-col gap-1">
                  {graphStats?.edges_by_type && Object.entries(graphStats.edges_by_type).slice(0, 10).map(([type, count]) => (
                    <div key={type} className="flex justify-between items-center text-xs py-0.5" style={{ color: '#cbd5e1' }}>
                      <span>{type}</span>
                      <span style={{ color: '#64748b' }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {resolutionStats && (
                <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="col-span-2 p-3">
                  <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>RESOLUTION</div>
                  <div className="grid grid-cols-5 gap-2">
                    <StatCard label="Nodes" value={resolutionStats.total_nodes || 0} />
                    <StatCard label="Meaningful" value={resolutionStats.meaningful_nodes || 0} color="#3b82f6" />
                    <StatCard label="Orphans" value={resolutionStats.meaningful_orphans || 0} color={resolutionStats.meaningful_orphans > 50 ? '#f87171' : '#10b981'} />
                    <StatCard label="Unresolved %" value={`${resolutionStats.meaningful_unresolved_pct || 0}%`} color={resolutionStats.meaningful_unresolved_pct > 5 ? '#f87171' : '#10b981'} />
                    <StatCard label="Aliases" value={resolutionStats.aliases || 0} color="#8b5cf6" />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Panel: Edges */}
          {activePanel === 'edges' && (
            <div data-testid="panel-edges" style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8 }} className="p-3 mt-3">
              {!selectedEntity ? (
                <div className="text-xs text-center py-4" style={{ color: '#334155' }}>Search for an entity to see its edges</div>
              ) : loadingRelations ? (
                <div className="text-xs text-center py-4" style={{ color: '#475569' }}>Loading...</div>
              ) : (
                <>
                  <div className="text-xs font-medium mb-2" style={{ color: '#94a3b8' }}>
                    EDGES FOR {selectedEntity.label?.toUpperCase()} ({relations.length})
                  </div>
                  <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto">
                    {relations.map((edge, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs py-1 px-1 cursor-pointer hover:opacity-80"
                        onClick={() => {
                          const targetId = edge.target === selectedEntity.id ? edge.source : edge.target;
                          setSearchQuery(targetId.split(':').pop());
                        }}
                        style={{ color: '#cbd5e1', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <span className="truncate max-w-[140px]">{edge.source_label || edge.source?.split(':').pop()}</span>
                        <span style={{ color: '#475569', fontSize: 10 }}>{edge.relation}</span>
                        <span className="truncate max-w-[140px]">{edge.target_label || edge.target?.split(':').pop()}</span>
                      </div>
                    ))}
                    {relations.length === 0 && <div className="text-xs py-2" style={{ color: '#334155' }}>No edges found</div>}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Summary Bar */}
        {graphStats && (
          <div data-testid="graph-summary" className="flex items-center gap-4 text-xs px-4 pb-3" style={{ color: '#475569' }}>
            <span>{graphStats.total_nodes?.toLocaleString()} nodes</span>
            <span>·</span>
            <span>{graphStats.total_edges?.toLocaleString()} edges</span>
            {radarData?.stats && (
              <>
                <span>·</span>
                <span style={{ color: '#10b981' }}>{radarData.stats.active_funds} active funds</span>
                <span>·</span>
                <span style={{ color: '#f87171' }}>{radarData.stats.pre_pump_alerts} pre-pump</span>
                <span>·</span>
                <span>{radarData.stats.total_signals_logged} signals</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphExplorer;
