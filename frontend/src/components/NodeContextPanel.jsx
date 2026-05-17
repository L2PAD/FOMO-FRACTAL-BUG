import React, { useEffect, useState } from 'react';
import { X, Shield, TrendingUp, Network, Route, AlertTriangle, Copy, Check } from 'lucide-react';
import { fetchNodeDetail } from '../graph/services/graphDataService';

const CopyIconBtn = ({ addr }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(addr);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = addr; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };
  return (
    <button
      data-testid="copy-address-btn"
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy address'}
      style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? '#34d399' : '#64748b', padding: '2px', display: 'flex', alignItems: 'center', transition: 'color 0.15s' }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
};

const NodeContextPanel = ({ nodeId, nodeType, onClose, onNavigate, onDrillDown }) => {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!nodeId) return;
    setLoading(true);
    fetchNodeDetail(nodeId).then(data => {
      setDetail(data);
      setLoading(false);
    });
  }, [nodeId]);

  if (!nodeId) return null;

  const node = detail?.node || {};
  const overlays = detail?.overlays || [];
  const routes = detail?.routes || [];

  const panelType = node.type || nodeType || 'wallet';

  return (
    <div
      data-testid="node-context-panel"
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        width: '320px',
        maxHeight: 'calc(100% - 32px)',
        overflowY: 'auto',
        backgroundColor: 'rgba(15, 23, 42, 0.97)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: '14px',
        zIndex: 20,
        backdropFilter: 'blur(16px)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px', borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase',
            backgroundColor: 'rgba(148, 163, 184, 0.1)', padding: '2px 6px', borderRadius: '4px',
          }}>
            {(panelType || '').replace(/_/g, ' ')}
          </span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
            {(node.label || nodeId.split(':')[1]?.slice(0, 10) || 'Loading...').replace(/_/g, ' ')}
          </span>
        </div>
        <button
          data-testid="context-panel-close"
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: '2px' }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Address with Copy */}
      {(() => {
        const parts = (nodeId || '').split(':');
        const addr = parts[1] || parts[0] || '';
        if (!addr.startsWith('0x') || addr.length < 10) return null;
        const short = `${addr.slice(0, 6)}...${addr.slice(-4)}`;
        return (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '8px 16px', borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          }}>
            <span style={{ color: '#94a3b8', fontSize: '12px', fontFamily: "'Gilroy', sans-serif" }}>{short}</span>
            <CopyIconBtn addr={addr} />
          </div>
        );
      })()}

      {loading ? (
        <div style={{ padding: '40px 16px', textAlign: 'center' }}>
          <div style={{ width: '20px', height: '20px', border: '2px solid #8b5cf6', borderTopColor: 'transparent', borderRadius: '50%', margin: '0 auto', animation: 'spin 0.8s linear infinite' }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : (
        <div style={{ padding: '12px 16px' }}>
          {/* Scores Row */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '14px',
          }}>
            {node.smart_money_score > 0 && (
              <ScoreCard label="Smart Money" value={node.smart_money_score} color="#10b981" />
            )}
            {node.risk_score > 0 && (
              <ScoreCard label="Risk" value={node.risk_score} color="#ef4444" />
            )}
            {node.alpha_score > 0 && (
              <ScoreCard label="Alpha" value={node.alpha_score} color="#8b5cf6" />
            )}
            {node.importance_score > 0 && (
              <ScoreCard label="Importance" value={node.importance_score} color="#3b82f6" />
            )}
            {node.exposure_score > 0 && (
              <ScoreCard label="Exposure" value={node.exposure_score} color="#f59e0b" />
            )}
            {(node.degree > 0) && (
              <ScoreCard label="Degree" value={node.degree} color="#64748b" isRaw />
            )}
          </div>

          {/* Metadata */}
          {node.metadata && Object.keys(node.metadata).length > 0 && (
            <Section title="Details" icon={<Network size={12} />}>
              {Object.entries(node.metadata).map(([key, val]) => {
                if (val === null || val === undefined || val === '' || (Array.isArray(val) && val.length === 0)) return null;
                return (
                  <MetaRow key={key} label={key.replace(/_/g, ' ')} value={
                    Array.isArray(val) ? val.join(', ') : typeof val === 'object' ? JSON.stringify(val) : String(val)
                  } />
                );
              })}
            </Section>
          )}

          {/* Node Info */}
          {(node.actor_type || node.behavior || node.entity || node.cluster_id) && (
            <Section title="Identity" icon={<Shield size={12} />}>
              {node.entity && <MetaRow label="Entity" value={(node.entity || '').replace(/_/g, ' ')} />}
              {node.actor_type && <MetaRow label="Actor Type" value={(node.actor_type || '').replace(/_/g, ' ')} />}
              {node.behavior && <MetaRow label="Behavior" value={(node.behavior || '').replace(/_/g, ' ')} />}
              {node.cluster_id && (
                <MetaRow label="Cluster" value={node.cluster_id}
                  onClick={() => onNavigate && onNavigate(`cluster:${node.cluster_id}:ethereum`)} />
              )}
            </Section>
          )}

          {/* Overlays */}
          {overlays.length > 0 && (
            <Section title="Intelligence" icon={<AlertTriangle size={12} />}>
              {overlays.map((ov, idx) => (
                <div key={idx} style={{
                  padding: '6px 8px', marginBottom: '4px', borderRadius: '6px',
                  backgroundColor: ov.overlay_type === 'risk' ? 'rgba(239, 68, 68, 0.08)' :
                    ov.overlay_type === 'signal' ? 'rgba(16, 185, 129, 0.08)' :
                    ov.overlay_type === 'alert' ? 'rgba(245, 158, 11, 0.08)' : 'rgba(148, 163, 184, 0.05)',
                }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>
                    {ov.overlay_type}: {ov.sub_type}
                  </div>
                  {ov.data?.message && (
                    <div style={{ fontSize: '11px', color: '#cbd5e1', marginTop: '2px' }}>{ov.data.message}</div>
                  )}
                  {ov.data?.confidence != null && (
                    <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                      Confidence: {(ov.data.confidence * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              ))}
            </Section>
          )}

          {/* Routes */}
          {routes.length > 0 && (
            <Section title="Capital Routes" icon={<Route size={12} />}>
              {routes.slice(0, 5).map((rt, idx) => (
                <div key={idx} style={{
                  padding: '6px 8px', marginBottom: '4px', borderRadius: '6px',
                  backgroundColor: 'rgba(139, 92, 246, 0.05)',
                }}>
                  <div style={{ fontSize: '10px', color: '#a78bfa', fontWeight: 600 }}>
                    {rt.route_type?.replace(/_/g, ' ')} — ${(rt.amount_usd || 0).toLocaleString()}
                  </div>
                  <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                    {shortenId(rt.source)} → {rt.via ? `${shortenId(rt.via)} → ` : ''}{shortenId(rt.destination)}
                  </div>
                </div>
              ))}
            </Section>
          )}

          {/* Navigate to Graph button */}
          {node.id && (
            <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
              <button
                data-testid="context-open-graph"
                onClick={() => onNavigate && onNavigate(node.id)}
                style={{
                  flex: 1, padding: '8px',
                  backgroundColor: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(139, 92, 246, 0.3)',
                  borderRadius: '8px', color: '#a78bfa', fontSize: '11px', fontWeight: 600,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                Center Graph
              </button>
              {onDrillDown && panelType !== 'cluster' && panelType !== 'narrative' && (
                <button
                  data-testid="context-drill-down"
                  onClick={() => onDrillDown(node.id, panelType)}
                  style={{
                    flex: 1, padding: '8px',
                    backgroundColor: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)',
                    borderRadius: '8px', color: '#60a5fa', fontSize: '11px', fontWeight: 600,
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  Open {panelType.charAt(0).toUpperCase() + panelType.slice(1)} Page
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function ScoreCard({ label, value, color, isRaw = false }) {
  const display = isRaw ? value : `${(value * 100).toFixed(0)}%`;
  return (
    <div style={{
      padding: '6px 8px', borderRadius: '8px',
      backgroundColor: 'rgba(148, 163, 184, 0.05)',
      border: '1px solid rgba(148, 163, 184, 0.08)',
    }}>
      <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: '14px', fontWeight: 700, color, marginTop: '2px' }}>{display}</div>
    </div>
  );
}

function Section({ title, icon, children }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px',
        fontSize: '10px', color: '#64748b', fontWeight: 600,
        textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.5px',
      }}>
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function MetaRow({ label, value, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '3px 0', cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'capitalize' }}>{label}</span>
      <span style={{
        fontSize: '11px', color: onClick ? '#a78bfa' : '#e2e8f0', fontWeight: 500,
        maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        textDecoration: onClick ? 'underline' : 'none',
      }}>{value}</span>
    </div>
  );
}

function shortenId(id) {
  if (!id) return '';
  const parts = id.split(':');
  if (parts.length >= 2) {
    const addr = parts[1];
    if (addr.startsWith('0x') && addr.length > 10) return `${addr.slice(0, 6)}..${addr.slice(-4)}`;
    return addr.length > 12 ? addr.slice(0, 12) + '..' : addr;
  }
  return id.length > 16 ? id.slice(0, 16) + '..' : id;
}

export default NodeContextPanel;
