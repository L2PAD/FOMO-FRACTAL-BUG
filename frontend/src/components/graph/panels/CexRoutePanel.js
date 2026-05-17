import React from 'react';
import { ChevronLeft, ChevronRight, Shield, Activity, AlertCircle, Lock, X, Copy, Check } from 'lucide-react';
import { fmtUsd } from '../utils';

/* ── Locked Route Panel (right-side) ── */
export const CexLockedPanel = React.memo(({
  lockedCexData, expandedCluster, isPathsCollapsed,
  onUnlock, setExpandedCluster, setIsPathsCollapsed,
}) => {
  const isCexNode = (n) => n.type === 'cex' || n.type === 'exchange' || n.id.startsWith('cex:') || n.id.startsWith('exchange:');
  return (
    <div data-testid="cex-route-locked-panel" style={{
      position: 'absolute', top: '56px', right: '12px', zIndex: 30,
      backgroundColor: 'rgba(15, 23, 42, 0.95)', border: '1px solid rgba(251, 191, 36, 0.25)',
      borderRadius: '12px', padding: '14px', color: '#e2e8f0', backdropFilter: 'blur(12px)',
      minWidth: '280px', maxWidth: '320px', fontSize: '12px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      maxHeight: 'calc(100% - 72px)', overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Lock size={13} color="#fbbf24" />
          <span style={{ fontWeight: 600, fontSize: '13px', color: '#fbbf24' }}>CEX Route</span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>{lockedCexData.nodes} node{lockedCexData.nodes !== 1 ? 's' : ''}</span>
        </div>
        <button data-testid="cex-route-unlock-btn" onClick={onUnlock}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
          <X size={14} />
        </button>
      </div>
      {/* Flow Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
        <div style={{ backgroundColor: 'rgba(48, 164, 108, 0.1)', border: '1px solid rgba(48, 164, 108, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Inflow</div>
          <div data-testid="cex-lock-inflow" style={{ color: '#30A46C', fontWeight: 600, fontSize: '13px' }}>{fmtUsd(lockedCexData.inflow)}</div>
        </div>
        <div style={{ backgroundColor: 'rgba(229, 72, 77, 0.1)', border: '1px solid rgba(229, 72, 77, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Outflow</div>
          <div data-testid="cex-lock-outflow" style={{ color: '#E5484D', fontWeight: 600, fontSize: '13px' }}>{fmtUsd(lockedCexData.outflow)}</div>
        </div>
        <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Net</div>
          <div data-testid="cex-lock-net" style={{ color: lockedCexData.net >= 0 ? '#30A46C' : '#E5484D', fontWeight: 600, fontSize: '13px' }}>
            {lockedCexData.net >= 0 ? '+' : ''}{fmtUsd(lockedCexData.net)}
          </div>
        </div>
        <div style={{ backgroundColor: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', borderRadius: '8px', padding: '7px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', marginBottom: '1px' }}>Total Volume</div>
          <div data-testid="cex-lock-total" style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '13px' }}>{fmtUsd(lockedCexData.total)}</div>
        </div>
      </div>
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '6px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase' }}>Edges</div>
          <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '12px' }}>{lockedCexData.edges}</div>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '6px 8px' }}>
          <div style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase' }}>TX Count</div>
          <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '12px' }}>{lockedCexData.txCount.toLocaleString()}</div>
        </div>
      </div>
      {/* Wash / Route Risk Intelligence */}
      {(lockedCexData.washScore > 0 || (lockedCexData.washFlags || []).length > 0 || (lockedCexData.dbWashAlerts || []).length > 0) && (() => {
        const score = lockedCexData.washScore || 0;
        const flags = lockedCexData.washFlags || [];
        const dbAlerts = lockedCexData.dbWashAlerts || [];
        const riskLabel = score >= 0.6 ? 'High Risk' : score >= 0.3 ? 'Medium Risk' : 'Low Risk';
        const riskColor = score >= 0.6 ? '#E5484D' : score >= 0.3 ? '#fbbf24' : '#30A46C';
        const sevColor = (s) => s === 'high' ? '#E5484D' : s === 'medium' ? '#fbbf24' : '#64748b';
        return (
          <div data-testid="wash-risk-section" style={{
            marginTop: '8px', padding: '8px 10px', borderRadius: '8px',
            backgroundColor: `${riskColor}0D`, border: `1px solid ${riskColor}33`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Shield size={12} color={riskColor} />
                <span style={{ fontSize: '10px', fontWeight: 600, color: riskColor, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Route Risk</span>
              </div>
              <span data-testid="wash-risk-score" style={{
                fontSize: '11px', fontWeight: 700, color: riskColor,
                backgroundColor: `${riskColor}1A`, padding: '1px 6px', borderRadius: '4px',
              }}>
                {riskLabel} ({Math.round(score * 100)}%)
              </span>
            </div>
            {flags.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: dbAlerts.length > 0 ? '6px' : '0' }}>
                {flags.map((flag, fi) => (
                  <span key={fi} data-testid={`wash-flag-${fi}`} title={flag.description} style={{
                    fontSize: '9px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px',
                    backgroundColor: `${sevColor(flag.severity)}1A`,
                    border: `1px solid ${sevColor(flag.severity)}33`,
                    color: sevColor(flag.severity), cursor: 'default',
                  }}>
                    {flag.label}
                  </span>
                ))}
              </div>
            )}
            {dbAlerts.length > 0 && (
              <div style={{ fontSize: '9px', color: '#94a3b8', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '4px' }}>
                {dbAlerts.length} DB alert{dbAlerts.length !== 1 ? 's' : ''}: {[...new Set(dbAlerts.map(a => a.pattern_type))].join(', ')}
              </div>
            )}
          </div>
        );
      })()}
      {/* Route paths — grouped tree view */}
      {lockedCexData.routes.length > 0 && (() => {
        const groups = new Map();
        lockedCexData.routes.forEach((route, i) => {
          const rp = route.resolvedPath || [];
          if (rp.length < 2) return;
          const prefix = rp.slice(0, -1);
          const target = rp[rp.length - 1];
          const key = prefix.map(n => n.id).join('\u2192');
          if (!groups.has(key)) groups.set(key, { prefix, targets: [], routeIndices: [], routes: [] });
          const g = groups.get(key);
          g.targets.push(target);
          g.routeIndices.push(i);
          g.routes.push(route);
        });
        const groupArr = Array.from(groups.values());
        return (
          <div style={{ marginTop: '8px', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase', fontWeight: 600 }}>Paths</div>
              <button data-testid="paths-collapse-toggle"
                onClick={() => setIsPathsCollapsed(v => !v)}
                style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px', fontSize: '10px' }}>
                {isPathsCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} style={{ transform: 'rotate(-90deg)' }} />}
              </button>
            </div>
            {!isPathsCollapsed && groupArr.map((group, gi) => {
              const { prefix, targets, routes: gRoutes } = group;
              const source = prefix[0];
              const intermediates = prefix.slice(1);
              return (
                <div key={gi} style={{ marginBottom: '8px', padding: '4px 6px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '3px', flexWrap: 'wrap', fontSize: '11px' }}>
                    <span style={{ color: isCexNode(source) ? '#fbbf24' : '#94a3b8', fontWeight: isCexNode(source) ? 600 : 400, fontSize: '11px' }}>
                      {(source.label || '').replace(/_/g, ' ').slice(0, 20)}
                    </span>
                    {intermediates.length > 0 && (
                      <>
                        <span style={{ color: '#475569', fontSize: '10px' }}>&rarr;</span>
                        {intermediates.length === 1 ? (
                          <span
                            data-testid={`cex-intermediate-${gi}`}
                            onClick={() => {
                              const isActive = expandedCluster?.groupIndex === gi;
                              setExpandedCluster(isActive ? null : {
                                groupIndex: gi,
                                segments: gRoutes[0]?.segments || [],
                                intermediates: intermediates,
                              });
                            }}
                            style={{
                              color: expandedCluster?.groupIndex === gi ? '#38bdf8' : '#94a3b8',
                              fontWeight: 400, fontSize: '10px', cursor: 'pointer',
                              borderBottom: '1px dashed rgba(56,189,248,0.4)',
                            }}>
                            {(intermediates[0].label || '').replace(/_/g, ' ').slice(0, 16)}
                          </span>
                        ) : (
                          <span
                            data-testid={`cex-cluster-badge-${gi}`}
                            onClick={() => {
                              const isActive = expandedCluster?.groupIndex === gi;
                              setExpandedCluster(isActive ? null : {
                                groupIndex: gi,
                                segments: gRoutes[0]?.segments || [],
                                intermediates: intermediates,
                              });
                            }}
                            style={{
                              color: '#38bdf8', cursor: 'pointer', fontWeight: 500, fontSize: '10px',
                              backgroundColor: expandedCluster?.groupIndex === gi ? 'rgba(56,189,248,0.2)' : 'rgba(56,189,248,0.1)',
                              border: '1px solid rgba(56,189,248,0.3)', borderRadius: '4px', padding: '1px 6px',
                            }}>
                            {intermediates.length} addresses
                          </span>
                        )}
                      </>
                    )}
                  </div>
                  <div style={{ marginLeft: intermediates.length > 0 ? '12px' : '0', marginTop: '3px' }}>
                    {targets.map((tgt, ti) => (
                      <div key={ti} style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '10px', padding: '1px 0' }}>
                        <span style={{ color: '#475569' }}>&rarr;</span>
                        <span style={{ color: isCexNode(tgt) ? '#fbbf24' : '#94a3b8', fontWeight: isCexNode(tgt) ? 600 : 400, fontSize: '10px' }}>
                          {(tgt.label || '').replace(/_/g, ' ').slice(0, 20)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: '9px', color: '#475569', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span>{gRoutes[0]?.hops ?? 0} hop{(gRoutes[0]?.hops ?? 0) !== 1 ? 's' : ''} &middot; {targets.length} target{targets.length !== 1 ? 's' : ''}</span>
                    {gRoutes[0]?.wash_score > 0 && (
                      <span data-testid={`wash-badge-${gi}`} style={{
                        color: gRoutes[0].wash_score >= 0.6 ? '#E5484D' : gRoutes[0].wash_score >= 0.3 ? '#fbbf24' : '#64748b',
                        fontSize: '8px', fontWeight: 700, letterSpacing: '0.03em',
                      }}>
                        <Shield size={8} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '1px' }} />
                        {Math.round(gRoutes[0].wash_score * 100)}%
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
});
CexLockedPanel.displayName = 'CexLockedPanel';

/* ── Segment Analysis Panel (left of locked panel) ── */
export const CexSegmentPanel = React.memo(({ expandedCluster, lockedCexData, copiedAddr, hideWeakLinks, setHideWeakLinks, onClose, onCopyAddr }) => {
  const segs = (expandedCluster.segments || []).slice().sort((a, b) => b.confidence - a.confidence);
  const visibleSegs = hideWeakLinks ? segs.filter(s => s.confidence >= 0.4) : segs;
  const top3 = segs.slice(0, 3);
  const chainConfidence = top3.length > 0 ? Math.round((top3.reduce((s, seg) => s + seg.confidence, 0) / top3.length) * 100) / 100 : 0;
  const chainLabel = chainConfidence >= 0.7 ? 'High confidence' : chainConfidence >= 0.45 ? 'Mixed' : 'Low confidence';
  const chainColor = chainConfidence >= 0.7 ? '#30A46C' : chainConfidence >= 0.45 ? '#fbbf24' : '#E5484D';
  const getSegLabel = (c) => c >= 0.7 ? 'Likely' : c >= 0.45 ? 'Possible' : 'Weak';
  const getSegColor = (c) => c >= 0.7 ? '#30A46C' : c >= 0.45 ? '#fbbf24' : '#E5484D';

  return (
    <div data-testid="cex-cluster-panel" style={{
      position: 'absolute', top: '56px', right: '344px', zIndex: 31,
      backgroundColor: 'rgba(15, 23, 42, 0.95)', border: '1px solid rgba(56, 189, 248, 0.25)',
      borderRadius: '12px', padding: '14px', color: '#e2e8f0', backdropFilter: 'blur(12px)',
      minWidth: '260px', maxWidth: '310px', fontSize: '12px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Activity size={13} color="#38bdf8" />
          <span style={{ fontWeight: 600, fontSize: '12px', color: '#38bdf8' }}>Segment Analysis</span>
        </div>
        <button data-testid="cex-cluster-close-btn" onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
          <X size={14} />
        </button>
      </div>
      <div data-testid="chain-quality" style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '7px 10px', borderRadius: '8px', marginBottom: '10px',
        backgroundColor: 'rgba(255,255,255,0.03)', border: `1px solid ${chainColor}33`,
      }}>
        <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>Chain Quality</span>
        <span style={{ fontSize: '12px', fontWeight: 600, color: chainColor }}>
          {chainLabel} ({Math.round(chainConfidence * 100)}%)
        </span>
      </div>
      {segs.some(s => s.confidence < 0.4) && (
        <button data-testid="hide-weak-toggle"
          onClick={() => setHideWeakLinks(v => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px', width: '100%',
            background: hideWeakLinks ? 'rgba(229,72,77,0.12)' : 'rgba(255,255,255,0.03)',
            border: hideWeakLinks ? '1px solid rgba(229,72,77,0.3)' : '1px solid rgba(100,116,139,0.15)',
            borderRadius: '6px', padding: '5px 8px', cursor: 'pointer', marginBottom: '8px',
            color: hideWeakLinks ? '#E5484D' : '#64748b', fontSize: '10px', fontWeight: 500,
          }}>
          <AlertCircle size={11} />
          {hideWeakLinks ? `Weak hidden (${segs.length - visibleSegs.length})` : 'Hide weak links'}
        </button>
      )}
      <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
        {visibleSegs.length === 0 && (
          <div style={{ fontSize: '10px', color: '#475569', textAlign: 'center', padding: '12px 0' }}>No segments to display</div>
        )}
        {visibleSegs.map((seg, idx) => {
          const srcAddr = seg.source.id.includes(':') ? seg.source.id.split(':').pop() : seg.source.id;
          const tgtAddr = seg.target.id.includes(':') ? seg.target.id.split(':').pop() : seg.target.id;
          const confPct = Math.round(seg.confidence * 100);
          const segColor = getSegColor(seg.confidence);
          const segLabel = getSegLabel(seg.confidence);
          return (
            <div key={idx} style={{
              padding: '6px 8px', borderRadius: '6px', marginBottom: '4px',
              backgroundColor: 'rgba(255,255,255,0.02)', borderLeft: `2px solid ${segColor}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '10px', flex: 1, minWidth: 0 }}>
                  <span style={{ color: '#e2e8f0', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '90px' }}>
                    {(seg.source.label || '').replace(/_/g, ' ').slice(0, 12)}
                  </span>
                  <span style={{ color: '#475569' }}>&rarr;</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '90px' }}>
                    {(seg.target.label || '').replace(/_/g, ' ').slice(0, 12)}
                  </span>
                </div>
                <span style={{ color: segColor, fontWeight: 600, fontSize: '10px', whiteSpace: 'nowrap', marginLeft: '6px' }}>
                  {segLabel} ({confPct}%)
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '9px', color: '#475569', fontFamily: 'monospace' }}>
                  {srcAddr.length > 10 ? srcAddr.slice(0, 6) + '..' + srcAddr.slice(-4) : srcAddr}
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button data-testid={`copy-src-${idx}`} onClick={() => onCopyAddr(srcAddr)}
                    style={{ background: 'none', border: 'none', color: copiedAddr === srcAddr ? '#30A46C' : '#475569', cursor: 'pointer', padding: '1px' }}>
                    {copiedAddr === srcAddr ? <Check size={10} /> : <Copy size={10} />}
                  </button>
                  <button data-testid={`copy-tgt-${idx}`} onClick={() => onCopyAddr(tgtAddr)}
                    style={{ background: 'none', border: 'none', color: copiedAddr === tgtAddr ? '#30A46C' : '#475569', cursor: 'pointer', padding: '1px' }}>
                    {copiedAddr === tgtAddr ? <Check size={10} /> : <Copy size={10} />}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {/* Wash flags for the route being analyzed */}
      {(() => {
        const routeIdx = expandedCluster.groupIndex;
        const gRoutes = lockedCexData.routes || [];
        const route = gRoutes[routeIdx];
        const rFlags = route?.wash_flags || [];
        if (rFlags.length === 0) return null;
        const sevColor = (s) => s === 'high' ? '#E5484D' : s === 'medium' ? '#fbbf24' : '#64748b';
        return (
          <div data-testid="segment-wash-flags" style={{
            marginTop: '6px', padding: '6px 8px', borderRadius: '6px',
            backgroundColor: 'rgba(229, 72, 77, 0.06)', border: '1px solid rgba(229, 72, 77, 0.15)',
          }}>
            <div style={{ fontSize: '9px', fontWeight: 600, color: '#E5484D', textTransform: 'uppercase', marginBottom: '4px' }}>
              <Shield size={9} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '3px' }} />
              Wash Signals
            </div>
            {rFlags.map((f, fi) => (
              <div key={fi} style={{ fontSize: '9px', color: sevColor(f.severity), padding: '1px 0' }}>
                {f.label}: <span style={{ color: '#94a3b8' }}>{f.description}</span>
              </div>
            ))}
          </div>
        );
      })()}
      <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid rgba(100,116,139,0.15)', display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#475569' }}>
        <span>{segs.length} segment{segs.length !== 1 ? 's' : ''}</span>
        <span>{(expandedCluster.intermediates || []).length} address{(expandedCluster.intermediates || []).length !== 1 ? 'es' : ''}</span>
      </div>
    </div>
  );
});
CexSegmentPanel.displayName = 'CexSegmentPanel';
