import React from 'react';
import { X } from 'lucide-react';
import MarketContextBlock from './MarketContextBlock';
import { fmtUsd } from '../utils';

const MODE_COLORS = { smart_money: '#22c55e', token_rotation: '#a78bfa', entity: '#38bdf8', risk: '#E5484D' };
const MODE_ICONS = {
  smart_money: 'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  entity: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2',
  risk: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z',
  token_rotation: 'M21.5 2v6h-6M2.5 22v-6h6',
};
const CAT_COLOR = (cat) => ({ smart_money: '#22c55e', entity: '#38bdf8', risk: '#E5484D', token_flow: '#a78bfa', route: '#fbbf24' }[cat] || '#94a3b8');
const TYPE_ICON = (type) => {
  if (type === 'accumulation') return '\u2193';
  if (type === 'distribution') return '\u2191';
  if (type === 'whale_activity') return '\u25CF';
  if (type === 'entity_cluster') return '\u25C6';
  if (type === 'rotation') return '\u27F2';
  if (type === 'loop_routing') return '\u21BB';
  if (type === 'high_risk_nodes') return '\u25B2';
  if (type === 'cex_flow_summary') return '\u21C4';
  return '\u2022';
};

const IntelligencePanel = React.memo(({
  graphMode, modeLabel, activeIntelligence, marketContext,
  expandedWalletSignal, setExpandedWalletSignal, onClose,
}) => {
  const modeColor = MODE_COLORS[graphMode] || '#60a5fa';

  return (
    <div data-testid="intelligence-panel" style={{
      position: 'absolute', top: '56px', right: '12px', zIndex: 30,
      backgroundColor: 'rgba(15, 23, 42, 0.95)', border: `1px solid ${modeColor}33`,
      borderRadius: '12px', padding: '14px', color: '#e2e8f0', backdropFilter: 'blur(12px)',
      minWidth: '280px', maxWidth: '320px', fontSize: '12px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      maxHeight: 'calc(100% - 72px)', overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={modeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d={MODE_ICONS[graphMode] || 'M12 2L2 7l10 5 10-5-10-5z'} />
          </svg>
          <span style={{ fontWeight: 600, fontSize: '13px', color: modeColor }}>{modeLabel}</span>
          <span style={{ fontSize: '10px', color: '#64748b' }}>{activeIntelligence.length} signal{activeIntelligence.length !== 1 ? 's' : ''}</span>
        </div>
        <button data-testid="intelligence-panel-close" onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
          <X size={14} />
        </button>
      </div>
      {/* Market Context */}
      <MarketContextBlock marketContext={marketContext} />
      {/* Signals */}
      {activeIntelligence.map((sig, si) => {
        const sc = CAT_COLOR(sig.category);
        const det = sig.details || {};
        return (
          <div key={si} data-testid={`intel-signal-${si}`} style={{
            padding: '10px', borderRadius: '8px', marginBottom: '6px',
            backgroundColor: `${sc}0D`, border: `1px solid ${sc}22`,
          }}>
            {/* Signal header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ fontSize: '14px', lineHeight: 1 }}>{TYPE_ICON(sig.type)}</span>
                <span style={{ fontWeight: 600, fontSize: '11px', color: sc, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  {sig.type.replace(/_/g, ' ')}
                </span>
              </div>
              <span style={{
                fontSize: '10px', fontWeight: 700, color: sc,
                backgroundColor: `${sc}1A`, padding: '1px 6px', borderRadius: '4px',
              }}>
                {Math.round(sig.confidence * 100)}%
              </span>
            </div>
            {/* Summary */}
            <div style={{ fontSize: '12px', color: '#e2e8f0', fontWeight: 500, marginBottom: '6px', lineHeight: 1.4 }}>
              {sig.summary}
            </div>
            {/* Confidence breakdown */}
            {sig.confidence_breakdown && sig.confidence_breakdown.length > 0 && (
              <div data-testid={`intel-breakdown-${si}`} style={{
                fontSize: '9px', color: '#64748b', marginBottom: '6px', padding: '4px 6px',
                backgroundColor: 'rgba(100,116,139,0.08)', borderRadius: '4px',
              }}>
                {sig.confidence_breakdown.map((line, bi) => (
                  <div key={bi} style={{ padding: '1px 0' }}>
                    <span style={{ color: '#94a3b8' }}>{line}</span>
                  </div>
                ))}
              </div>
            )}
            {/* Details */}
            <div style={{ fontSize: '10px', color: '#94a3b8' }}>
              {sig.type === 'entity_cluster' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>Size: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{det.cluster_size} addresses</span></div>
                  <div>Type: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{det.entity_type || 'unknown'}</span></div>
                  <div>Internal: <span style={{ color: '#30A46C', fontWeight: 500 }}>{fmtUsd(det.internal_flow_usd)}</span></div>
                  <div>External: <span style={{ color: '#60a5fa', fontWeight: 500 }}>{fmtUsd(det.external_flow_usd)}</span></div>
                </div>
              )}
              {(sig.type === 'accumulation' || sig.type === 'distribution') && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>Volume: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{fmtUsd(det.total_volume_usd)}</span></div>
                  <div style={{ textAlign: 'right' }}>
                    <span data-testid={`intel-wallets-badge-${si}`}
                      onClick={() => setExpandedWalletSignal(expandedWalletSignal?.signalIndex === si ? null : {
                        signalIndex: si,
                        wallets: det.wallets || [],
                        title: `${sig.type === 'accumulation' ? 'Accumulating' : 'Distributing'} Wallets`,
                        flowKey: sig.type === 'accumulation' ? 'inflow' : 'outflow',
                      })}
                      style={{
                        color: '#60a5fa', fontWeight: 600, fontSize: '10px', cursor: 'pointer',
                        backgroundColor: 'rgba(96,165,250,0.12)', padding: '2px 7px', borderRadius: '4px',
                        border: '1px solid rgba(96,165,250,0.25)',
                      }}>
                      [ {det.wallet_count} address{det.wallet_count !== 1 ? 'es' : ''} ]
                    </span>
                  </div>
                </div>
              )}
              {sig.type === 'whale_activity' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>Whales: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{det.whale_count}</span></div>
                  <div>Flow: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{fmtUsd(det.total_flow_usd)}</span></div>
                </div>
              )}
              {sig.type === 'high_risk_nodes' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>Flagged: <span style={{ color: '#E5484D', fontWeight: 500 }}>{det.node_count} node{det.node_count !== 1 ? 's' : ''}</span></div>
                  <div>Severity: <span style={{ color: det.severity === 'high' ? '#E5484D' : det.severity === 'medium' ? '#fbbf24' : '#94a3b8', fontWeight: 600 }}>{det.severity}</span></div>
                  <div>Avg risk: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{Math.round((det.avg_risk_score || 0) * 100)}%</span></div>
                </div>
              )}
              {sig.type === 'loop_routing' && (
                <div>
                  <div style={{ marginBottom: '3px' }}>Loops: <span style={{ color: '#E5484D', fontWeight: 500 }}>{det.loop_count}</span> &middot; Volume: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{fmtUsd(det.total_volume_usd)}</span></div>
                  {det.loops && det.loops.slice(0, 3).map((l, li) => (
                    <div key={li} style={{ fontSize: '9px', color: '#64748b', padding: '1px 0' }}>
                      {l.node_a} &#x2194; {l.node_b} <span style={{ color: '#94a3b8' }}>{fmtUsd(l.volume_usd)}</span>
                    </div>
                  ))}
                </div>
              )}
              {sig.type === 'rotation' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>From: <span style={{ color: '#a78bfa', fontWeight: 500 }}>{det.token_from_label}</span></div>
                  <div>To: <span style={{ color: '#a78bfa', fontWeight: 500 }}>{det.token_to_label}</span></div>
                  <div>Volume out: <span style={{ color: '#E5484D', fontWeight: 500 }}>{fmtUsd(det.volume_from_usd)}</span></div>
                  <div>Volume in: <span style={{ color: '#30A46C', fontWeight: 500 }}>{fmtUsd(det.volume_to_usd)}</span></div>
                  <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
                    <span data-testid={`rotation-wallets-badge-${si}`}
                      onClick={() => setExpandedWalletSignal(expandedWalletSignal?.signalIndex === `rot-${si}` ? null : {
                        signalIndex: `rot-${si}`,
                        wallets: (det.wallets || []).map(w => ({ ...w, inflow: w.buy_exposure, outflow: w.sell_exposure })),
                        title: `Rotating Wallets (${det.token_from_label} \u2192 ${det.token_to_label})`,
                        flowKey: 'sell_exposure',
                        tokenFrom: det.token_from_label,
                        tokenTo: det.token_to_label,
                      })}
                      style={{
                        color: '#a78bfa', fontWeight: 600, fontSize: '10px', cursor: 'pointer',
                        backgroundColor: 'rgba(167,139,250,0.12)', padding: '2px 7px', borderRadius: '4px',
                        border: '1px solid rgba(167,139,250,0.25)',
                      }}>
                      [ {det.shared_wallets} wallet{det.shared_wallets !== 1 ? 's' : ''} ]
                    </span>
                  </div>
                </div>
              )}
              {sig.type === 'cex_flow_summary' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <div>Inflow: <span style={{ color: '#30A46C', fontWeight: 500 }}>{fmtUsd(det.total_inflow_usd)}</span></div>
                  <div>Outflow: <span style={{ color: '#E5484D', fontWeight: 500 }}>{fmtUsd(det.total_outflow_usd)}</span></div>
                  <div>Net: <span style={{ color: det.net_flow_usd >= 0 ? '#30A46C' : '#E5484D', fontWeight: 600 }}>{det.net_flow_usd >= 0 ? '+' : ''}{fmtUsd(det.net_flow_usd)}</span></div>
                  <div>CEXes: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{det.cex_count}</span></div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});

IntelligencePanel.displayName = 'IntelligencePanel';

export default IntelligencePanel;
