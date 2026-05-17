/**
 * Core Engine V2.2 — Market Intelligence Core
 * 
 * Central search. TF selector (30m/1h/4h/1d/1w). 
 * Sigmoid bias (UP+DOWN=100). Specific blocked gate reasons.
 * 4 KPI cards + 2 column layout. Decision box with gate details.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { RefreshCw, Loader2, Search, X, AlertTriangle, Shield, ShieldAlert, Check, Ban, ArrowRight } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const TF_OPTIONS = [
  { value: '30m', label: '30m', tip: 'Fast/noisy — high shift, more false signals. Use for scalping context' },
  { value: '1h', label: '1H', tip: 'Baseline timeframe. Balanced noise/signal ratio' },
  { value: '4h', label: '4H', tip: 'Swing context. Smoother risk, fewer false transitions' },
  { value: '1d', label: '1D', tip: 'Structural view. Low noise, high-confidence regime & blocks' },
  { value: '1w', label: '1W', tip: 'Macro context. Maximum smoothing, long-term regime only' },
];

const RC = { breakout: '#16a34a', range: '#94a3b8', distribution: '#dc2626', trend: '#6366f1' };
const RKC = { low: '#16a34a', moderate: '#d97706', high: '#dc2626' };

function Tip({ text, children, block }) {
  const [show, setShow] = useState(false);
  if (!text) return children;
  const Tag = block ? 'div' : 'span';
  return (
    <Tag className={`relative ${block ? 'block' : 'inline-flex'}`} onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute z-50 left-0 top-full mt-1.5 w-64 px-3 py-2 rounded-lg pointer-events-none text-[12px]"
          style={{ background: '#0f172a', color: '#e2e8f0', boxShadow: '0 8px 24px rgba(0,0,0,0.25)' }}>
          {text}
        </span>
      )}
    </Tag>
  );
}

function SL({ children }) {
  return <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#94a3b8' }}>{children}</div>;
}

/* ═══════════ Macro Context Chip (compact, links to Capital Flow) ═══════════ */
const MACRO_RC = { FLIGHT_TO_BTC: '#6366f1', ALT_ROTATION: '#16a34a', CAPITAL_EXIT: '#dc2626', NEUTRAL: '#94a3b8' };
const SYNC_COLORS = { ALIGNED: '#16a34a', MIXED: '#d97706', CONFLICT: '#dc2626' };

function MacroContextChip({ macro, syncData }) {
  const [, setParams] = useSearchParams();
  const regime = macro.regime || 'NEUTRAL';
  const rc = MACRO_RC[regime] || '#94a3b8';
  const riskPct = Math.round((macro.riskOffProb || 0) * 100);

  const syncState = syncData?.state || '';
  const syncColor = SYNC_COLORS[syncState] || '#94a3b8';
  const alignPct = syncData?.alignmentScore || 0;

  const tipText = syncState === 'CONFLICT'
    ? `Core bias conflicts with macro regime. Reduce aggression. Alignment ${alignPct}%`
    : syncState === 'MIXED'
    ? `Mixed signals between Core and Macro. Use caution. Alignment ${alignPct}%`
    : `Core and Macro aligned. Signals reinforce each other. Alignment ${alignPct}%`;

  return (
    <Tip text={tipText}>
      <button data-testid="core-macro-context-chip" onClick={() => setParams({ tab: 'macro-v2' })}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all hover:opacity-80"
        style={{ background: `${rc}08`, border: `1px solid ${rc}25` }}>
        <span className="text-[11px] font-bold" style={{ color: rc }}>{(macro.regimeLabel || regime).replace(/_/g, ' ')}</span>
        <span className="text-[10px] font-semibold" style={{ color: '#94a3b8' }}>Risk-Off {riskPct}%</span>
        {syncState && (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ color: syncColor, background: `${syncColor}10` }}>
            {syncState === 'CONFLICT' ? 'CONFLICT' : syncState === 'MIXED' ? 'MIXED' : `Align ${alignPct}%`}
          </span>
        )}
        <ArrowRight className="w-3 h-3" style={{ color: '#94a3b8' }} />
      </button>
    </Tip>
  );
}

/* ═══════════ Header: Title + Badges + TF + Refresh ═══════════ */
function Header({ data, mode, symbol, loading, tf, setTf, onRefresh, resetGlobal, syncData }) {
  const integrity = data?.integrity || {};
  const macro = data?.macro || {};
  const meta = data?.meta || {};
  const intColor = ['healthy', 'ok'].includes(integrity.status) ? '#16a34a' : integrity.status === 'degraded' ? '#d97706' : '#dc2626';

  return (
    <div data-testid="core-header" className="flex items-center justify-between pt-4 pb-2">
      <div className="flex items-center gap-5">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: '#0f172a' }}>Core Engine</h1>
          <div className="text-[12px] flex items-center gap-1.5" style={{ color: '#94a3b8' }}>
            <span className="font-semibold" style={{ color: mode === 'asset' ? '#0f172a' : '#94a3b8' }}>
              {mode === 'asset' ? symbol?.replace('USDT', '') : 'Global'}
            </span>
            <span>·</span><span>{tf}</span>
            {meta.latencyMs != null && <><span>·</span><span>{meta.latencyMs}ms</span></>}
          </div>
        </div>
        <Tip text={`Penalty: ${integrity.penalty || 1}x. ${(integrity.warnings || []).join(', ') || 'Clean'}`}>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: intColor }} />
            <span className="text-[11px] font-semibold capitalize" style={{ color: intColor }}>{integrity.status || 'ok'}</span>
          </div>
        </Tip>
        {macro.available && (
          <MacroContextChip macro={macro} syncData={syncData} />
        )}
      </div>
      <div className="flex items-center gap-3">
        <div data-testid="core-tf-selector" className="flex items-center gap-0.5 rounded-lg p-0.5" style={{ background: 'rgba(15,23,42,0.03)' }}>
          {TF_OPTIONS.map(t => (
            <Tip key={t.value} text={t.tip}>
              <button data-testid={`core-tf-${t.value}`} onClick={() => setTf(t.value)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-all ${tf === t.value ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'}`}
                style={tf === t.value ? { background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' } : {}}>
                {t.label}
              </button>
            </Tip>
          ))}
        </div>
        {mode === 'asset' && (
          <button data-testid="core-reset-global" onClick={resetGlobal} className="text-[11px] font-bold px-2.5 py-1 rounded-md hover:bg-slate-50" style={{ color: '#64748b' }}>Global</button>
        )}
        <button data-testid="core-refresh" onClick={onRefresh} className="p-1.5 hover:opacity-60" disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#94a3b8' }} /> : <RefreshCw className="w-4 h-4" style={{ color: '#94a3b8' }} />}
        </button>
      </div>
    </div>
  );
}

/* ═══════════ Central Search Bar ═══════════ */
function SearchBar({ searchOpen, setSearchOpen, searchRef, searchQuery, setSearchQuery, searchResults, searchLoading, selectSymbol }) {
  return (
    <div data-testid="core-search-bar" className="mb-6" ref={searchRef}>
      <div className="relative">
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl cursor-text transition-all"
          style={{ background: 'rgba(15,23,42,0.03)' }}
          onClick={() => setSearchOpen(true)}>
          <Search className="w-4 h-4 flex-shrink-0" style={{ color: '#94a3b8' }} />
          {searchOpen ? (
            <input data-testid="core-search-input" autoFocus value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search asset... (e.g. SOL, ADA, ETH)"
              className="flex-1 text-[14px] outline-none bg-transparent font-medium" style={{ color: '#0f172a' }} />
          ) : (
            <span className="text-[14px] font-medium" style={{ color: '#94a3b8' }}>Search asset...</span>
          )}
          {searchQuery && (
            <button onClick={(e) => { e.stopPropagation(); setSearchQuery(''); }}>
              <X className="w-4 h-4" style={{ color: '#94a3b8' }} />
            </button>
          )}
        </div>

        {searchOpen && searchQuery && (
          <div className="absolute left-0 right-0 top-12 z-50 rounded-xl overflow-hidden"
            style={{ background: '#fff', boxShadow: '0 16px 48px rgba(0,0,0,0.12)' }}>
            <div className="max-h-80 overflow-y-auto py-1" style={{ scrollbarWidth: 'thin' }}>
              {searchLoading && <div className="px-4 py-4 flex justify-center"><Loader2 className="w-4 h-4 animate-spin" style={{ color: '#94a3b8' }} /></div>}
              {!searchLoading && searchResults.length === 0 && (
                <div className="px-4 py-3 text-[13px]" style={{ color: '#94a3b8' }}>No results</div>
              )}
              {searchResults.map(r => (
                <button key={r.symbol} onClick={() => selectSymbol(r.symbol)}
                  className="w-full text-left px-4 py-3 hover:bg-slate-50 flex items-center justify-between transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="text-[14px] font-bold" style={{ color: '#0f172a' }}>{r.short}</span>
                    <span className="text-[11px] font-bold capitalize px-1.5 py-0.5 rounded" style={{ color: RC[r.regime] || '#94a3b8', background: `${RC[r.regime] || '#94a3b8'}10` }}>{r.regime}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className="text-[12px] font-bold" style={{ color: RKC[r.riskLevel] || '#94a3b8' }}>Risk {r.risk}</span>
                    </div>
                    <span className="text-[11px] font-semibold capitalize w-16 text-right" style={{ color: r.bias?.includes('bullish') ? '#16a34a' : r.bias?.includes('bearish') ? '#dc2626' : '#94a3b8' }}>
                      {r.bias?.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[11px] font-semibold tabular-nums w-10 text-right" style={{ color: r.shift > 0.5 ? '#d97706' : '#64748b' }}>
                      {(r.shift * 100).toFixed(0)}%
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════ 4 KPI Cards (Regime, Risk, Bias, Shift) ═══════════ */
function KPIRow({ data }) {
  if (!data) return null;
  const { regime, risk, pressure, transition } = data;
  const shiftC = transition.shiftProbability > 0.5 ? '#d97706' : transition.shiftProbability > 0.3 ? '#0f172a' : '#16a34a';

  return (
    <div data-testid="core-kpi" className="flex gap-6 mb-8">
      <Tip text={`Confidence: ${regime.confidenceLevel}. Gap: ${(regime.dominanceGap * 100).toFixed(0)}%. Entropy: ${(regime.entropy * 100).toFixed(0)}%`}>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Regime</div>
          <div className="text-[24px] font-bold capitalize leading-tight" style={{ color: RC[regime.dominant] || '#64748b' }}>{regime.dominant}</div>
          <div className="text-[12px] font-semibold" style={{ color: '#64748b' }}>{(regime.confidence * 100).toFixed(0)}% <span className="capitalize">{regime.confidenceLevel}</span></div>
        </div>
      </Tip>
      <Tip text="Overall risk (0-100). Axes: liquidity, stress, manipulation, structure, conflict">
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Risk</div>
          <div className="text-[24px] font-bold tabular-nums" style={{ color: RKC[risk.level] || '#64748b' }}>{risk.totalIndex}</div>
          <div className="text-[12px] font-semibold capitalize" style={{ color: '#64748b' }}>{risk.level}</div>
        </div>
      </Tip>
      <Tip text={`Bias score: ${pressure.biasScore?.toFixed(2)}. Strength: ${(pressure.biasStrength * 100).toFixed(0)}%`}>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Bias</div>
          <div className="text-[24px] font-bold tabular-nums" style={{ color: pressure.netBias > 5 ? '#16a34a' : pressure.netBias < -5 ? '#dc2626' : '#94a3b8' }}>
            {pressure.upward}<span className="text-[16px] font-medium mx-1" style={{ color: '#94a3b8' }}>/</span>{pressure.downward}
          </div>
          <div className="text-[12px] font-semibold capitalize" style={{ color: '#64748b' }}>{pressure.biasLabel?.replace(/_/g, ' ')}</div>
        </div>
      </Tip>
      <Tip text={`shift = 0.45×instability + 0.35×risk + 0.20×trigger. Instability: ${(transition.instability * 100).toFixed(0)}%. Trigger: ${(transition.transitionTrigger * 100).toFixed(0)}%`}>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase font-semibold mb-1" style={{ color: '#94a3b8' }}>Shift</div>
          <div className="text-[24px] font-bold tabular-nums" style={{ color: shiftC }}>{(transition.shiftProbability * 100).toFixed(0)}%</div>
          <div className="text-[12px] font-semibold" style={{ color: '#64748b' }}>instab {(transition.instability * 100).toFixed(0)}%</div>
        </div>
      </Tip>
    </div>
  );
}

/* ═══════════ Compact Bars (reusable) ═══════════ */
function BarRow({ label, value, max = 100, color, bold }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`text-[12px] w-24 ${bold ? 'font-bold' : 'font-medium'}`} style={{ color: bold ? color : '#64748b' }}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.04)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(value / max) * 100}%`, background: color, opacity: bold ? 1 : 0.4 }} />
      </div>
      <span className="text-[12px] tabular-nums font-bold w-10 text-right" style={{ color: bold ? '#0f172a' : '#64748b' }}>{typeof value === 'number' && value <= 1 ? `${(value * 100).toFixed(0)}%` : value}</span>
    </div>
  );
}

/* ═══════════ Left Column: Transition + Regime + Pressure ═══════════ */
function LeftColumn({ data }) {
  const { regime, pressure, transition } = data;
  const sorted = Object.entries(regime.probabilities).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex-1">
      {/* Transition Map */}
      <div data-testid="core-transitions" className="mb-6">
        <SL>Transition Map</SL>
        <div className="space-y-2">
          {transition.transitions.map(t => (
            <div key={t.key} className="flex items-center gap-3">
              <span className="text-[12px] font-medium w-40" style={{ color: '#64748b' }}>
                <span className="capitalize" style={{ color: RC[t.from] || '#64748b' }}>{t.from}</span>
                <span className="mx-1.5" style={{ color: '#cbd5e1' }}>{'\u2192'}</span>
                <span className="capitalize">{t.to}</span>
              </span>
              <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.04)' }}>
                <div className="h-full rounded-full" style={{ width: `${t.probability * 100}%`, background: t.probability > 0.5 ? '#d97706' : '#94a3b8' }} />
              </div>
              <span className="text-[12px] tabular-nums font-bold w-10 text-right" style={{ color: '#0f172a' }}>{(t.probability * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Regime Distribution */}
      <div data-testid="core-regime-bars" className="mb-6">
        <SL>Regime Distribution</SL>
        <div className="space-y-2">
          {sorted.map(([key, prob]) => (
            <BarRow key={key} label={key.charAt(0).toUpperCase() + key.slice(1)} value={(prob * 100).toFixed(0)}
              color={RC[key] || '#94a3b8'} bold={key === regime.dominant} />
          ))}
        </div>
      </div>

      {/* Pressure */}
      <div data-testid="core-pressure" className="mb-6">
        <SL>Pressure</SL>
        <div className="flex gap-8">
          <div>
            <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Up</div>
            <div className="text-[22px] font-bold tabular-nums" style={{ color: '#16a34a' }}>{pressure.upward}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Down</div>
            <div className="text-[22px] font-bold tabular-nums" style={{ color: '#dc2626' }}>{pressure.downward}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Net</div>
            <div className="text-[16px] font-bold tabular-nums" style={{ color: pressure.netBias > 5 ? '#16a34a' : pressure.netBias < -5 ? '#dc2626' : '#94a3b8' }}>
              {pressure.netBias > 0 ? '+' : ''}{pressure.netBias}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ Right Column: Execution + Risk + Factors ═══════════ */
function RightColumn({ data }) {
  const { risk, factors, execution, transition } = data;
  const structRef = data.structuralRef;
  const execItems = [
    { key: 'aggressionMultiplier', label: 'Aggression' },
    { key: 'leverageMultiplier', label: 'Leverage' },
    { key: 'signalAmplification', label: 'Signal Amp' },
  ];

  return (
    <div className="flex-1">
      {/* Execution Controls + Decision */}
      <div data-testid="core-execution" className="mb-6">
        <SL>Execution Controls</SL>
        <div className="flex gap-6 items-end mb-3">
          {execItems.map(({ key, label }) => {
            const val = execution[key] || 0;
            const color = val > 0.7 ? '#16a34a' : val > 0.4 ? '#d97706' : '#dc2626';
            return (
              <div key={key}>
                <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>{label}</div>
                <div className="text-[22px] font-bold tabular-nums" style={{ color }}>{val.toFixed(2)}</div>
              </div>
            );
          })}
          {execution.strongActionsBlocked && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md" style={{ background: 'rgba(220,38,38,0.06)' }}>
              <AlertTriangle className="w-3.5 h-3.5" style={{ color: '#dc2626' }} />
              <span className="text-[11px] font-bold" style={{ color: '#dc2626' }}>BLOCKED</span>
            </div>
          )}
        </div>

        {/* Structural Reference (4h) — shown for 30m/1h */}
        {structRef && (
          <div data-testid="core-structural-ref" className="flex items-center gap-3 mb-3 px-3 py-2 rounded-lg"
            style={{ background: structRef.strongActionsBlocked ? 'rgba(220,38,38,0.04)' : 'rgba(22,163,74,0.04)' }}>
            <span className="text-[11px] font-bold uppercase" style={{ color: '#64748b' }}>{structRef.tf} ref</span>
            <span className="text-[11px] font-semibold capitalize" style={{ color: RC[structRef.regime] || '#64748b' }}>{structRef.regime}</span>
            <span className="text-[11px] font-semibold" style={{ color: RKC[structRef.riskLevel] || '#64748b' }}>Risk {structRef.risk}</span>
            <span className="text-[11px] font-semibold" style={{ color: structRef.shiftProbability > 0.5 ? '#d97706' : '#64748b' }}>
              Shift {(structRef.shiftProbability * 100).toFixed(0)}%
            </span>
            {structRef.strongActionsBlocked ? (
              <span className="flex items-center gap-1 text-[11px] font-bold" style={{ color: '#dc2626' }}>
                <AlertTriangle className="w-3 h-3" /> Blocked
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-bold" style={{ color: '#16a34a' }}>
                <Check className="w-3 h-3" /> Clear
              </span>
            )}
          </div>
        )}

        {/* Decision Box inline */}
        <div data-testid="core-decision" className="flex gap-6 mt-2">
          <div>
            {(execution.decision?.allowed || []).map((a, i) => (
              <div key={i} className="flex items-center gap-1.5 mb-0.5">
                <Check className="w-3 h-3 flex-shrink-0" style={{ color: '#16a34a' }} />
                <span className="text-[11px] font-medium" style={{ color: '#0f172a' }}>{a}</span>
              </div>
            ))}
          </div>
          <div>
            {(execution.decision?.blocked || []).map((b, i) => (
              <div key={i} className="flex items-center gap-1.5 mb-0.5">
                <Ban className="w-3 h-3 flex-shrink-0" style={{ color: '#dc2626' }} />
                <span className="text-[11px] font-medium" style={{ color: '#64748b' }}>{b}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Risk Breakdown */}
      <div data-testid="core-risk-bars" className="mb-6">
        <SL>Risk Breakdown</SL>
        <div className="space-y-2">
          {Object.entries(risk.breakdown).map(([key, val]) => (
            <BarRow key={key} label={key.charAt(0).toUpperCase() + key.slice(1)} value={val}
              color={val > 50 ? '#dc2626' : val > 30 ? '#d97706' : '#16a34a'} bold={val > 50} />
          ))}
        </div>
      </div>

      {/* Factors */}
      <div data-testid="core-factors" className="mb-6">
        <SL>Factors</SL>
        <div className="space-y-2">
          {[['structure','Structure'],['flow','Flow'],['liquidity','Liquidity'],['smartMoney','Smart Money'],['stability','Stability']].map(([key, label]) => {
            const val = factors[key] || 0;
            const color = val > 65 ? '#16a34a' : val > 40 ? '#d97706' : '#dc2626';
            return <BarRow key={key} label={label} value={val} color={color} bold={val > 65} />;
          })}
        </div>
      </div>
    </div>
  );
}

/* ═══════════ Relative Metrics (Asset vs Market) ═══════════ */
function RelativePanel({ relative }) {
  if (!relative) return null;
  const riskC = relative.riskVsMedian < -10 ? '#16a34a' : relative.riskVsMedian > 10 ? '#dc2626' : '#d97706';
  return (
    <div data-testid="core-relative" className="mb-6">
      <SL>vs Market ({relative.universeCount} assets)</SL>
      <div className="flex gap-8">
        <Tip text={`Lower than ${relative.riskPercentile}% of assets`}>
          <div>
            <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Risk Pctl</div>
            <div className="text-[20px] font-bold tabular-nums" style={{ color: riskC }}>{relative.riskPercentile}%</div>
            <div className="text-[11px] font-semibold" style={{ color: riskC }}>vs med {relative.riskVsMedian > 0 ? '+' : ''}{relative.riskVsMedian}</div>
          </div>
        </Tip>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Shift Rank</div>
          <div className="text-[20px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{relative.shiftRank}<span className="text-[13px] font-medium" style={{ color: '#94a3b8' }}>/{relative.shiftTotal}</span></div>
        </div>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Instab Rank</div>
          <div className="text-[20px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{relative.instabilityRank}<span className="text-[13px] font-medium" style={{ color: '#94a3b8' }}>/{relative.instabilityTotal}</span></div>
        </div>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Bias vs Avg</div>
          <div className="text-[20px] font-bold tabular-nums" style={{ color: relative.biasVsAvg > 5 ? '#16a34a' : relative.biasVsAvg < -5 ? '#dc2626' : '#94a3b8' }}>
            {relative.biasVsAvg > 0 ? '+' : ''}{relative.biasVsAvg}%
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-0.5" style={{ color: '#64748b' }}>Regime</div>
          <div className="text-[12px] font-bold" style={{ color: relative.regimeAlignsGlobal ? '#16a34a' : '#d97706' }}>
            {relative.regimeAlignsGlobal ? 'Aligns' : 'Deviates'}
          </div>
          <div className="text-[11px]" style={{ color: '#94a3b8' }}>vs {relative.globalDominant}</div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ Explain ═══════════ */
function ExplainBlock({ explain }) {
  if (!explain) return null;
  return (
    <div data-testid="core-explain" className="mb-6">
      <SL>Engine Summary</SL>
      <div className="text-[14px] font-semibold mb-2" style={{ color: '#0f172a' }}>{explain.oneLiner}</div>
      <div className="space-y-0.5">
        {(explain.bullets || []).map((b, i) => (
          <div key={i} className="text-[12px] flex gap-2" style={{ color: '#64748b' }}>
            <span style={{ color: '#94a3b8' }}>·</span><span>{b}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════ Universe Panel ═══════════ */
function UniversePanel({ data }) {
  if (!data) return null;
  const { regimeDistribution, riskDistribution, biasDistribution, topUnstable, topRisky, topOpportunities } = data;
  const total = data.meta?.count || 1;
  const BC = { bullish: '#16a34a', bearish: '#dc2626', neutral: '#94a3b8' };

  return (
    <div data-testid="core-universe">
      <SL>Universe — {total} assets</SL>
      <div className="flex gap-12 mb-5">
        <div>
          <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#64748b' }}>Regime</div>
          {Object.entries(regimeDistribution).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 mb-0.5">
              <span className="text-[12px] font-bold w-24 capitalize" style={{ color: RC[k] || '#94a3b8' }}>{k}</span>
              <span className="text-[14px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{v}</span>
              <span className="text-[11px]" style={{ color: '#94a3b8' }}>({(v / total * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#64748b' }}>Risk</div>
          {Object.entries(riskDistribution).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 mb-0.5">
              <span className="text-[12px] font-bold w-24 capitalize" style={{ color: RKC[k] || '#94a3b8' }}>{k}</span>
              <span className="text-[14px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{v}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#64748b' }}>Bias</div>
          {Object.entries(biasDistribution).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 mb-0.5">
              <span className="text-[12px] font-bold w-24 capitalize" style={{ color: BC[k] || '#94a3b8' }}>{k}</span>
              <span className="text-[14px] font-bold tabular-nums" style={{ color: '#0f172a' }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex gap-10">
        {topUnstable?.length > 0 && (
          <div className="flex-1">
            <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#d97706' }}>Top Unstable</div>
            {topUnstable.slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-center gap-2 mb-0.5">
                <span className="text-[12px] font-bold" style={{ color: '#0f172a' }}>{a.symbol}</span>
                <span className="text-[11px] tabular-nums" style={{ color: '#d97706' }}>{(a.shiftProb * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
        {topRisky?.length > 0 && (
          <div className="flex-1">
            <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#dc2626' }}>Top Risky</div>
            {topRisky.slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-center gap-2 mb-0.5">
                <span className="text-[12px] font-bold" style={{ color: '#0f172a' }}>{a.symbol}</span>
                <span className="text-[11px] tabular-nums" style={{ color: '#dc2626' }}>{a.risk}</span>
              </div>
            ))}
          </div>
        )}
        {topOpportunities?.length > 0 && (
          <div className="flex-1">
            <div className="text-[11px] uppercase font-semibold mb-2" style={{ color: '#16a34a' }}>Top Opportunities</div>
            {topOpportunities.slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-center gap-2 mb-0.5">
                <span className="text-[12px] font-bold" style={{ color: '#0f172a' }}>{a.symbol}</span>
                <span className="text-[11px] tabular-nums" style={{ color: '#16a34a' }}>amp {a.amp.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════ Position Sizing Panel ═══════════ */
const MODE_COLORS = { DEFENSIVE: '#d97706', NEUTRAL: '#94a3b8', AGGRESSIVE: '#16a34a' };
const MODE_BG = { DEFENSIVE: 'rgba(217,119,6,0.06)', NEUTRAL: 'rgba(148,163,184,0.06)', AGGRESSIVE: 'rgba(22,163,106,0.06)' };

function PositionSizingPanel({ posData }) {
  if (!posData) return null;
  const { sizeMult, mode, blocked, explain, blockedReasons, components, inputs } = posData;
  const mc = MODE_COLORS[mode] || '#94a3b8';
  const bg = MODE_BG[mode] || 'rgba(148,163,184,0.06)';
  const reasons = blocked ? blockedReasons : explain;

  return (
    <div data-testid="position-sizing-panel" className="rounded-2xl p-5 mb-6" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Position Sizing Policy</SL>
      <div className="flex items-center gap-6 mb-4">
        <div className="flex items-center gap-3">
          <div data-testid="position-size-value" className="text-[36px] font-black tabular-nums leading-none" style={{ color: blocked ? '#dc2626' : mc }}>
            {blocked ? '0.00' : sizeMult.toFixed(2)}
            <span className="text-[16px] font-bold ml-0.5">x</span>
          </div>
          <div className="flex flex-col gap-1">
            <span data-testid="position-mode-badge" className="text-[11px] font-bold tracking-wide px-2 py-0.5 rounded-md" style={{ color: mc, background: bg }}>
              {mode}
            </span>
            {blocked && (
              <span className="text-[11px] font-bold tracking-wide px-2 py-0.5 rounded-md" style={{ color: '#dc2626', background: 'rgba(220,38,38,0.06)' }}>
                BLOCKED
              </span>
            )}
          </div>
        </div>

        {!blocked && components && (
          <div className="flex-1 grid grid-cols-3 gap-x-4 gap-y-1 text-[11px]" style={{ color: '#64748b' }}>
            <ComponentRow label="Confidence" value={components.confFactor} />
            <ComponentRow label="Risk Penalty" value={components.riskPenalty} />
            <ComponentRow label="Sync Factor" value={components.syncFactor} />
            <ComponentRow label="Macro Mult" value={components.macroMult} />
            <ComponentRow label="Mode Factor" value={components.modeFactor} />
            <ComponentRow label="Appetite" value={components.appetite} />
          </div>
        )}
      </div>

      {reasons?.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {reasons.map((r, i) => (
            <div key={i} className="flex items-start gap-2 text-[12px]" style={{ color: blocked ? '#dc2626' : '#475569' }}>
              <span className="mt-0.5">{blocked ? <Ban className="w-3 h-3" /> : <Check className="w-3 h-3" style={{ color: '#16a34a' }} />}</span>
              <span>{r}</span>
            </div>
          ))}
        </div>
      )}

      {inputs && (
        <div className="mt-3 flex gap-4 text-[10px]" style={{ color: '#94a3b8' }}>
          <span>Core: {inputs.core.direction} ({(inputs.core.confidence * 100).toFixed(0)}%)</span>
          <span>Macro: {inputs.macro.regime} (RO {(inputs.macro.riskOffProb * 100).toFixed(0)}%)</span>
          <span>Risk: S{inputs.risk.structural}/T{inputs.risk.tactical}</span>
          <span>Sync: {inputs.sync.state} ({inputs.sync.alignmentScore}%)</span>
        </div>
      )}
    </div>
  );
}

function ComponentRow({ label, value }) {
  return (
    <div className="flex justify-between items-center" data-testid={`pos-comp-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <span>{label}</span>
      <span className="font-semibold tabular-nums" style={{ color: '#0f172a' }}>{typeof value === 'number' ? value.toFixed(3) : value}</span>
    </div>
  );
}

/* ═══════════ MAIN PAGE ═══════════ */
export default function CoreEnginePage() {
  const [data, setData] = useState(null);
  const [universeData, setUniverseData] = useState(null);
  const [syncData, setSyncData] = useState(null);
  const [posData, setPosData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState('global');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [tf, setTfState] = useState('1h');
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchRef = useRef(null);
  const searchTimer = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const scope = mode === 'asset' ? 'asset' : 'global';
      const sym = mode === 'asset' ? symbol : 'BTCUSDT';
      const res = await fetch(`${API}/api/core-engine/snapshot?scope=${scope}&symbol=${sym}&tf=${tf}`);
      setData(await res.json());
      // Fetch sync data and position sizing in parallel
      fetch(`${API}/api/core/macro-sync?symbol=${sym}&tf=${tf}`).then(r => r.json()).then(setSyncData).catch(() => {});
      fetch(`${API}/api/core/position-size?asset=${sym}&tf=${tf}`).then(r => r.json()).then(setPosData).catch(() => {});
      if (mode === 'global') {
        fetch(`${API}/api/core-engine/universe?tf=${tf}`).then(r => r.json()).then(setUniverseData).catch(() => {});
      }
    } catch (e) { console.error('Core fetch:', e); }
    setLoading(false);
  }, [mode, symbol, tf]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!searchQuery || searchQuery.length < 1) { setSearchResults([]); return; }
    clearTimeout(searchTimer.current);
    setSearchLoading(true);
    searchTimer.current = setTimeout(() => {
      fetch(`${API}/api/core-engine/search?q=${encodeURIComponent(searchQuery)}`)
        .then(r => r.json())
        .then(d => { setSearchResults(d.results || []); setSearchLoading(false); })
        .catch(() => { setSearchResults([]); setSearchLoading(false); });
    }, 300);
    return () => clearTimeout(searchTimer.current);
  }, [searchQuery]);

  useEffect(() => {
    if (!searchOpen) return;
    const h = (e) => { if (searchRef.current && !searchRef.current.contains(e.target)) { setSearchOpen(false); setSearchQuery(''); } };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [searchOpen]);

  const selectSymbol = (s) => { setSymbol(s); setMode('asset'); setSearchOpen(false); setSearchQuery(''); setSearchResults([]); };
  const resetGlobal = () => { setMode('global'); setSymbol('BTCUSDT'); };

  return (
    <div className="max-w-[1200px] mx-auto px-6 pb-12">
      <Header data={data} mode={mode} symbol={symbol} loading={loading} tf={tf} setTf={setTfState} onRefresh={fetchData} resetGlobal={resetGlobal} syncData={syncData} />
      <SearchBar searchOpen={searchOpen} setSearchOpen={setSearchOpen} searchRef={searchRef}
        searchQuery={searchQuery} setSearchQuery={setSearchQuery} searchResults={searchResults}
        searchLoading={searchLoading} selectSymbol={selectSymbol} />

      {loading && !data && (
        <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin" style={{ color: '#94a3b8' }} /></div>
      )}

      {data?.ok && (
        <>
          <KPIRow data={data} />
          {mode === 'asset' && data.relative && <RelativePanel relative={data.relative} />}
          <PositionSizingPanel posData={posData} />
          <div className="flex gap-12 mb-2">
            <LeftColumn data={data} />
            <RightColumn data={data} />
          </div>
          <ExplainBlock explain={data.explain} />
          {mode === 'global' && universeData?.ok && <UniversePanel data={universeData} />}
        </>
      )}
    </div>
  );
}
