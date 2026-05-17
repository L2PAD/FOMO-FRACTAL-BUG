/**
 * R1.3 — Research V3 Page (Macro Interpretation Engine)
 * Clean design: no borders, no boxes, no shadows on badges.
 * Rich dark tooltips for every section.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Loader2, ArrowRight, Search, Globe, BarChart3, X } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL;

// ═══════════════════════════════════════
// COLORS
// ═══════════════════════════════════════

const STATE_COLORS = {
  // Regime: trend=green, range=neutral, transition/chaotic=bad
  RANGE: '#64748b', INSIDE_RANGE: '#64748b', TRENDING_UP: '#16a34a', TRENDING_DOWN: '#dc2626',
  TRANSITION: '#d97706', CHAOTIC: '#dc2626',
  // Volatility: low=neutral, normal=neutral, high=bad, expansion=warning
  LOW_VOL: '#64748b', HIGH_VOL: '#dc2626', NORMAL_VOL: '#64748b', EXPANSION: '#d97706', CONTRACTION: '#6366f1',
  // Liquidity: thin=bad, normal=neutral, deep=good
  THIN_LIQUIDITY: '#dc2626', DEEP_LIQUIDITY: '#16a34a', NORMAL_LIQUIDITY: '#64748b',
  // Flow: buy=green, sell=red, balanced=neutral
  BUY_DOMINANT: '#16a34a', SELL_DOMINANT: '#dc2626', BALANCED: '#64748b',
  // Stress: stable=good, stressed/panic=bad, normal=neutral
  STRESSED: '#dc2626', PANIC: '#dc2626', STABLE: '#16a34a', NORMAL: '#64748b',
};
const STATE_LABELS = {
  RANGE: 'Ranging', INSIDE_RANGE: 'In Range', TRENDING_UP: 'Uptrend', TRENDING_DOWN: 'Downtrend',
  TRANSITION: 'Transition', CHAOTIC: 'Chaotic',
  LOW_VOL: 'Low', HIGH_VOL: 'High', NORMAL_VOL: 'Normal', EXPANSION: 'Expansion', CONTRACTION: 'Contraction',
  THIN_LIQUIDITY: 'Thin', DEEP_LIQUIDITY: 'Deep', NORMAL_LIQUIDITY: 'Normal',
  BUY_DOMINANT: 'Buyers', SELL_DOMINANT: 'Sellers', BALANCED: 'Balanced',
  STRESSED: 'Stressed', PANIC: 'Panic', STABLE: 'Stable', NORMAL: 'Normal',
};
const RISK_COLORS = { HIGH: '#dc2626', MID: '#d97706', LOW: '#16a34a' };
const VERDICT_COLORS = { buy: '#16a34a', sell: '#dc2626', watch: '#d97706', neutral: '#64748b' };
const HORIZON_NAMES = { short: 'Short (0-2d)', mid: 'Mid (3-7d)', swing: 'Swing (1-4w)' };
const INTEGRITY_COLORS = { HEALTHY: '#16a34a', DEGRADED: '#d97706', CRITICAL: '#dc2626' };

// Semantic color for horizon bias text
function biasColor(bias) {
  if (!bias) return '#64748b';
  const b = bias.toLowerCase();
  if (b.includes('momentum') || b.includes('trend follow') || b.includes('continuation')) return '#16a34a';
  if (b.includes('fade') || b.includes('defensive') || b.includes('avoid') || b.includes('reduce')) return '#dc2626';
  if (b.includes('regime shift') || b.includes('wait')) return '#d97706';
  return '#64748b';
}
function sl(s) { return STATE_LABELS[s] || s?.replace(/_/g, ' ') || '\u2014'; }
function sc(s) { return STATE_COLORS[s] || '#64748b'; }

// ═══════════════════════════════════════
// TOOLTIP DESCRIPTIONS
// ═══════════════════════════════════════

const DOMAIN_TOOLTIPS = {
  regime: {
    title: 'Market Regime',
    desc: 'Current price structure type.',
    details: [
      { label: 'Ranging', text: 'Price moves sideways in a channel. Fade breakouts.', color: '#94a3b8' },
      { label: 'Uptrend', text: 'Higher highs/lows. Follow momentum.', color: '#16a34a' },
      { label: 'Downtrend', text: 'Lower highs/lows. Short bias or reduce longs.', color: '#dc2626' },
      { label: 'Transition', text: 'Regime changing. Wait for confirmation.', color: '#d97706' },
      { label: 'Chaotic', text: 'No clear structure. Reduce exposure.', color: '#dc2626' },
    ],
  },
  volatility: {
    title: 'Volatility',
    desc: 'Amplitude of price movements.',
    details: [
      { label: 'Low', text: 'Compressed range. Breakout building.', color: '#94a3b8' },
      { label: 'Normal', text: 'Standard conditions. Normal sizing.', color: '#94a3b8' },
      { label: 'High', text: 'Wide swings. Reduce size, widen stops.', color: '#dc2626' },
      { label: 'Expansion', text: 'Volatility expanding. Trend acceleration likely.', color: '#d97706' },
    ],
  },
  liquidity: {
    title: 'Liquidity',
    desc: 'Order book depth and execution quality.',
    details: [
      { label: 'Thin', text: 'Low depth. High slippage risk. Use limit orders.', color: '#dc2626' },
      { label: 'Normal', text: 'Adequate depth. Standard execution.', color: '#94a3b8' },
      { label: 'Deep', text: 'Rich order books. Stable fills.', color: '#16a34a' },
    ],
  },
  flow: {
    title: 'Order Flow',
    desc: 'Who is driving the market right now.',
    details: [
      { label: 'Buyers', text: 'Net buying pressure. Aggressive bids.', color: '#16a34a' },
      { label: 'Sellers', text: 'Net selling pressure. Asks dominate.', color: '#dc2626' },
      { label: 'Balanced', text: 'No clear direction in flow.', color: '#94a3b8' },
    ],
  },
  stress: {
    title: 'Market Stress',
    desc: 'Overall market pressure and stability.',
    details: [
      { label: 'Stable', text: 'Calm conditions. Normal operations.', color: '#16a34a' },
      { label: 'Stressed', text: 'Elevated tension. Potential dislocations.', color: '#dc2626' },
      { label: 'Panic', text: 'Extreme fear. Liquidation cascades possible.', color: '#dc2626' },
    ],
  },
};

const RISK_TOOLTIP = {
  title: 'Risk Pressure',
  desc: 'Aggregated risk score from liquidity, manipulation, data quality, and divergence.',
  details: [
    { label: 'LOW (0-35%)', text: 'Normal conditions. Standard parameters.', color: '#16a34a' },
    { label: 'MID (35-65%)', text: 'Elevated risk. Monitor closely, consider reducing size.', color: '#d97706' },
    { label: 'HIGH (65-100%)', text: 'Critical. Reduce exposure, avoid leverage, tighten stops.', color: '#dc2626' },
  ],
};

const HORIZON_TOOLTIP = {
  title: 'Horizon Bias',
  desc: 'Optimal trading approach for each timeframe based on regime, momentum, and market structure.',
  details: [
    { label: 'Short (0-2d)', text: 'Intraday to overnight. Sensitive to flow and volatility.', color: '#e2e8f0' },
    { label: 'Mid (3-7d)', text: 'Swing trades. Sensitive to regime and trend.', color: '#e2e8f0' },
    { label: 'Swing (1-4w)', text: 'Position trades. Sensitive to regime shifts and macro.', color: '#e2e8f0' },
  ],
};

const FORCES_TOOLTIP = {
  title: 'Dominant Forces',
  desc: 'Top market drivers ranked by impact. Abnormal states (stress, thin liquidity, manipulation) score higher.',
};

const EXECUTION_TOOLTIP = {
  title: 'Trading Environment',
  desc: 'Actionable context for position management based on current market conditions.',
  details: [
    { label: 'Style', text: 'Recommended trading approach.', color: '#e2e8f0' },
    { label: 'Avoid', text: 'Specific risks to stay away from.', color: '#e2e8f0' },
    { label: 'Instruments', text: 'Spot vs Futures preference.', color: '#e2e8f0' },
    { label: 'Risk Controls', text: 'Position sizing and stop adjustments.', color: '#e2e8f0' },
  ],
};

// ═══════════════════════════════════════
// RICH TOOLTIP COMPONENT
// ═══════════════════════════════════════

function RichTooltip({ tooltip, children, position = 'bottom' }) {
  const [show, setShow] = useState(false);
  const ref = useRef(null);

  if (!tooltip) return children;
  const isUp = position === 'top';

  return (
    <div className="relative inline-flex" ref={ref}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div className="absolute z-50 left-0 w-80 p-4 rounded-xl pointer-events-none"
          style={{
            ...(isUp ? { bottom: '100%', marginBottom: '8px' } : { top: '100%', marginTop: '8px' }),
            background: '#0f172a', color: '#e2e8f0',
            boxShadow: '0 12px 40px rgba(0,0,0,0.3)',
            animation: 'fadeIn 0.15s ease-out',
          }}>
          <div className="text-[14px] font-bold text-white mb-1">{tooltip.title}</div>
          <div className="text-[12px] mb-3" style={{ color: '#94a3b8' }}>{tooltip.desc}</div>
          {tooltip.details?.map((d, i) => (
            <div key={i} className="mb-2 last:mb-0">
              <span className="text-[12px] font-semibold" style={{ color: d.color || '#e2e8f0' }}>{d.label}</span>
              <span className="text-[11px] ml-1.5" style={{ color: '#94a3b8' }}>{'\u2014'} {d.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// SECTION HEADER
// ═══════════════════════════════════════

function SectionHead({ title, tooltip, description, tooltipPosition = 'bottom' }) {
  return (
    <div className="mb-4">
      <RichTooltip tooltip={tooltip} position={tooltipPosition}>
        <div className="text-[13px] font-semibold uppercase" style={{ color: '#94a3b8', letterSpacing: '1px' }}>{title}</div>
      </RichTooltip>
      {description && <div className="text-[11px] mt-0.5" style={{ color: '#b0b8c4' }}>{description}</div>}
    </div>
  );
}

// ═══════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════

export default function ExchangeResearchPage({ externalMode, externalSymbol }) {
  const [_mode, _setMode] = useState('global');
  const [_symbol, _setSymbol] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [symbols, setSymbols] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [, setSearchParams] = useSearchParams();
  const searchRef = useRef(null);

  // Use external mode/symbol if provided
  const hasExternal = externalMode !== undefined;
  const mode = hasExternal ? externalMode : _mode;
  const symbol = hasExternal ? (externalSymbol || '') : _symbol;

  useEffect(() => {
    if (!searchOpen) return;
    const handler = (e) => { if (searchRef.current && !searchRef.current.contains(e.target)) { setSearchOpen(false); setSearchQuery(''); } };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [searchOpen]);

  useEffect(() => {
    fetch(`${API}/api/v11/exchange/research/symbols`)
      .then(r => r.json()).then(d => { if (d.ok) setSymbols(d.symbols); }).catch(() => {});
  }, []);

  const load = useCallback(async (spin = false) => {
    if (spin) setRefreshing(true);
    try {
      let url;
      if (mode === 'global') url = `${API}/api/v11/exchange/research/global`;
      else if (mode === 'universe') url = `${API}/api/v11/exchange/research/universe`;
      else url = `${API}/api/v11/exchange/research/asset/${symbol}`;
      const res = await fetch(url);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch (e) { console.error('Research fetch:', e); }
    finally { setLoading(false); setRefreshing(false); }
  }, [mode, symbol]);

  useEffect(() => { setLoading(true); load(true); }, [load]);
  useEffect(() => { const iv = setInterval(() => load(false), 60000); return () => clearInterval(iv); }, [load]);

  const selectSymbol = (sym) => { _setSymbol(sym); _setMode('asset'); setSearchOpen(false); setSearchQuery(''); };
  const filteredSymbols = searchQuery
    ? symbols.filter(s => s.replace('USDT', '').toLowerCase().includes(searchQuery.toLowerCase())).slice(0, 20)
    : symbols.slice(0, 20);

  if (loading && !data) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} /></div>;
  }

  return (
    <div data-testid="research-page" className="max-w-[1200px] mx-auto px-6 py-6">
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }`}</style>

      {/* Header — hidden when controlled externally */}
      {!hasExternal && (
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-[22px] font-bold tracking-tight" style={{ color: '#0f172a' }}>Research</h2>
          <p className="text-[13px] mt-0.5" style={{ color: '#94a3b8' }}>
            {mode === 'global' ? 'Global market context' : mode === 'universe' ? 'Universe insight' : `Asset: ${symbol.replace('USDT', '')}`}
            {' '}&middot; {data?.latencyMs || 0}ms
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {[
              { id: 'global', icon: Globe, label: 'Global' },
              { id: 'universe', icon: BarChart3, label: 'Universe' },
            ].map(m => (
              <button key={m.id} data-testid={`research-mode-${m.id}`}
                onClick={() => { _setMode(m.id); _setSymbol(''); }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold transition-colors"
                style={{ color: mode === m.id ? '#0f172a' : '#94a3b8' }}>
                <m.icon className="w-3.5 h-3.5" /> {m.label}
              </button>
            ))}
          </div>
          <div className="relative" ref={searchRef}>
            <button data-testid="research-search-btn" onClick={() => setSearchOpen(!searchOpen)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold transition-all duration-200"
              style={{ color: mode === 'asset' ? '#0f172a' : '#94a3b8' }}>
              <Search className="w-3.5 h-3.5" />
              {mode === 'asset' ? symbol.replace('USDT', '') : 'Asset'}
            </button>
            {searchOpen && (
              <div className="absolute right-0 top-10 z-50 w-72 rounded-xl overflow-hidden"
                style={{
                  background: '#ffffff',
                  boxShadow: '0 16px 48px rgba(0,0,0,0.12)',
                  animation: 'fadeIn 0.15s ease-out',
                }}>
                <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
                  <Search className="w-4 h-4 flex-shrink-0" style={{ color: '#94a3b8' }} />
                  <input data-testid="research-search-input" autoFocus value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Search asset..."
                    className="flex-1 text-[14px] outline-none bg-transparent font-medium"
                    style={{ color: '#0f172a', caretColor: '#6366f1' }} />
                  {searchQuery && (
                    <button onClick={() => setSearchQuery('')} className="transition-opacity hover:opacity-70">
                      <X className="w-3.5 h-3.5" style={{ color: '#94a3b8' }} />
                    </button>
                  )}
                </div>
                <div className="max-h-64 overflow-y-auto py-1" style={{ scrollbarWidth: 'thin' }}>
                  {filteredSymbols.length === 0 && (
                    <div className="px-4 py-3 text-[13px]" style={{ color: '#94a3b8' }}>No results</div>
                  )}
                  {filteredSymbols.map((s, idx) => (
                    <button key={s} data-testid={`research-sym-${s}`} onClick={() => selectSymbol(s)}
                      className="w-full text-left px-4 py-2 text-[13px] font-semibold transition-all duration-100 hover:bg-slate-50"
                      style={{
                        color: '#0f172a',
                        animationDelay: `${idx * 20}ms`,
                        animation: 'fadeIn 0.15s ease-out both',
                      }}>
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
          <button onClick={() => load(true)} disabled={refreshing} data-testid="research-refresh"
            className="p-2 transition-colors" style={{ color: '#94a3b8' }}>
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
      )}

      {data?.integrity && <IntegrityBar integrity={data.integrity} />}
      {mode === 'asset' && data?.assetOverlay && <AssetOverlayCard overlay={data.assetOverlay} />}
      {mode === 'asset' && !data?.assetOverlay && (
        <div className="mb-6 text-[13px]" style={{ color: '#b45309' }}>No radar data for {symbol}. Showing market-level context.</div>
      )}

      <MarketStateCard state={data?.marketState} />
      {mode === 'universe' && data?.universeInsight && <UniverseInsightCard insight={data.universeInsight} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-10">
        <RiskPressureCard risk={data?.riskPressure} />
        <HorizonBiasCard horizons={data?.horizonBias} />
      </div>

      <div className="mt-10"><DominantForcesCard forces={data?.dominantForces} data={data} /></div>
      <div className="mt-10"><ExecutionCard exec={data?.executionImplications} setSearchParams={setSearchParams} /></div>
    </div>
  );
}

// ═══════════════════════════════════════
// INTEGRITY BAR
// ═══════════════════════════════════════

function IntegrityBar({ integrity }) {
  const color = INTEGRITY_COLORS[integrity.status] || '#64748b';
  const statusLabels = { HEALTHY: 'All systems normal', DEGRADED: 'Limited data coverage', CRITICAL: 'Data severely compromised' };
  return (
    <div data-testid="integrity-bar" className="mb-6 flex items-center gap-3">
      <span className="text-[12px] font-bold" style={{ color }}>{statusLabels[integrity.status] || integrity.status}</span>
      <span className="text-[12px]" style={{ color: '#64748b' }}>{integrity.reasons?.join(' / ')}</span>
      <span className="text-[12px] tabular-nums ml-auto font-semibold" style={{ color: '#0f172a' }}>Coverage: {integrity.coveragePct}%</span>
    </div>
  );
}

// ═══════════════════════════════════════
// ASSET OVERLAY
// ═══════════════════════════════════════

function AssetOverlayCard({ overlay }) {
  const vc = VERDICT_COLORS[overlay.verdict] || '#64748b';
  return (
    <div data-testid="asset-overlay" className="mb-8 pb-6" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
      <div className="text-[13px] font-semibold uppercase mb-3" style={{ color: '#94a3b8', letterSpacing: '1px' }}>Radar Signal</div>
      <div className="flex items-center gap-8 flex-wrap">
        <span className="text-[15px] font-bold uppercase" style={{ color: vc }}>
          {overlay.verdict} {overlay.direction === 'long' ? '\u2191' : overlay.direction === 'short' ? '\u2193' : ''}
        </span>
        <Stat label="Conv" value={overlay.conviction} color={vc} />
        <Stat label="Tier" value={overlay.convictionTier || '\u2014'} />
        <Stat label="Horizon" value={overlay.horizon} color="#64748b" />
        <Stat label="Setup" value={overlay.setupScore?.toFixed(2)} color="#64748b" />
        {overlay.divergence?.score > 0 && <Stat label="Div" value={overlay.divergence.label} color="#6366f1" />}
      </div>
      {overlay.radarOneLiner && <div className="mt-3 text-[12px]" style={{ color: '#94a3b8' }}>{overlay.radarOneLiner}</div>}
    </div>
  );
}

function Stat({ label, value, color = '#0f172a' }) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase" style={{ color: '#b0b8c4' }}>{label}</div>
      <div className="text-[16px] font-bold tabular-nums" style={{ color }}>{value}</div>
    </div>
  );
}

// ═══════════════════════════════════════
// UNIVERSE INSIGHT
// ═══════════════════════════════════════

function UniverseInsightCard({ insight }) {
  if (!insight?.totalSymbols) return null;
  return (
    <div data-testid="universe-insight" className="mb-8 pb-6" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
      <SectionHead title="Universe Insight" description={`${insight.totalSymbols} symbols analyzed across the alpha universe.`}
        tooltip={{ title: 'Universe Insight', desc: 'Cross-universe analysis showing dominant patterns, signal distributions, and structural tendencies across all tracked symbols.' }} />
      {insight.dominance?.length > 0 && (
        <div className="space-y-2.5 mb-4">
          {insight.dominance.map((d, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="w-12 text-right text-[14px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{d.pct}%</div>
              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.04)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, d.pct)}%`, background: '#6366f1', opacity: 0.35 }} />
              </div>
              <div className="text-[12px]" style={{ color: '#64748b' }}>{d.label}</div>
            </div>
          ))}
        </div>
      )}
      {insight.stats && (
        <div className="flex gap-8 mt-3">
          {[
            { label: 'BUY', value: `${insight.stats.buyPct}%`, color: '#16a34a' },
            { label: 'SELL', value: `${insight.stats.sellPct}%`, color: '#dc2626' },
            { label: 'WATCH', value: `${insight.stats.watchPct}%`, color: '#d97706' },
            { label: 'Compression', value: `${insight.stats.compressionPct}%`, color: '#6366f1' },
            { label: 'High Conv', value: `${insight.stats.highConvictionPct}%`, color: '#0f172a' },
          ].map((s, i) => <Stat key={i} label={s.label} value={s.value} color={s.color} />)}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// MARKET STATE
// ═══════════════════════════════════════

function MarketStateCard({ state }) {
  if (!state) return null;
  const domains = [
    { key: 'regime', label: 'Regime' }, { key: 'volatility', label: 'Volatility' },
    { key: 'liquidity', label: 'Liquidity' }, { key: 'flow', label: 'Flow' },
    { key: 'stress', label: 'Stress' },
  ];
  return (
    <div data-testid="market-state-card">
      <SectionHead title="Market State"
        description="Current structural environment across 5 key domains."
        tooltip={{ title: 'Market State', desc: 'Five independent assessments of current market conditions. Each domain is scored by confidence (0-100%). Together they define the trading environment.' }} />
      <div className="flex gap-8 flex-wrap">
        {domains.map(d => {
          const v = state[d.key] || {};
          const tt = DOMAIN_TOOLTIPS[d.key];
          return (
            <RichTooltip key={d.key} tooltip={tt}>
              <div className="min-w-[120px]">
                <div className="text-[11px] uppercase" style={{ color: '#b0b8c4', letterSpacing: '0.5px' }}>{d.label}</div>
                <div className="text-[20px] font-bold mt-0.5" style={{ color: sc(v.state) }}>{sl(v.state)}</div>
                <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${(v.confidence || 0) * 100}%`, background: sc(v.state) }} />
                </div>
                <div className="text-[11px] mt-0.5 tabular-nums font-semibold" style={{ color: '#0f172a' }}>{((v.confidence || 0) * 100).toFixed(0)}%</div>
              </div>
            </RichTooltip>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// RISK PRESSURE
// ═══════════════════════════════════════

function RiskPressureCard({ risk }) {
  if (!risk) return null;
  const color = RISK_COLORS[risk.level] || '#64748b';
  return (
    <div data-testid="risk-pressure-card">
      <SectionHead title="Risk Pressure"
        description="Aggregated risk from liquidity, manipulation, data quality, and cross-venue divergence."
        tooltip={RISK_TOOLTIP} />
      <div className="flex items-center gap-4 mb-3">
        <span className="text-[32px] font-bold tabular-nums" style={{ color }}>{(risk.score * 100).toFixed(0)}%</span>
        <span className="text-[13px] font-bold uppercase" style={{ color }}>{risk.level}</span>
      </div>
      {risk.drivers?.length > 0 && (
        <div className="space-y-1">
          {risk.drivers.map((d, i) => (
            <div key={i} className="text-[13px]" style={{ color: '#64748b' }}>{'\u00b7'} {d}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// HORIZON BIAS
// ═══════════════════════════════════════

function HorizonBiasCard({ horizons }) {
  if (!horizons) return null;
  return (
    <div data-testid="horizon-bias-card">
      <SectionHead title="Horizon Bias"
        description="Optimal trading approach for each timeframe."
        tooltip={HORIZON_TOOLTIP} />
      <div className="space-y-4">
        {['short', 'mid', 'swing'].map(h => {
          const v = horizons[h] || {};
          return (
            <div key={h} className="flex items-center justify-between">
              <div>
                <span className="text-[12px] font-semibold" style={{ color: '#94a3b8' }}>{HORIZON_NAMES[h]}</span>
                <span className="text-[15px] font-bold ml-3" style={{ color: biasColor(v.bias) }}>{v.bias}</span>
              </div>
              <span className="text-[12px] tabular-nums font-semibold" style={{ color: '#0f172a' }}>{((v.confidence || 0) * 100).toFixed(0)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// DOMINANT FORCES
// ═══════════════════════════════════════

function DominantForcesCard({ forces, data }) {
  if (!forces?.length) return null;
  const totalRisk = data?.totalRisk;
  return (
    <div data-testid="dominant-forces-card">
      <SectionHead title="Dominant Forces"
        description="Top market drivers ranked by impact. Abnormal conditions score higher."
        tooltip={FORCES_TOOLTIP} tooltipPosition="top" />
      {totalRisk && (
        <div className="flex items-center gap-3 mb-4">
          <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: '#64748b' }}>Total Risk</span>
          <span className="text-[18px] font-bold" style={{ color: totalRisk.level === 'Low' ? '#16a34a' : totalRisk.level === 'Elevated' ? '#dc2626' : '#d97706' }}>
            {totalRisk.totalRiskIndex}
          </span>
          <span className="text-[13px] font-semibold" style={{ color: totalRisk.level === 'Low' ? '#16a34a' : totalRisk.level === 'Elevated' ? '#dc2626' : '#d97706' }}>
            / 100 — {totalRisk.level}
          </span>
        </div>
      )}
      <div className="space-y-4">
        {forces.map((f, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-[14px] font-bold" style={{ color: '#0f172a' }}>{f.name}</span>
                <span className="text-[13px] font-semibold" style={{ color: sc(f.state) }}>{sl(f.state)}</span>
              </div>
              <p className="text-[12px] mt-0.5" style={{ color: '#94a3b8' }}>{f.explanation}</p>
            </div>
            <div className="w-20">
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.04)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, f.impactScore * 70)}%`, background: sc(f.state) }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// EXECUTION IMPLICATIONS
// ═══════════════════════════════════════

function ExecutionCard({ exec, setSearchParams }) {
  if (!exec) return null;
  return (
    <div data-testid="execution-card" className="pb-8 pt-8" style={{ borderTop: '1px solid rgba(15,23,42,0.06)' }}>
      <SectionHead title="Trading Environment"
        description="What the current market conditions mean for your trading."
        tooltip={EXECUTION_TOOLTIP} tooltipPosition="top" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div>
          <div className="text-[11px] uppercase mb-1 font-semibold tracking-wide" style={{ color: '#64748b' }}>Style</div>
          <div className="text-[14px] font-bold" style={{ color: '#0f172a' }}>{exec.style}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase mb-1 font-semibold tracking-wide" style={{ color: '#64748b' }}>Avoid</div>
          {exec.avoid?.length > 0 ? exec.avoid.map((a, i) => (
            <div key={i} className="text-[13px] font-medium" style={{ color: '#dc2626' }}>{a}</div>
          )) : <div className="text-[13px]" style={{ color: '#16a34a' }}>No restrictions</div>}
        </div>
        <div>
          <div className="text-[11px] uppercase mb-1 font-semibold tracking-wide" style={{ color: '#64748b' }}>Instruments</div>
          {exec.preferredInstruments?.map((p, i) => <div key={i} className="text-[13px] font-medium" style={{ color: '#0f172a' }}>{p}</div>)}
        </div>
        <div>
          <div className="text-[11px] uppercase mb-1 font-semibold tracking-wide" style={{ color: '#64748b' }}>Risk Controls</div>
          {exec.riskControls?.map((r, i) => <div key={i} className="text-[13px]" style={{ color: '#0f172a' }}>{r}</div>)}
        </div>
      </div>
      <div className="flex gap-6 mt-8">
        <button data-testid="research-link-market" onClick={() => setSearchParams({ tab: 'market-board' })}
          className="flex items-center gap-2 text-[14px] font-bold transition-opacity duration-200"
          style={{ color: '#6366f1' }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '0.7'; }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}>
          Market Board <ArrowRight className="w-4 h-4" />
        </button>
        <button data-testid="research-link-radar" onClick={() => setSearchParams({ tab: 'alt-radar' })}
          className="flex items-center gap-2 text-[14px] font-bold transition-opacity duration-200"
          style={{ color: '#0f172a' }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '0.6'; }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}>
          Radar <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
