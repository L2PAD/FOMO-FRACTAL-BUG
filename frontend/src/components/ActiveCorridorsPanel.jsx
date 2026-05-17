import React, { useState, useEffect, useCallback } from 'react';
import { ArrowRight, Zap, X, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ActiveCorridorsPanel = ({ onCorridorClick, style, inline = false, isOpen, onToggle }) => {
  const [corridors, setCorridors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [internalVisible, setInternalVisible] = useState(false);
  const visible = isOpen !== undefined ? isOpen : internalVisible;
  const toggleVisible = () => {
    const next = !visible;
    if (onToggle) onToggle(next);
    else setInternalVisible(next);
  };

  const fetchCorridors = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/graph-core/corridors/active?limit=15&min_value=0`);
      if (res.ok) {
        const data = await res.json();
        setCorridors(data.corridors || []);
      }
    } catch (err) {
      console.error('[ActiveCorridors] fetch error:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (visible) fetchCorridors();
  }, [visible, fetchCorridors]);

  // Inline mode: render toggle button that fits in a toolbar row
  const toggleBtn = (
    <button
      data-testid="corridors-panel-toggle"
      onClick={() => toggleVisible()}
      style={{
        ...(inline ? {} : { position: 'absolute', top: '56px', left: '16px', zIndex: 10 }),
        display: 'flex',
        alignItems: 'center',
        gap: '5px',
        padding: '6px 10px',
        backgroundColor: visible ? 'rgba(245, 158, 11, 0.18)' : 'rgba(15, 23, 42, 0.9)',
        border: '1px solid rgba(245, 158, 11, 0.25)',
        borderRadius: '8px',
        color: '#f59e0b',
        fontSize: '11px',
        fontWeight: 600,
        cursor: 'pointer',
        backdropFilter: 'blur(10px)',
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      <Zap size={12} />
      Corridors
    </button>
  );

  if (!visible) return toggleBtn;

  // Expanded panel
  const panel = (
    <div
      data-testid="corridors-panel"
      style={{
        ...(inline
          ? { position: 'absolute', top: '44px', left: 0, zIndex: 30 }
          : { position: 'absolute', top: '56px', left: '16px', zIndex: 20 }),
        width: '280px',
        maxHeight: '400px',
        overflow: 'auto',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: '12px',
        backdropFilter: 'blur(12px)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px', borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
      }}>
        <span style={{ color: '#f59e0b', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Zap size={14} /> Active Corridors
        </span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button data-testid="corridors-refresh-btn" onClick={fetchCorridors}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
          <button data-testid="corridors-close-btn" onClick={() => toggleVisible()}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
            <X size={14} />
          </button>
        </div>
      </div>

      <div style={{ padding: '6px' }}>
        {loading && corridors.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#475569', fontSize: '12px' }}>Loading corridors...</div>
        )}
        {!loading && corridors.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#475569', fontSize: '12px' }}>
            No active corridors detected yet.
            <br /><span style={{ fontSize: '10px', color: '#334155' }}>Corridors appear when graph data is loaded.</span>
          </div>
        )}
        {corridors.map((c, i) => (
          <button
            key={`${c.source}-${c.target}-${i}`}
            data-testid={`corridor-item-${i}`}
            onClick={() => onCorridorClick && onCorridorClick(c)}
            style={{
              display: 'block', width: '100%', padding: '10px 12px', marginBottom: '4px',
              backgroundColor: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.1)',
              borderRadius: '8px', cursor: 'pointer', textAlign: 'left', transition: 'background-color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.12)'}
            onMouseLeave={e => e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.05)'}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <span style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 500 }}>{c.source_label}</span>
              <ArrowRight size={12} style={{ color: '#f59e0b' }} />
              <span style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 500 }}>{c.target_label}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#f59e0b', fontSize: '11px', fontWeight: 600 }}>
                {c.total_amount_usd > 0
                  ? c.total_amount_usd >= 1000000 ? `$${(c.total_amount_usd / 1000000).toFixed(1)}M` : `$${(c.total_amount_usd / 1000).toFixed(0)}K`
                  : `${c.corridor_count} flow${c.corridor_count !== 1 ? 's' : ''}`}
              </span>
              {c.bridge_label && <span style={{ color: '#64748b', fontSize: '10px' }}>via {c.bridge_label}</span>}
              {c.corridor_count > 1 && <span style={{ color: '#475569', fontSize: '10px' }}>x{c.corridor_count}</span>}
            </div>
          </button>
        ))}
      </div>
    </div>
  );

  if (inline) {
    return (
      <div style={{ position: 'relative' }}>
        {toggleBtn}
        {panel}
      </div>
    );
  }

  return panel;
};

export default ActiveCorridorsPanel;
