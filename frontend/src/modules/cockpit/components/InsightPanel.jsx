/**
 * InsightPanel — Deep-dive panel for a selected pattern
 * ======================================================
 * 
 * Opens when user CLICKS a pattern on the chart.
 * 5 sections, NO scroll, minimal design.
 * 
 * Sections:
 * 1. Header — Pattern Name + Confidence badge
 * 2. Context — Market state, regime
 * 3. Interpretation — line1, line2
 * 4. Watch Levels — breakout/breakdown levels
 * 5. Meta — type, family, role
 */

import React from 'react';

const InsightPanel = ({ pattern, interpretation, watchLevels: watchLevelsProp, lifecycle: lifecycleProp, onClose }) => {
  if (!pattern) return null;

  const formatType = (type) => {
    if (!type) return 'Pattern';
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  const patternType = pattern.type || pattern.contract?.type || '';
  const role = pattern.role || 'dominant';
  const isDominant = role === 'dominant';
  
  // Handle interpretation being a string or object
  const interpObj = typeof interpretation === 'object' && interpretation !== null ? interpretation : {};
  
  // Get confidence from multiple sources (render_stack → interpretation → 0)
  const rawConf = pattern.contract?.confidence || pattern.confidence || interpObj.confidence || 0;
  const confPercent = Math.round(rawConf < 1 && rawConf > 0 ? rawConf * 100 : rawConf);

  // Direction from type heuristic
  const direction = patternType.includes('top') || patternType.includes('head_shoulders') || patternType.includes('rising_wedge')
    ? 'bearish'
    : patternType.includes('bottom') || patternType.includes('inverse') || patternType.includes('falling_wedge')
    ? 'bullish'
    : 'neutral';

  const directionColor = direction === 'bullish' ? '#22c55e' : direction === 'bearish' ? '#ef4444' : '#94a3b8';

  const watchLevels = interpObj.watch_levels || watchLevelsProp || [];
  const marketState = interpObj.market_state || 'DEVELOPING';
  const line1 = interpObj.line1 || (typeof interpretation === 'string' ? interpretation : '');
  const line2 = interpObj.line2 || '';
  const narrative = interpObj.narrative || '';

  // Family from type
  const family = patternType.includes('triangle') || patternType.includes('wedge') || patternType.includes('pennant')
    ? 'Converging'
    : patternType.includes('channel') || patternType.includes('flag')
    ? 'Parallel'
    : patternType.includes('top') || patternType.includes('bottom') || patternType.includes('head') || patternType.includes('range') || patternType.includes('rectangle')
    ? 'Horizontal'
    : 'Other';

  return (
    <div
      data-testid="insight-panel"
      style={{
        position: 'absolute',
        bottom: '60px',
        left: '16px',
        width: '280px',
        background: 'rgba(15, 23, 42, 0.96)',
        backdropFilter: 'blur(12px)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.1)',
        color: '#ffffff',
        zIndex: 60,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: 'hidden',
      }}
    >
      {/* ═══════════════ 1. HEADER ═══════════════ */}
      <div
        data-testid="insight-panel-header"
        style={{
          padding: '14px 16px 10px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: directionColor,
            }}
          />
          <span style={{ fontSize: '14px', fontWeight: '700' }}>
            {formatType(patternType)}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '12px',
              fontWeight: '700',
              color: confPercent >= 60 ? '#22c55e' : confPercent >= 40 ? '#fbbf24' : '#94a3b8',
            }}
          >
            {confPercent}%
          </span>
          <button
            data-testid="insight-panel-close"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: '16px',
              lineHeight: 1,
              padding: '0 2px',
            }}
          >
            ×
          </button>
        </div>
      </div>

      {/* ═══════════════ 2. CONTEXT ═══════════════ */}
      <div
        data-testid="insight-panel-context"
        style={{
          padding: '10px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
        }}
      >
        <div style={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>
          Context
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            fontSize: '10px',
            fontWeight: '700',
            textTransform: 'uppercase',
            padding: '2px 6px',
            borderRadius: '3px',
            background: marketState.includes('REVERSAL') ? 'rgba(239,68,68,0.15)' :
              marketState === 'COMPRESSION' ? 'rgba(251,191,36,0.15)' :
              marketState === 'CONFLICTED' ? 'rgba(249,115,22,0.15)' :
              'rgba(139,92,246,0.15)',
            color: marketState.includes('REVERSAL ↓') ? '#ef4444' :
              marketState.includes('REVERSAL ↑') ? '#22c55e' :
              marketState === 'COMPRESSION' ? '#fbbf24' :
              marketState === 'CONFLICTED' ? '#f97316' :
              '#8b5cf6',
          }}>
            {marketState}
          </span>
          <span style={{ fontSize: '11px', color: directionColor, fontWeight: '600' }}>
            {direction.toUpperCase()}
          </span>
        </div>
      </div>

      {/* ═══════════════ 3. INTERPRETATION ═══════════════ */}
      {(line1 || line2) && (
        <div
          data-testid="insight-panel-interpretation"
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}
        >
          <div style={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>
            Interpretation
          </div>
          {line1 && (
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.85)', lineHeight: '1.5', marginBottom: '3px' }}>
              {line1}
            </div>
          )}
          {line2 && (
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', lineHeight: '1.5' }}>
              {line2}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════ 4. WATCH LEVELS ═══════════════ */}
      {watchLevels.length > 0 && (
        <div
          data-testid="insight-panel-watch-levels"
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}
        >
          <div style={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
            Watch Levels
          </div>
          {watchLevels.map((lvl, i) => (
            <div
              key={i}
              data-testid={`insight-watch-level-${i}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 0',
              }}
            >
              <span style={{
                color: lvl.type === 'breakout_up' ? '#22c55e' : '#ef4444',
                fontSize: '12px',
                fontWeight: '700',
              }}>
                {lvl.type === 'breakout_up' ? '▲' : '▼'}
              </span>
              <span style={{
                color: lvl.type === 'breakout_up' ? '#22c55e' : '#ef4444',
                fontSize: '12px',
                fontWeight: '600',
                fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
              }}>
                {typeof lvl.price === 'number' ? lvl.price.toLocaleString() : lvl.price}
              </span>
              <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.35)' }}>
                — {lvl.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ═══════════════ 5. LIFECYCLE STATUS ═══════════════ */}
      {(() => {
        const lc = interpObj.lifecycle || lifecycleProp || null;
        if (!lc) return null;
        const lcState = lc.state || 'forming';
        const lcLabel = lc.label || '';
        const stateConfig = {
          forming: { bg: 'rgba(148,163,184,0.12)', color: '#94a3b8', text: 'FORMING' },
          confirmed_up: { bg: 'rgba(34,197,94,0.15)', color: '#22c55e', text: 'BREAKOUT' },
          confirmed_down: { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', text: 'BREAKDOWN' },
          invalidated: { bg: 'rgba(100,116,139,0.12)', color: '#64748b', text: 'INVALIDATED' },
        };
        const cfg = stateConfig[lcState] || stateConfig.forming;
        return (
          <div
            data-testid="insight-panel-lifecycle"
            style={{
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{
              fontSize: '10px',
              fontWeight: '800',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              padding: '2px 8px',
              borderRadius: '3px',
              background: cfg.bg,
              color: cfg.color,
            }}>
              {cfg.text}
            </span>
            {lcLabel && (
              <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)' }}>
                {lcLabel}
              </span>
            )}
          </div>
        );
      })()}

      {/* ═══════════════ 6. META ═══════════════ */}
      <div
        data-testid="insight-panel-meta"
        style={{
          padding: '10px 16px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '8px',
        }}
      >
        <div>
          <div style={{ fontSize: '9px', color: '#475569', marginBottom: '2px' }}>Type</div>
          <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600' }}>
            {patternType.replace(/_/g, ' ')}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '9px', color: '#475569', marginBottom: '2px' }}>Family</div>
          <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600' }}>
            {family}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '9px', color: '#475569', marginBottom: '2px' }}>Role</div>
          <div style={{ fontSize: '10px', fontWeight: '700', color: isDominant ? '#fbbf24' : '#64748b' }}>
            {isDominant ? 'MAIN' : 'ALT'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default InsightPanel;
