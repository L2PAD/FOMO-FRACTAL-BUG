/**
 * SignalsTab — colored priority text, cluster type labels + Cross-Market Intelligence section.
 */
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Flame, AlertTriangle, ArrowRightLeft, TrendingDown, BarChart3, Check } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SignalsTab() {
  const [metaAlerts, setMetaAlerts] = useState([]);
  const [regime, setRegime] = useState(null);
  const [alertsFeed, setAlertsFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cmSignals, setCmSignals] = useState([]);
  const [cmStrategies, setCmStrategies] = useState({ actionable: [], no_trade: [] });
  const [cmLoading, setCmLoading] = useState(true);
  const [cpSignals, setCpSignals] = useState([]);
  const [cpLoading, setCpLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/alert-correlation/history?limit=20`).then(r => r.ok ? r.json() : { metaAlerts: [] }).catch(() => ({ metaAlerts: [] })),
      fetch(`${API}/api/alert-correlation/regime`).then(r => r.ok ? r.json() : { regime: null }).catch(() => ({ regime: null })),
    ]).then(([ma, rg]) => {
      setMetaAlerts(ma.metaAlerts || []);
      setRegime(rg.regime || null);
    }).finally(() => setLoading(false));
  }, []);

  // Fetch Cross-Market Intelligence
  useEffect(() => {
    setCmLoading(true);
    Promise.all([
      fetch(`${API}/api/cross-market/signals`).then(r => r.ok ? r.json() : { signals: [] }).catch(() => ({ signals: [] })),
      fetch(`${API}/api/cross-market/strategies`).then(r => r.ok ? r.json() : { actionable: [], no_trade: [] }).catch(() => ({ actionable: [], no_trade: [] })),
    ]).then(([sig, strat]) => {
      setCmSignals(sig.signals || []);
      setCmStrategies({ actionable: strat.actionable || [], no_trade: strat.no_trade || [] });
    }).finally(() => setCmLoading(false));
  }, []);

  // Fetch Cross-Platform Intelligence (Kalshi)
  useEffect(() => {
    setCpLoading(true);
    fetch(`${API}/api/cross-market/kalshi/signals`)
      .then(r => r.ok ? r.json() : { signals: [] })
      .then(d => setCpSignals(d.signals || []))
      .catch(() => {})
      .finally(() => setCpLoading(false));
  }, []);

  useEffect(() => {
    const wsUrl = API.replace(/^http/, 'ws') + '/api/ws';
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => ws.send(JSON.stringify({ action: 'subscribe', channel: 'alerts' }));
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'alert:realtime' || msg.type === 'alert:urgent') {
            const alert = msg.payload;
            if (alert?.id) setAlertsFeed(prev => [alert, ...prev.filter(a => a.id !== alert.id)].slice(0, 50));
          }
        } catch {}
      };
    } catch {}
    return () => { if (ws) ws.close(); };
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading signals...</div>;

  const important = alertsFeed.filter(a =>
    a.type === 'ENTRY_SIGNAL' || a.type === 'EXIT_SIGNAL' || a.type === 'RISK_ALERT' || a.type === 'STATE_CHANGE'
  );

  return (
    <div className="px-6 py-5 space-y-6" data-testid="signals-tab">
      {/* Regime */}
      {regime && (
        <div className="text-sm" data-testid="regime-banner">
          <span className="text-gray-400">Regime:</span>{' '}
          <span className={`font-semibold ${
            regime.direction === 'RISK_ON' ? 'text-emerald-600' :
            regime.direction === 'RISK_OFF' ? 'text-red-500' : 'text-gray-600'
          }`}>
            {regime.direction === 'RISK_ON' ? 'Risk On' : regime.direction === 'RISK_OFF' ? 'Risk Off' : 'Neutral'}
          </span>
        </div>
      )}

      {/* Important */}
      <div>
        <h2 className="text-sm font-medium text-gray-900 mb-2">Important</h2>
        {important.length > 0 ? (
          <div className="bg-white rounded-lg border border-gray-200/60 divide-y divide-gray-100">
            {important.map((a, i) => {
              const typeColor = signalTypeColor(a.type);
              return (
                <div key={a.id || i} className="px-4 py-3 text-sm" data-testid={`signal-${a.id}`}>
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-semibold uppercase tracking-wider ${typeColor}`}>
                      {a.type?.replace(/_/g, ' ')}
                    </span>
                    <span className="font-medium text-gray-900">{a.asset}</span>
                    <span className="text-gray-500 truncate flex-1">{a.market}</span>
                    <span className="text-xs text-gray-400 font-mono shrink-0">{new Date(a.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4">No important signals — system is monitoring</p>
        )}
      </div>

      {/* Clusters */}
      <div>
        <h2 className="text-sm font-medium text-gray-900 mb-2">
          Clusters {metaAlerts.length > 0 && <span className="text-gray-400">({metaAlerts.length})</span>}
        </h2>
        {metaAlerts.length > 0 ? (
          <div className="bg-white rounded-lg border border-gray-200/60 divide-y divide-gray-100">
            {metaAlerts.map(ma => <ClusterRow key={ma.metaAlertId} ma={ma} />)}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4">No active clusters</p>
        )}
      </div>

      {/* Cross-Market Intelligence */}
      <CrossMarketSection signals={cmSignals} strategies={cmStrategies} loading={cmLoading} />

      {/* Cross-Platform Intelligence (Poly ↔ Kalshi) */}
      <CrossPlatformSection signals={cpSignals} loading={cpLoading} />
    </div>
  );
}

function signalTypeColor(type) {
  if (type === 'ENTRY_SIGNAL') return 'text-emerald-600';
  if (type === 'EXIT_SIGNAL' || type === 'RISK_ALERT') return 'text-red-500';
  if (type === 'STATE_CHANGE') return 'text-blue-600';
  return 'text-gray-500';
}

function clusterTypeColor(type) {
  if (!type) return 'text-gray-400';
  const t = type.toUpperCase();
  if (t.includes('RISK') || t.includes('UNLOCK')) return 'text-red-500';
  if (t.includes('ROTATION') || t.includes('CONFIRMATION')) return 'text-emerald-600';
  return 'text-amber-600';
}

function ClusterRow({ ma }) {
  const [open, setOpen] = useState(false);
  const isHighPrio = ma.priority === 'HIGH';
  return (
    <div data-testid={`cluster-${ma.metaAlertId}`}>
      <div
        className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-gray-50/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="text-gray-400">
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </span>
        {isHighPrio && <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
        <span className={`text-xs font-semibold uppercase tracking-wider ${clusterTypeColor(ma.type)}`}>
          {ma.type?.replace(/_/g, ' ')}
        </span>
        <span className="text-sm text-gray-600 truncate flex-1">{ma.summary}</span>
        <span className="text-xs text-gray-400 font-mono shrink-0">{new Date(ma.timestamp).toLocaleTimeString()}</span>
      </div>
      {open && (
        <div className="px-4 pb-3 ml-8 space-y-2">
          <div className="flex gap-3 flex-wrap">
            {(ma.assets || []).map((a, i) => (
              <span key={i} className="text-xs text-blue-600 font-medium">{a}</span>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            {ma.keyDrivers?.length > 0 && (
              <div>
                <div className="text-xs text-gray-400 mb-0.5">Drivers</div>
                {ma.keyDrivers.map((d, i) => <div key={i} className="text-sm text-emerald-600 leading-relaxed">+ {d}</div>)}
              </div>
            )}
            {ma.risks?.length > 0 && (
              <div>
                <div className="text-xs text-gray-400 mb-0.5">Risks</div>
                {ma.risks.map((r, i) => <div key={i} className="text-sm text-red-500 leading-relaxed">- {r}</div>)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}



/* ============ CROSS-MARKET INTELLIGENCE SECTION ============ */

function CrossMarketSection({ signals, strategies, loading }) {
  const [expandedSignal, setExpandedSignal] = useState(null);

  if (loading) {
    return (
      <div data-testid="cross-market-section">
        <h2 className="text-sm font-medium text-gray-900 mb-2 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-gray-400" />
          Cross-Market Intelligence
        </h2>
        <p className="text-sm text-gray-400 py-4">Loading cross-market analysis...</p>
      </div>
    );
  }

  const highSignals = signals.filter(s => s.severity === 'HIGH');
  const mediumSignals = signals.filter(s => s.severity === 'MEDIUM');
  const lowSignals = signals.filter(s => s.severity === 'LOW');
  const actionable = strategies.actionable || [];

  return (
    <div data-testid="cross-market-section" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-gray-400" />
          Cross-Market Intelligence
          {signals.length > 0 && (
            <span className="text-gray-400 font-normal">({signals.length} signals)</span>
          )}
        </h2>
        {actionable.length > 0 && (
          <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full" data-testid="cm-actionable-count">
            {actionable.length} actionable
          </span>
        )}
      </div>

      {/* Actionable Strategies */}
      {actionable.length > 0 && (
        <div className="space-y-2" data-testid="cm-strategies">
          {actionable.map((s, i) => (
            <StrategyCard key={i} strategy={s} />
          ))}
        </div>
      )}

      {/* High Severity Signals */}
      {highSignals.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-red-500 mb-1.5">
            High Severity ({highSignals.length})
          </div>
          <div className="bg-white rounded-lg border border-red-100 divide-y divide-gray-100">
            {highSignals.map((s, i) => (
              <CrossMarketSignalRow
                key={i}
                signal={s}
                expanded={expandedSignal === `high-${i}`}
                onToggle={() => setExpandedSignal(expandedSignal === `high-${i}` ? null : `high-${i}`)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Medium Severity Signals */}
      {mediumSignals.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-amber-500 mb-1.5">
            Medium ({mediumSignals.length})
          </div>
          <div className="bg-white rounded-lg border border-gray-200/60 divide-y divide-gray-100">
            {mediumSignals.map((s, i) => (
              <CrossMarketSignalRow
                key={i}
                signal={s}
                expanded={expandedSignal === `med-${i}`}
                onToggle={() => setExpandedSignal(expandedSignal === `med-${i}` ? null : `med-${i}`)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Low Severity Signals */}
      {lowSignals.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1.5">
            Low ({lowSignals.length})
          </div>
          <div className="bg-white rounded-lg border border-gray-200/60 divide-y divide-gray-100">
            {lowSignals.map((s, i) => (
              <CrossMarketSignalRow
                key={i}
                signal={s}
                expanded={expandedSignal === `low-${i}`}
                onToggle={() => setExpandedSignal(expandedSignal === `low-${i}` ? null : `low-${i}`)}
              />
            ))}
          </div>
        </div>
      )}

      {signals.length === 0 && (
        <p className="text-sm text-gray-400 py-4">No cross-market signals detected. Markets appear structurally consistent.</p>
      )}
    </div>
  );
}


function CrossMarketSignalRow({ signal, expanded, onToggle }) {
  const typeIcon = signalTypeIcon(signal.type);
  const severityColor = signal.severity === 'HIGH' ? 'text-red-500' : signal.severity === 'MEDIUM' ? 'text-amber-500' : 'text-gray-400';

  return (
    <div data-testid={`cm-signal-${signal.type}`}>
      <div
        className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-gray-50/50 transition-colors"
        onClick={onToggle}
      >
        <span className="text-gray-400">
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </span>
        {typeIcon}
        <span className={`text-xs font-semibold uppercase tracking-wider ${severityColor}`}>
          {signal.type?.replace(/_/g, ' ')}
        </span>
        <span className="text-xs font-medium text-blue-600">{signal.entity}</span>
        <span className="text-sm text-gray-500 truncate flex-1">{signal.message}</span>
        {signal.gap_pct != null && (
          <span className={`text-xs font-mono font-medium ${signal.gap_pct > 3 ? 'text-red-500' : 'text-amber-500'}`}>
            {signal.gap_pct}%
          </span>
        )}
      </div>
      {expanded && (
        <div className="px-4 pb-3 ml-8 space-y-1.5">
          {signal.relation_mode && (
            <div className="text-xs text-gray-400">
              Mode: <span className="font-medium text-gray-600">{signal.relation_mode}</span>
            </div>
          )}
          {signal.confidence != null && (
            <div className="text-xs text-gray-400">
              Confidence: <span className="font-medium text-gray-600">{(signal.confidence * 100).toFixed(0)}%</span>
            </div>
          )}
          <div className="text-xs text-gray-500">{signal.message}</div>
        </div>
      )}
    </div>
  );
}


function StrategyCard({ strategy }) {
  const ab = strategy.actionability_breakdown || {};
  const severity = strategy.actionability_severity || 'MEDIUM';
  const severityColor = severity === 'STRONG' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' :
    severity === 'HIGH' ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-gray-600 bg-gray-50 border-gray-200';
  const borderColor = severity === 'STRONG' ? 'border-emerald-200' :
    severity === 'HIGH' ? 'border-amber-200' : 'border-gray-200';

  return (
    <div
      className={`bg-white rounded-lg border ${borderColor} p-4 space-y-2`}
      data-testid={`cm-strategy-${strategy.strategy_type}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded uppercase tracking-wider">
            {strategy.strategy_type?.replace(/_/g, ' ')}
          </span>
          <span className="text-xs font-medium text-blue-600">{strategy.entity}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${severityColor}`} data-testid="actionability-badge">
            {severity}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-medium text-gray-500">
            score {strategy.mispricing_score?.toFixed(3)}
          </span>
          {strategy.actionability_score != null && (
            <span className="text-[10px] font-mono text-gray-400" data-testid="actionability-score">
              act {strategy.actionability_score?.toFixed(3)}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${strategy.action_a === 'SELL_YES' ? 'text-red-600' : 'text-emerald-600'}`}>
            {strategy.action_a}
          </span>
          <span className="text-xs text-gray-500 truncate max-w-[200px]" title={strategy.question_a}>
            ${strategy.threshold_a?.toLocaleString()} ({(strategy.price_a * 100).toFixed(1)}%)
          </span>
        </div>
        <ArrowRightLeft className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${strategy.action_b === 'BUY_YES' ? 'text-emerald-600' : 'text-red-600'}`}>
            {strategy.action_b}
          </span>
          <span className="text-xs text-gray-500 truncate max-w-[200px]" title={strategy.question_b}>
            ${strategy.threshold_b?.toLocaleString()} ({(strategy.price_b * 100).toFixed(1)}%)
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-500">{strategy.rationale}</p>

      {/* Actionability breakdown */}
      {Object.keys(ab).length > 0 && (
        <div className="flex items-center gap-3 pt-1 border-t border-gray-100" data-testid="actionability-breakdown">
          <ActionabilityPill label="Liquidity" value={ab.liquidity_component} max={0.30} />
          <ActionabilityPill label="Execution" value={ab.execution_component} max={0.20} />
          <ActionabilityPill label="Time" value={ab.time_component} max={0.10} />
        </div>
      )}
    </div>
  );
}


function ActionabilityPill({ label, value, max }) {
  if (value == null) return null;
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  const color = pct >= 80 ? 'text-emerald-600' : pct >= 50 ? 'text-amber-600' : 'text-gray-400';
  const levelLabel = pct >= 80 ? 'High' : pct >= 50 ? 'Good' : 'Low';
  return (
    <span className={`text-[10px] font-medium ${color}`} data-testid={`pill-${label.toLowerCase()}`}>
      {label}: {levelLabel}
    </span>
  );
}


function signalTypeIcon(type) {
  if (type === 'STRUCTURE_MISMATCH') return <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />;
  if (type === 'MONOTONIC_BREAK') return <TrendingDown className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
  if (type === 'EQUIVALENT_DIVERGENCE') return <ArrowRightLeft className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
  if (type === 'LADDER_VIOLATION') return <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
  if (type === 'LADDER_GAP') return <BarChart3 className="w-3.5 h-3.5 text-gray-400 shrink-0" />;
  return <BarChart3 className="w-3.5 h-3.5 text-gray-400 shrink-0" />;
}


/* ============ CROSS-PLATFORM INTELLIGENCE (Poly ↔ Kalshi) ============ */

function CrossPlatformSection({ signals, loading }) {
  const [expanded, setExpanded] = useState(null);

  if (loading) {
    return (
      <div data-testid="cross-platform-section">
        <h2 className="text-sm font-medium text-gray-900 mb-2 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-blue-500" />
          Cross-Platform Intelligence
        </h2>
        <p className="text-sm text-gray-400 py-4">Loading cross-platform analysis...</p>
      </div>
    );
  }

  const actionable = signals.filter(s => s.actionable);
  const monitoring = signals.filter(s => !s.actionable);

  return (
    <div data-testid="cross-platform-section" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-blue-500" />
          Cross-Platform Intelligence
          <span className="text-[10px] font-medium text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">Poly × Kalshi</span>
          {signals.length > 0 && (
            <span className="text-gray-400 font-normal">({signals.length})</span>
          )}
        </h2>
        {actionable.length > 0 && (
          <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full" data-testid="cp-actionable-count">
            {actionable.length} actionable
          </span>
        )}
      </div>

      {/* Actionable Signals */}
      {actionable.map((sig, i) => (
        <CrossPlatformCard
          key={`act-${i}`}
          signal={sig}
          expanded={expanded === `act-${i}`}
          onToggle={() => setExpanded(expanded === `act-${i}` ? null : `act-${i}`)}
        />
      ))}

      {/* Monitoring Signals */}
      {monitoring.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1.5">
            Monitoring ({monitoring.length})
          </div>
          {monitoring.map((sig, i) => (
            <CrossPlatformCard
              key={`mon-${i}`}
              signal={sig}
              expanded={expanded === `mon-${i}`}
              onToggle={() => setExpanded(expanded === `mon-${i}` ? null : `mon-${i}`)}
              compact
            />
          ))}
        </div>
      )}

      {signals.length === 0 && (
        <p className="text-sm text-gray-400 py-4">No cross-platform signals. Markets appear consistent across Poly and Kalshi.</p>
      )}
    </div>
  );
}


function CrossPlatformCard({ signal, expanded, onToggle, compact = false }) {
  const strat = signal.strategy;
  const severity = signal.severity || 'MEDIUM';
  const edgeBadge = signal.edge_badge || '';
  const trapFlags = signal.trap_flags || [];

  const severityStyles = severity === 'STRONG'
    ? 'border-emerald-200 bg-emerald-50/30'
    : severity === 'HIGH'
    ? 'border-amber-200 bg-amber-50/20'
    : 'border-gray-200';

  const severityBadge = severity === 'STRONG'
    ? 'text-emerald-700 bg-emerald-100'
    : severity === 'HIGH'
    ? 'text-amber-700 bg-amber-100'
    : 'text-gray-500 bg-gray-100';

  const edgeLabel = (signal.edge_case_type || 'UNKNOWN').replace(/_/g, ' ').toLowerCase();

  return (
    <div className={`rounded-lg border p-4 space-y-2 ${severityStyles}`} data-testid={`cp-signal-${signal.entity}`}>
      {/* Header */}
      <div className="flex items-center justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex items-center gap-2 flex-wrap">
          {strat && strat.strategy_type !== 'NO_TRADE' && (
            <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded uppercase tracking-wider"
                  data-testid="cp-strategy-type">
              {strat.strategy_type?.replace(/_/g, ' ')}
            </span>
          )}
          <span className="text-sm font-semibold text-blue-600">{signal.entity}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${severityBadge}`} data-testid="cp-severity">
            {severity}
          </span>
          <span className="text-[10px] font-medium text-gray-400 capitalize">{edgeLabel}</span>
          {/* Edge Badge */}
          {edgeBadge === 'verified_edge' && (
            <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded flex items-center gap-0.5"
                  data-testid="cp-verified-badge">
              <Check className="w-3 h-3" /> Verified Edge
            </span>
          )}
          {edgeBadge === 'execution_risk' && (
            <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded flex items-center gap-0.5"
                  data-testid="cp-risk-badge">
              <AlertTriangle className="w-3 h-3" /> Execution Risk
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono font-bold text-emerald-600" data-testid="cp-edge">
            +{signal.gap_pct}%
          </span>
          <span className="text-gray-400">
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </span>
        </div>
      </div>

      {/* Legs (always visible for actionable) */}
      {strat && strat.legs && strat.legs.length > 0 && !compact && (
        <div className="flex items-center gap-4 pl-1">
          {strat.legs.map((leg, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <span className={`text-sm font-bold ${leg.action === 'BUY_YES' ? 'text-emerald-600' : 'text-red-600'}`}>
                {leg.action}
              </span>
              <span className="text-xs text-gray-500 capitalize">{leg.platform}</span>
              {leg.price != null && (
                <span className="text-xs font-mono text-gray-400">({(leg.price * 100).toFixed(1)}%)</span>
              )}
              {i < strat.legs.length - 1 && <ArrowRightLeft className="w-3 h-3 text-gray-300 mx-1" />}
            </div>
          ))}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="space-y-2 pt-2 border-t border-gray-100/60">
          {strat && strat.reasoning && (
            <div className="space-y-0.5">
              {strat.reasoning.map((r, i) => (
                <p key={i} className="text-xs text-gray-500">{r}</p>
              ))}
            </div>
          )}
          <div className="flex gap-4 text-[10px] text-gray-400">
            <span>Score: {signal.score?.toFixed(3)}</span>
            <span>Actionability: {signal.actionability_score?.toFixed(3)}</span>
            {signal.real_edge_score != null && <span>Real Edge: {signal.real_edge_score?.toFixed(3)}</span>}
            <span>Confidence: {(signal.strategy?.confidence || 0).toFixed(2)}</span>
          </div>
          {/* Trap Flags */}
          {trapFlags.length > 0 && (
            <div className="flex gap-2">
              {trapFlags.map((flag, i) => (
                <span key={i} className="text-[10px] text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded">
                  {flag.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
          {/* Real Edge Components */}
          {signal.real_edge_components && expanded && (
            <div className="flex gap-3 text-[10px] text-gray-400">
              <span>Liq Balance: {signal.real_edge_components.liquidity_balance}</span>
              <span>Spread: {signal.real_edge_components.spread_quality}</span>
              <span>Timing: {signal.real_edge_components.timing_alignment}</span>
              <span>Stability: {signal.real_edge_components.stability}</span>
            </div>
          )}
          {strat && strat.risks && strat.risks.length > 0 && (
            <div className="text-[10px] text-gray-400">
              Risks: {strat.risks.join(' | ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
