import React, { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, X, BarChart3 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const LiquidityMapPanel = ({ style, inline = false, isOpen, onToggle, edgesShown = 0, entityId = null, onRouteClick }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [internalVisible, setInternalVisible] = useState(false);
  const [prevEntityId, setPrevEntityId] = useState(null);
  const visible = isOpen !== undefined ? isOpen : internalVisible;
  const toggleVisible = () => {
    const next = !visible;
    if (onToggle) onToggle(next);
    else setInternalVisible(next);
  };

  const fetchMap = useCallback(async () => {
    setLoading(true);
    try {
      const params = entityId ? `?entity=${encodeURIComponent(entityId)}` : '';
      const res = await fetch(`${API_URL}/api/graph-core/liquidity-map${params}`);
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error('[LiquidityMap] fetch error:', err);
    }
    setLoading(false);
  }, [entityId]);

  // Re-fetch when entity changes
  useEffect(() => {
    if (visible && entityId !== prevEntityId) {
      setPrevEntityId(entityId);
      setData(null);
    }
  }, [entityId, visible, prevEntityId]);

  useEffect(() => {
    if (visible && !data) fetchMap();
  }, [visible, data, fetchMap]);

  if (!visible) {
    return (
      <button data-testid="liquidity-map-toggle" onClick={toggleVisible}
        style={{
          display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 10px',
          backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(59, 130, 246, 0.25)',
          borderRadius: '8px', color: '#3b82f6', fontSize: '11px', fontWeight: 600,
          cursor: 'pointer', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap', ...style,
        }}>
        <BarChart3 size={12} /> Liquidity Map
      </button>
    );
  }

  const summary = data?.summary || {};
  const fromAgg = data?.from_aggregates || {};
  const toAgg = data?.to_aggregates || {};
  const topCP = data?.top_counterparties || [];
  const topRoutes = data?.top_routes || [];
  const routeMeta = data?.route_meta || {};
  const flowState = summary.flow_state || 'ACCUMULATION';
  const flowDriver = summary.flow_driver || null;

  const fmt = (v) => {
    if (!v || v === 0) return '$0';
    const abs = Math.abs(v);
    if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
    return `$${v.toFixed(0)}`;
  };

  const fmtNum = (v) => {
    if (!v) return '0';
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
    return v.toLocaleString();
  };

  const FLOW_COLORS = {
    'ACCUMULATION': '#22c55e',
    'DISTRIBUTION': '#EF4444',
    'ROUTING': '#EAB308',
  };
  const stateColor = FLOW_COLORS[flowState] || '#94a3b8';

  const SectionLabel = ({ children }) => (
    <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase', fontWeight: 600, marginBottom: '5px', marginTop: '10px' }}>{children}</div>
  );

  const AggRow = ({ label, value, pct, color }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 8px', borderRadius: '5px', marginBottom: '1px', backgroundColor: 'rgba(255,255,255,0.02)' }}>
      <span style={{ color: '#cbd5e1', fontSize: '11px' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ color: color || '#e2e8f0', fontWeight: 600, fontSize: '11px' }}>{fmt(value)}</span>
        {pct > 0 && <span style={{ color: '#64748b', fontSize: '10px' }}>({pct}%)</span>}
      </div>
    </div>
  );

  const panelContent = (
    <div data-testid="liquidity-map-panel" style={{
      ...(inline ? { position: 'absolute', top: '44px', left: 0, zIndex: 30 } : {}),
      backgroundColor: 'rgba(15, 23, 42, 0.95)', border: '1px solid rgba(59, 130, 246, 0.2)',
      borderRadius: '12px', padding: '14px', color: '#e2e8f0', backdropFilter: 'blur(12px)',
      minWidth: '360px', maxWidth: '400px', fontSize: '12px', maxHeight: '75vh', overflowY: 'auto',
      boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <BarChart3 size={14} color="#3b82f6" />
          <span style={{ fontWeight: 600, fontSize: '13px' }}>Liquidity Map</span>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button data-testid="liquidity-map-refresh" onClick={fetchMap}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={toggleVisible}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
            <X size={13} />
          </button>
        </div>
      </div>

      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>Loading...</div>
      )}

      {data && (
        <>
          {/* Block 1: INFLOW / OUTFLOW / NET / VOLUME */}
          <div data-testid="liquidity-flow-summary" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
            <div style={{ backgroundColor: 'rgba(48, 164, 108, 0.1)', border: '1px solid rgba(48, 164, 108, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Inflow</div>
              <div data-testid="liq-inflow" style={{ color: '#30A46C', fontWeight: 600, fontSize: '13px' }}>{fmt(summary.inflow)}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(229, 72, 77, 0.1)', border: '1px solid rgba(229, 72, 77, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Outflow</div>
              <div data-testid="liq-outflow" style={{ color: '#E5484D', fontWeight: 600, fontSize: '13px' }}>{fmt(summary.outflow)}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Net</div>
              <div data-testid="liq-net" style={{ color: (summary.net || 0) >= 0 ? '#30A46C' : '#E5484D', fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '3px' }}>
                {(summary.net || 0) >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                {(summary.net || 0) >= 0 ? '+' : ''}{fmt(summary.net || 0)}
              </div>
            </div>
            <div style={{ backgroundColor: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Total Volume</div>
              <div data-testid="liq-volume" style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '13px' }}>{fmt(summary.volume || summary.total_volume)}</div>
            </div>
          </div>

          {/* EDGES + TX COUNT */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
            <div data-testid="liq-edges" style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase' }}>Edges</div>
              <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '12px' }}>
                {edgesShown > 0
                  ? <><span style={{ color: '#3b82f6' }}>{edgesShown}</span> <span style={{ color: '#475569', fontSize: '10px' }}>shown</span> / <span>{fmtNum(summary.edges_total)}</span> <span style={{ color: '#475569', fontSize: '10px' }}>total</span></>
                  : <>{fmtNum(summary.edges_total)} <span style={{ color: '#475569', fontSize: '10px' }}>total</span></>}
              </div>
            </div>
            <div data-testid="liq-tx-count" style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase' }}>TX Count</div>
              <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '12px' }}>{fmtNum(summary.tx_count)}</div>
              {(summary.tx_in > 0 || summary.tx_out > 0) && (
                <div style={{ fontSize: '10px', marginTop: '1px' }}>
                  <span style={{ color: '#30A46C', fontWeight: 600 }}>IN:</span> <span style={{ color: '#94a3b8' }}>{fmtNum(summary.tx_in)}</span>
                  {'  '}
                  <span style={{ color: '#E5484D', fontWeight: 600 }}>OUT:</span> <span style={{ color: '#94a3b8' }}>{fmtNum(summary.tx_out)}</span>
                </div>
              )}
            </div>
          </div>

          {/* FLOW STATE */}
          <div data-testid="liquidity-flow-state" style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '7px 10px', borderRadius: '8px', marginBottom: '8px',
            backgroundColor: `${stateColor}10`,
            border: `1px solid ${stateColor}33`,
          }}>
            <span style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase', fontWeight: 600 }}>Flow State</span>
            <span data-testid="liq-flow-state-value" style={{ color: stateColor, fontWeight: 700, fontSize: '12px' }}>
              {flowState}
              {flowDriver && <span style={{ fontWeight: 500, fontSize: '11px' }}> ({flowDriver})</span>}
            </span>
          </div>

          {/* TOP ROUTES — the core CEX Flow v2 feature */}
          {topRoutes.length > 0 && (
            <>
              <SectionLabel>Flow Routes</SectionLabel>
              {topRoutes.slice(0, 7).map((route, i) => (
                <div key={route.type || i} data-testid={`route-${i}`}
                  onClick={() => route.sample_path?.length >= 2 && onRouteClick?.(route)}
                  style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 8px', borderRadius: '5px', marginBottom: '2px',
                  backgroundColor: route.wash_score > 0.5 ? 'rgba(239, 68, 68, 0.05)' : 'rgba(255,255,255,0.02)',
                  cursor: route.sample_path?.length >= 2 ? 'pointer' : 'default',
                  transition: 'background-color 0.15s',
                }}
                onMouseEnter={e => { if (route.sample_path?.length >= 2) e.currentTarget.style.backgroundColor = 'rgba(52, 211, 153, 0.1)'; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = route.wash_score > 0.5 ? 'rgba(239, 68, 68, 0.05)' : 'rgba(255,255,255,0.02)'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', minWidth: 0, flex: 1 }}>
                    <span style={{ color: '#cbd5e1', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {route.label}
                    </span>
                    {route.wash_score > 0.5 && (
                      <span style={{ color: '#EF4444', fontSize: '8px', fontWeight: 700, padding: '1px 4px', borderRadius: '3px', backgroundColor: 'rgba(239, 68, 68, 0.15)', whiteSpace: 'nowrap' }}>WASH</span>
                    )}
                  </div>
                  <div style={{ textAlign: 'right', whiteSpace: 'nowrap', marginLeft: '8px' }}>
                    <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '11px' }}>
                      {route.volume_usd > 0 ? fmt(route.volume_usd) : `${fmtNum(route.tx_count)} tx`}
                    </span>
                    {route.route_count > 1 && (
                      <span style={{ color: '#475569', fontSize: '9px', marginLeft: '4px' }}>{route.route_count}x</span>
                    )}
                  </div>
                </div>
              ))}
              {routeMeta.wash_route_count > 0 && (
                <div style={{ color: '#EF4444', fontSize: '10px', padding: '4px 8px', marginTop: '2px', opacity: 0.7 }}>
                  {routeMeta.wash_route_count} suspected wash route{routeMeta.wash_route_count > 1 ? 's' : ''} ({fmt(routeMeta.wash_volume_usd)})
                </div>
              )}
            </>
          )}

          {/* FROM / TO */}
          <SectionLabel>From</SectionLabel>
          {Object.entries(fromAgg)
            .filter(([, v]) => (v?.amount || v) > 0)
            .sort(([, a], [, b]) => (b?.amount || b) - (a?.amount || a))
            .map(([label, v]) => (
              <AggRow key={`from-${label}`} label={label} value={v?.amount ?? v} pct={v?.pct ?? 0} color="#30A46C" />
            ))}
          {Object.values(fromAgg).every(v => !(v?.amount || v)) && (
            <div style={{ color: '#475569', fontSize: '11px', padding: '3px 8px' }}>No inflow data</div>
          )}

          <SectionLabel>To</SectionLabel>
          {Object.entries(toAgg)
            .filter(([, v]) => (v?.amount || v) > 0)
            .sort(([, a], [, b]) => (b?.amount || b) - (a?.amount || a))
            .map(([label, v]) => (
              <AggRow key={`to-${label}`} label={label} value={v?.amount ?? v} pct={v?.pct ?? 0} color="#E5484D" />
            ))}
          {Object.values(toAgg).every(v => !(v?.amount || v)) && (
            <div style={{ color: '#475569', fontSize: '11px', padding: '3px 8px' }}>No outflow data</div>
          )}

          {/* TOP COUNTERPARTIES */}
          {topCP.length > 0 && (
            <>
              <SectionLabel>Top Counterparties</SectionLabel>
              {topCP.slice(0, 5).map((cp, i) => (
                <div key={cp.id || i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 8px', borderRadius: '5px', marginBottom: '1px', backgroundColor: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', minWidth: 0 }}>
                    <span style={{ color: '#475569', fontSize: '10px', minWidth: '14px' }}>{i + 1}.</span>
                    <span data-testid={`counterparty-${i}`} style={{ color: '#cbd5e1', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>{cp.label}</span>
                  </div>
                  <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '11px', whiteSpace: 'nowrap' }}>{fmt(cp.amount)}</span>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );

  if (inline) {
    return (
      <div style={{ position: 'relative' }}>
        <button data-testid="liquidity-map-toggle" onClick={toggleVisible}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 10px',
            backgroundColor: 'rgba(59, 130, 246, 0.18)', border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: '8px', color: '#3b82f6', fontSize: '11px', fontWeight: 600,
            cursor: 'pointer', backdropFilter: 'blur(10px)', whiteSpace: 'nowrap', ...style,
          }}>
          <BarChart3 size={12} /> Liquidity Map
        </button>
        {panelContent}
      </div>
    );
  }

  return panelContent;
};

export default LiquidityMapPanel;
