import React from 'react';
import { Copy } from 'lucide-react';

/**
 * HoverTooltip — pure display component for node hover info.
 * Does NOT know about graph state, modes, or loading.
 * Only renders node info at a fixed position.
 */
const HoverTooltip = React.memo(({ node, position }) => {
  if (!node) return null;

  const addr = node.address || (() => {
    const parts = (node.id || '').split(':');
    const mid = parts[1] || parts[0] || '';
    return mid.startsWith('0x') ? mid : null;
  })();
  const hasAddr = addr && addr.startsWith('0x') && addr.length >= 10;
  const shortAddr = hasAddr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : null;

  const copyAddress = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(addr).catch(() => {
      const ta = document.createElement('textarea');
      ta.value = addr; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
    });
    const btn = e.currentTarget;
    btn.dataset.copied = 'true';
    setTimeout(() => { btn.dataset.copied = ''; }, 1500);
  };

  const stats = [
    node.smartMoneyScore > 0 && { label: 'Smart Money', value: `${(node.smartMoneyScore * 100).toFixed(0)}%`, color: '#10b981' },
    node.riskScore > 0 && { label: 'Risk', value: `${(node.riskScore * 100).toFixed(0)}%`, color: node.riskScore > 0.7 ? '#ef4444' : node.riskScore > 0.4 ? '#f59e0b' : '#10b981' },
    node.totalFlowUsd > 0 && { label: 'Flow', value: `$${Number(node.totalFlowUsd).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: '#3b82f6' },
    node.capitalInfluenceScore > 0 && { label: 'Capital Influence', value: `${(node.capitalInfluenceScore * 100).toFixed(0)}%`, color: '#8b5cf6' },
    node.alphaScore > 0 && { label: 'Alpha', value: `${(node.alphaScore * 100).toFixed(0)}%`, color: '#f59e0b' },
    node.degree > 0 && { label: 'Connections', value: node.degree, color: '#e2e8f0' },
  ].filter(Boolean);

  return (
    <div data-testid="node-hover-tooltip" style={{
      position: 'fixed', left: position.x + 14, top: position.y + 14,
      backgroundColor: 'rgba(10, 14, 26, 0.97)', border: '1px solid rgba(100, 116, 139, 0.25)',
      borderRadius: '10px', padding: '10px 14px',
      pointerEvents: 'auto', zIndex: 1000, minWidth: '190px', maxWidth: '280px',
      backdropFilter: 'blur(14px)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    }}>
      {/* Name */}
      <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '13px', marginBottom: '4px', lineHeight: 1.3 }}>
        {(node.label || node.id || '').replace(/_/g, ' ')}
      </div>

      {/* Address + Copy */}
      {hasAddr && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
          <span style={{ color: '#64748b', fontSize: '11px', fontFamily: "'Gilroy', sans-serif" }}>{shortAddr}</span>
          <button data-testid="copy-address-btn" onClick={copyAddress}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: '2px', display: 'flex', alignItems: 'center', transition: 'color 0.15s' }}
            onMouseOver={(e) => e.currentTarget.style.color = '#fff'}
            onMouseOut={(e) => e.currentTarget.style.color = '#64748b'}
            title="Copy address"
          ><Copy size={12} /></button>
        </div>
      )}

      {/* Tags */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', backgroundColor: 'rgba(148,163,184,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
          {(node.type || 'wallet').replace(/_/g, ' ')}
        </span>
        {node.entity && (
          <span style={{ fontSize: '9px', fontWeight: 700, color: '#a78bfa', textTransform: 'uppercase', backgroundColor: 'rgba(139,92,246,0.12)', padding: '2px 6px', borderRadius: '4px' }}>
            {node.entity}
          </span>
        )}
        {node.clusterId && (
          <span style={{ fontSize: '9px', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', backgroundColor: 'rgba(56,189,248,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
            cluster
          </span>
        )}
      </div>

      {/* Stats grid */}
      {stats.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 14px' }}>
          {stats.map((s, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '10px', color: '#64748b' }}>{s.label}</span>
              <span style={{ fontSize: '11px', fontWeight: 600, color: s.color }}>{s.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

HoverTooltip.displayName = 'HoverTooltip';

export default HoverTooltip;
