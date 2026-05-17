/**
 * Exchange Labs — Indicator Intelligence System
 * 
 * 3 modes: Global / Universe / Asset
 * No borders, no shadows. Typography + whitespace driven.
 * Labs diagnose; they don't decide.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw, Loader2, Search, X, ChevronRight, Globe, BarChart3,
  Activity, Waves, Target, Shield, ArrowRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const GROUP_ICONS = {
  'Market Structure': Activity,
  'Flow & Participation': Waves,
  'Smart Money & Risk': Target,
  'Meta / Quality': Shield,
};

const STATE_COLORS = {
  TRENDING: '#16a34a', RANGING: '#94a3b8', TRANSITION: '#d97706', NEUTRAL: '#94a3b8',
  COMPRESSION: '#d97706', HIGH: '#dc2626', NORMAL: '#94a3b8', LOW: '#64748b',
  THIN: '#dc2626', DEEP: '#16a34a',
  STABLE: '#16a34a', STRESSED: '#dc2626', PANIC: '#dc2626',
  BUYERS: '#16a34a', SELLERS: '#dc2626', BALANCED: '#94a3b8',
  SPIKE: '#d97706', STRONG_UP: '#16a34a', STRONG_DOWN: '#dc2626',
  EXPANDING: '#16a34a', NARROWING: '#dc2626', MODERATE: '#94a3b8',
  ACTIVE_LONG: '#16a34a', ACTIVE_SHORT: '#dc2626', QUIET: '#94a3b8',
  HIGH_RISK: '#dc2626', CLEAN: '#16a34a',
  CASCADE_RISK: '#dc2626', ELEVATED: '#d97706',
  DEGRADED: '#d97706', HEALTHY: '#16a34a',
  ALIGNED: '#16a34a', CONFLICTED: '#dc2626',
};

const OVERALL_STATE_COLORS = {
  BREAKOUT_ACTIVE: '#16a34a',
  BREAKOUT_BUILDING: '#d97706',
  DISTRIBUTION: '#dc2626',
  LIQUIDITY_TRAP: '#dc2626',
  RANGE_CHOP: '#94a3b8',
  DATA_WEAK: '#64748b',
};

function sc(state) { return STATE_COLORS[state] || '#94a3b8'; }

/* ═══════════════════════ Tooltip ═══════════════════════ */
function HoverTooltip({ text, children, position = 'bottom' }) {
  const [show, setShow] = useState(false);
  if (!text) return children;
  const isUp = position === 'top';
  return (
    <div className="relative inline-flex" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div className="absolute z-50 left-0 w-64 px-3 py-2 rounded-lg pointer-events-none text-[12px]"
          style={{
            ...(isUp ? { bottom: '100%', marginBottom: 6 } : { top: '100%', marginTop: 6 }),
            background: '#0f172a', color: '#e2e8f0',
            boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
          }}>
          {text}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════ Lab Card ═══════════════════════ */
function LabCard({ lab, onDrilldown }) {
  const color = sc(lab.state);
  return (
    <button data-testid={`lab-card-${lab.lab}`} onClick={() => onDrilldown(lab.lab)}
      className="text-left w-full py-4 transition-opacity duration-150 hover:opacity-80"
      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
      <div className="flex items-center justify-between mb-1.5">
        <HoverTooltip text={lab.description}>
          <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: '#94a3b8' }}>
            {lab.displayName}
          </span>
        </HoverTooltip>
        <ChevronRight className="w-3 h-3" style={{ color: '#cbd5e1' }} />
      </div>
      <div className="flex items-center gap-3">
        <span className="text-[18px] font-bold" style={{ color }}>{lab.state.replace(/_/g, ' ')}</span>
        <span className="text-[12px] font-semibold" style={{ color: '#0f172a' }}>{(lab.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="flex items-center gap-4 mt-2">
        <div className="flex-1">
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
            <div className="h-full rounded-full transition-all" style={{ width: `${lab.abnormality * 100}%`, background: color }} />
          </div>
        </div>
        <div className="flex gap-3 text-[10px] font-semibold shrink-0">
          <span style={{ color: lab.riskContribution >= 0.5 ? '#dc2626' : '#64748b' }}>
            Risk {(lab.riskContribution * 100).toFixed(0)}
          </span>
          <span style={{ color: lab.convictionContribution > 0.1 ? '#16a34a' : lab.convictionContribution < -0.1 ? '#dc2626' : '#64748b' }}>
            Conv {lab.convictionContribution > 0 ? '+' : ''}{(lab.convictionContribution * 100).toFixed(0)}
          </span>
        </div>
      </div>
    </button>
  );
}

/* ═══════════════════════ Drilldown Drawer ═══════════════════════ */
function DrilldownDrawer({ data, onClose }) {
  if (!data) return null;
  const color = sc(data.state);
  return (
    <div data-testid="lab-drilldown" className="fixed inset-0 z-50 flex justify-end"
      style={{ background: 'rgba(0,0,0,0.2)' }} onClick={onClose}>
      <div className="w-full max-w-lg bg-white h-full overflow-y-auto" onClick={e => e.stopPropagation()}
        style={{ boxShadow: '-8px 0 40px rgba(0,0,0,0.08)' }}>
        <div className="px-8 py-6">
          <div className="flex items-center justify-between mb-6">
            <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: '#94a3b8' }}>
              {data.displayName} — Drilldown
            </span>
            <button onClick={onClose}><X className="w-4 h-4" style={{ color: '#94a3b8' }} /></button>
          </div>

          <div className="text-[28px] font-bold mb-1" style={{ color }}>{data.state.replace(/_/g, ' ')}</div>
          <div className="text-[13px] mb-6" style={{ color: '#64748b' }}>
            Confidence {(data.confidence * 100).toFixed(0)}% · Abnormality {(data.abnormality * 100).toFixed(0)}%
          </div>

          {/* Impact */}
          <div className="flex gap-8 mb-8">
            <div>
              <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Risk</div>
              <div className="text-[18px] font-bold" style={{ color: data.riskContribution >= 0.5 ? '#dc2626' : '#0f172a' }}>
                {(data.riskContribution * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Conviction</div>
              <div className="text-[18px] font-bold" style={{ color: data.convictionContribution > 0.05 ? '#16a34a' : data.convictionContribution < -0.05 ? '#dc2626' : '#0f172a' }}>
                {data.convictionContribution > 0 ? '+' : ''}{(data.convictionContribution * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Source</div>
              <div className="text-[14px] font-bold" style={{ color: '#0f172a' }}>{data.sourceType}</div>
            </div>
          </div>

          {/* Horizon */}
          <div className="mb-8">
            <div className="text-[10px] uppercase font-semibold mb-2" style={{ color: '#94a3b8' }}>Horizon Impact</div>
            <div className="flex gap-4">
              {Object.entries(data.horizonW || {}).map(([h, w]) => (
                <div key={h} className="flex-1">
                  <div className="text-[11px] font-semibold mb-1" style={{ color: '#64748b' }}>{h}</div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
                    <div className="h-full rounded-full" style={{ width: `${w * 100}%`, background: '#6366f1' }} />
                  </div>
                  <div className="text-[11px] font-semibold mt-0.5" style={{ color: '#0f172a' }}>{(w * 100).toFixed(0)}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* Metrics table */}
          <div className="mb-8">
            <div className="text-[10px] uppercase font-semibold mb-3" style={{ color: '#94a3b8' }}>Raw Metrics</div>
            {data.metrics?.map(m => (
              <div key={m.key} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
                <span className="flex-1 text-[13px] font-medium" style={{ color: '#0f172a' }}>{m.key.replace(/_/g, ' ')}</span>
                <span className="text-[12px] tabular-nums font-semibold" style={{ color: '#0f172a' }}>{typeof m.raw === 'number' ? m.raw.toFixed(4) : String(m.raw)}</span>
                <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
                  <div className="h-full rounded-full" style={{ width: `${m.norm * 100}%`, background: m.abnormality > 0.6 ? '#dc2626' : m.abnormality > 0.3 ? '#d97706' : '#16a34a' }} />
                </div>
                <span className="text-[11px] tabular-nums w-8 text-right font-semibold" style={{ color: '#0f172a' }}>{(m.norm * 100).toFixed(0)}</span>
              </div>
            ))}
          </div>

          {/* Evidence */}
          {data.evidence?.length > 0 && (
            <div className="mb-8">
              <div className="text-[10px] uppercase font-semibold mb-2" style={{ color: '#94a3b8' }}>Evidence</div>
              {data.evidence.map((e, i) => (
                <div key={i} className="text-[13px] py-1" style={{ color: '#0f172a' }}>· {e}</div>
              ))}
            </div>
          )}

          {/* Risks */}
          {data.risks?.length > 0 && (
            <div>
              <div className="text-[10px] uppercase font-semibold mb-2" style={{ color: '#94a3b8' }}>Risk Tags</div>
              <div className="flex gap-2 flex-wrap">
                {data.risks.map((r, i) => (
                  <span key={i} className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ color: '#dc2626', background: 'rgba(220,38,38,0.06)' }}>
                    {r.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════ Universe View ═══════════════════════ */
function UniverseView({ data }) {
  if (!data) return null;
  const { stateDistribution, topEdges, labHeat, universeSize } = data;
  return (
    <div data-testid="universe-view">
      <div className="text-[11px] uppercase tracking-wider font-semibold mb-4" style={{ color: '#94a3b8' }}>
        Universe — {universeSize} assets
      </div>

      {/* State Distribution */}
      <div className="mb-8">
        <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#64748b' }}>State Distribution</div>
        <div className="flex gap-4 flex-wrap">
          {Object.entries(stateDistribution).map(([key, val]) => (
            <div key={key} className="min-w-[100px]">
              <div className="text-[13px] font-bold" style={{ color: OVERALL_STATE_COLORS[key] || '#94a3b8' }}>
                {key.replace(/_/g, ' ')}
              </div>
              <div className="text-[18px] font-bold" style={{ color: '#0f172a' }}>{val.pct}%</div>
              <div className="text-[11px]" style={{ color: '#94a3b8' }}>{val.count} assets</div>
            </div>
          ))}
        </div>
      </div>

      {/* Lab Heat */}
      <div className="mb-8">
        <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#64748b' }}>Lab Abnormality Heat</div>
        {labHeat?.slice(0, 8).map(h => (
          <div key={h.lab} className="flex items-center gap-3 py-1.5">
            <span className="text-[13px] font-medium w-32" style={{ color: '#0f172a' }}>{h.lab.replace(/_/g, ' ')}</span>
            <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
              <div className="h-full rounded-full" style={{ width: `${h.avgAbnormality * 100}%`, background: h.avgAbnormality > 0.6 ? '#dc2626' : h.avgAbnormality > 0.35 ? '#d97706' : '#16a34a' }} />
            </div>
            <span className="text-[12px] tabular-nums font-semibold w-10 text-right" style={{ color: '#0f172a' }}>{(h.avgAbnormality * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>

      {/* Top Edges */}
      <div>
        <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#64748b' }}>Top Edges</div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-2">
          {topEdges?.slice(0, 20).map((e, i) => (
            <div key={e.symbol} className="flex items-center gap-2 py-1">
              <span className="text-[12px] font-bold" style={{ color: '#0f172a' }}>{e.symbol.replace('USDT', '')}</span>
              <span className="text-[11px] font-semibold" style={{ color: OVERALL_STATE_COLORS[e.state] || '#94a3b8' }}>
                {e.state.replace(/_/g, ' ')}
              </span>
              <span className="text-[11px] tabular-nums ml-auto font-semibold" style={{ color: '#0f172a' }}>{(e.confidence * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════ Main Page ═══════════════════════ */
export default function LabsPage({ externalMode, externalSymbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [_mode, _setMode] = useState('global');
  const [_symbol, _setSymbol] = useState('BTCUSDT');
  const [symbols, setSymbols] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [drilldown, setDrilldown] = useState(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [, setSearchParams] = useSearchParams();
  const searchRef = useRef(null);

  // Use external mode/symbol if provided (from ExchangePage insights bar)
  const hasExternal = externalMode !== undefined;
  const mode = hasExternal ? externalMode : _mode;
  const symbol = hasExternal ? (externalSymbol || 'BTCUSDT') : _symbol;
  const setMode = hasExternal ? () => {} : _setMode;
  const setSymbol = hasExternal ? () => {} : _setSymbol;

  const fetchLabs = useCallback(async () => {
    setLoading(true);
    try {
      const params = mode === 'asset' ? `mode=asset&asset=${symbol}` : `mode=${mode}`;
      const res = await fetch(`${API}/api/exchange/labs?${params}`);
      const d = await res.json();
      setData(d);
    } catch (e) { console.error('Labs fetch error:', e); }
    setLoading(false);
  }, [mode, symbol]);

  useEffect(() => { fetchLabs(); }, [fetchLabs]);

  useEffect(() => {
    fetch(`${API}/api/exchange/labs/symbols`).then(r => r.json()).then(d => setSymbols(d.symbols || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!searchOpen) return;
    const handler = (e) => { if (searchRef.current && !searchRef.current.contains(e.target)) { setSearchOpen(false); setSearchQuery(''); } };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [searchOpen]);

  const selectSymbol = (s) => {
    setSymbol(s);
    setMode('asset');
    setSearchOpen(false);
    setSearchQuery('');
  };

  const openDrilldown = async (labKey) => {
    setDrilldownLoading(true);
    try {
      const asset = mode === 'asset' ? symbol : 'BTCUSDT';
      const res = await fetch(`${API}/api/exchange/labs/drilldown?lab=${labKey}&asset=${asset}`);
      const d = await res.json();
      if (d.ok) setDrilldown(d);
    } catch (e) { console.error('Drilldown error:', e); }
    setDrilldownLoading(false);
  };

  const filteredSymbols = searchQuery
    ? symbols.filter(s => s.replace('USDT', '').toLowerCase().includes(searchQuery.toLowerCase())).slice(0, 20)
    : symbols.slice(0, 20);

  return (
    <div className="max-w-5xl mx-auto px-4 pb-16" style={{ animation: 'fadeIn 0.3s ease-out' }}>
      {/* Header — hidden when controlled by external mode bar */}
      {!hasExternal && (
      <div className="flex items-center justify-between mb-1 pt-6">
        <div>
          <h1 className="text-[24px] font-bold" style={{ color: '#0f172a' }}>Labs</h1>
          <div className="text-[13px]" style={{ color: '#94a3b8' }}>
            {mode === 'global' ? 'Global diagnostics' : mode === 'universe' ? 'Universe analysis' : symbol.replace('USDT', '') + ' diagnostics'}
            {data?.latencyMs ? ` · ${data.latencyMs}ms` : ''}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Mode buttons */}
          <button data-testid="labs-mode-global" onClick={() => setMode('global')}
            className="flex items-center gap-1 px-3 py-1.5 text-[12px] font-semibold transition-all duration-200"
            style={{ color: mode === 'global' ? '#0f172a' : '#94a3b8' }}>
            <Globe className="w-3.5 h-3.5" /> Global
          </button>
          <button data-testid="labs-mode-universe" onClick={() => setMode('universe')}
            className="flex items-center gap-1 px-3 py-1.5 text-[12px] font-semibold transition-all duration-200"
            style={{ color: mode === 'universe' ? '#0f172a' : '#94a3b8' }}>
            <BarChart3 className="w-3.5 h-3.5" /> Universe
          </button>

          {/* Asset search */}
          <div className="relative" ref={searchRef}>
            <button data-testid="labs-search-btn" onClick={() => setSearchOpen(!searchOpen)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold transition-all duration-200"
              style={{ color: mode === 'asset' ? '#0f172a' : '#94a3b8' }}>
              <Search className="w-3.5 h-3.5" />
              {mode === 'asset' ? symbol.replace('USDT', '') : 'Asset'}
            </button>
            {searchOpen && (
              <div className="absolute right-0 top-10 z-50 w-72 rounded-xl overflow-hidden"
                style={{ background: '#ffffff', boxShadow: '0 16px 48px rgba(0,0,0,0.12)' }}>
                <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
                  <Search className="w-4 h-4 flex-shrink-0" style={{ color: '#94a3b8' }} />
                  <input data-testid="labs-search-input" autoFocus value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Search asset..." className="flex-1 text-[14px] outline-none bg-transparent font-medium"
                    style={{ color: '#0f172a', caretColor: '#6366f1' }} />
                  {searchQuery && <button onClick={() => setSearchQuery('')}><X className="w-3.5 h-3.5" style={{ color: '#94a3b8' }} /></button>}
                </div>
                <div className="max-h-64 overflow-y-auto py-1" style={{ scrollbarWidth: 'thin' }}>
                  {filteredSymbols.length === 0 && <div className="px-4 py-3 text-[13px]" style={{ color: '#94a3b8' }}>No results</div>}
                  {filteredSymbols.map(s => (
                    <button key={s} data-testid={`labs-sym-${s}`} onClick={() => selectSymbol(s)}
                      className="w-full text-left px-4 py-2 text-[13px] font-semibold hover:bg-slate-50 transition-colors"
                      style={{ color: '#0f172a' }}>
                      {s.replace('USDT', '')}
                    </button>
                  ))}
                </div>
                <div className="px-4 py-2 text-[10px] uppercase tracking-wide" style={{ color: '#94a3b8', borderTop: '1px solid rgba(15,23,42,0.06)' }}>
                  {symbols.length} assets
                </div>
              </div>
            )}
          </div>

          <button data-testid="labs-refresh" onClick={fetchLabs}
            className="p-1.5 transition-opacity hover:opacity-60" disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#94a3b8' }} /> : <RefreshCw className="w-4 h-4" style={{ color: '#94a3b8' }} />}
          </button>
        </div>
      </div>
      )}

      {loading && !data && <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin" style={{ color: '#94a3b8' }} /></div>}

      {data?.ok && mode !== 'universe' && (
        <>
          {/* Integrity */}
          {data.integrity && (
            <div data-testid="labs-integrity" className="flex items-center gap-3 mb-4 mt-4">
              <span className="text-[12px] font-bold" style={{ color: data.integrity.status === 'HEALTHY' ? '#16a34a' : data.integrity.status === 'DEGRADED' ? '#d97706' : '#dc2626' }}>
                {data.integrity.status === 'HEALTHY' ? 'All systems normal' : data.integrity.status === 'DEGRADED' ? 'Limited data coverage' : 'Data severely compromised'}
              </span>
              <span className="text-[12px]" style={{ color: '#64748b' }}>
                Coverage {data.integrity.coveragePct}% · Fresh {data.integrity.freshnessSec}s · {data.integrity.sourceType}
              </span>
            </div>
          )}

          {/* Overall State */}
          {data.overallState && (
            <div data-testid="labs-overall-state" className="mb-6 mt-2">
              <div className="text-[28px] font-bold" style={{ color: OVERALL_STATE_COLORS[data.overallState.stateKey] || '#94a3b8' }}>
                {data.overallState.stateLabel}
              </div>
              <div className="text-[13px] mt-1" style={{ color: '#64748b' }}>{data.explain?.oneLiner}</div>
              {data.explain?.bullets?.length > 0 && (
                <div className="mt-2 space-y-0.5">
                  {data.explain.bullets.map((b, i) => (
                    <div key={i} className="text-[12px]" style={{ color: '#64748b' }}>· {b}</div>
                  ))}
                </div>
              )}
              {data.explain?.invalidation && (
                <div className="text-[11px] mt-2 italic" style={{ color: '#94a3b8' }}>{data.explain.invalidation}</div>
              )}
            </div>
          )}

          {/* Active Risks */}
          {data.activeRisks?.length > 0 && (
            <div data-testid="labs-active-risks" className="mb-6">
              <div className="text-[11px] uppercase tracking-wider font-semibold mb-2" style={{ color: '#dc2626' }}>
                Active Risks ({data.activeRisks.length})
              </div>
              <div className="flex gap-2 flex-wrap">
                {data.activeRisks.map((r, i) => (
                  <span key={i} className="text-[11px] font-bold" style={{ color: '#dc2626' }}>· {r}</span>
                ))}
              </div>
            </div>
          )}

          {/* Lab Groups */}
          {data.groups?.map(group => {
            const Icon = GROUP_ICONS[group.name] || Activity;
            return (
              <div key={group.name} className="mb-8" data-testid={`labs-group-${group.name}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="w-4 h-4" style={{ color: '#94a3b8' }} />
                  <span className="text-[11px] uppercase tracking-wider font-bold" style={{ color: '#94a3b8' }}>{group.name}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
                  {group.labs.map(lab => (
                    <LabCard key={lab.lab} lab={lab} onDrilldown={openDrilldown} />
                  ))}
                </div>
              </div>
            );
          })}

          {/* Navigation */}
          <div className="flex gap-6 mt-8 pt-6" style={{ borderTop: '1px solid rgba(15,23,42,0.06)' }}>
            <button data-testid="labs-link-research" onClick={() => setSearchParams({ tab: 'research' })}
              className="flex items-center gap-2 text-[14px] font-bold transition-opacity duration-200 hover:opacity-60"
              style={{ color: '#6366f1' }}>
              Research <ArrowRight className="w-4 h-4" />
            </button>
            <button data-testid="labs-link-radar" onClick={() => setSearchParams({ tab: 'alt-radar' })}
              className="flex items-center gap-2 text-[14px] font-bold transition-opacity duration-200 hover:opacity-60"
              style={{ color: '#0f172a' }}>
              Radar <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </>
      )}

      {/* Universe mode */}
      {data?.ok && mode === 'universe' && <UniverseView data={data.universe} />}

      {/* Drilldown Drawer */}
      <DrilldownDrawer data={drilldown} onClose={() => setDrilldown(null)} />
    </div>
  );
}
