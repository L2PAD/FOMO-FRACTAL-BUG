import React from 'react';
import { MODE_LABELS } from '../utils';

const ModeHUD = React.memo(({
  graphMode, isCexFlowMode, isRouteFocus, activeRoute, cexRoutes,
  activeIntelligence, onCloseRouteFocus, onCloseCexFlow, onCloseIntelMode,
}) => {
  // Route Focus HUD
  if (isRouteFocus && activeRoute) {
    return (
      <div data-testid="route-focus-hud" style={{
        position: 'absolute', bottom: '60px', left: '50%', transform: 'translateX(-50%)',
        zIndex: 20, display: 'flex', alignItems: 'center', gap: '12px',
        background: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(12px)',
        border: '1px solid rgba(52, 211, 153, 0.3)', borderRadius: '12px', padding: '10px 18px',
      }}>
        <span style={{ color: '#34D399', fontSize: '11px', fontWeight: 700, letterSpacing: '0.05em' }}>ROUTE FOCUS</span>
        <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 500 }}>{activeRoute.label}</span>
        <span style={{ color: '#64748b', fontSize: '11px' }}>${(activeRoute.volume_usd || 0).toLocaleString(undefined, {maximumFractionDigits: 0})}</span>
        <button data-testid="route-focus-close" onClick={onCloseRouteFocus}
          style={{ background: 'rgba(148, 163, 184, 0.15)', border: 'none', borderRadius: '6px',
            color: '#94a3b8', cursor: 'pointer', padding: '4px 8px', fontSize: '11px', fontWeight: 600 }}>
          ESC
        </button>
      </div>
    );
  }

  // CEX Flow HUD
  if (isCexFlowMode && !isRouteFocus) {
    return (
      <div data-testid="cex-flow-hud" style={{
        position: 'absolute', bottom: '60px', left: '50%', transform: 'translateX(-50%)',
        zIndex: 20, display: 'flex', alignItems: 'center', gap: '12px',
        background: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(12px)',
        border: '1px solid rgba(251, 191, 36, 0.3)', borderRadius: '12px', padding: '10px 18px',
      }}>
        <span style={{ color: '#fbbf24', fontSize: '11px', fontWeight: 700, letterSpacing: '0.05em' }}>CEX FLOW</span>
        <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 500 }}>{cexRoutes.length} route{cexRoutes.length !== 1 ? 's' : ''}</span>
        <span style={{ color: '#64748b', fontSize: '11px' }}>Exchange-to-exchange corridors</span>
        <button data-testid="cex-flow-close" onClick={onCloseCexFlow}
          style={{ background: 'rgba(148, 163, 184, 0.15)', border: 'none', borderRadius: '6px',
            color: '#94a3b8', cursor: 'pointer', padding: '4px 8px', fontSize: '11px', fontWeight: 600 }}>
          ESC
        </button>
      </div>
    );
  }

  // Intelligence Mode HUD
  if (graphMode && graphMode !== 'cex_flow' && !isCexFlowMode && !isRouteFocus) {
    const MC = { smart_money: '#22c55e', token_rotation: '#a78bfa', entity: '#38bdf8', risk: '#E5484D' };
    const c = MC[graphMode] || '#60a5fa';
    return (
      <div data-testid="intel-mode-hud" style={{
        position: 'absolute', bottom: '60px', left: '50%', transform: 'translateX(-50%)',
        zIndex: 20, display: 'flex', alignItems: 'center', gap: '12px',
        background: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(12px)',
        border: `1px solid ${c}4D`, borderRadius: '12px', padding: '10px 18px',
      }}>
        <span style={{ color: c, fontSize: '11px', fontWeight: 700, letterSpacing: '0.05em' }}>{(MODE_LABELS[graphMode] || graphMode).toUpperCase()}</span>
        <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 500 }}>{activeIntelligence.length} signal{activeIntelligence.length !== 1 ? 's' : ''}</span>
        <button data-testid="intel-mode-close" onClick={onCloseIntelMode}
          style={{ background: 'rgba(148, 163, 184, 0.15)', border: 'none', borderRadius: '6px',
            color: '#94a3b8', cursor: 'pointer', padding: '4px 8px', fontSize: '11px', fontWeight: 600 }}>
          ESC
        </button>
      </div>
    );
  }

  return null;
});

ModeHUD.displayName = 'ModeHUD';

export default ModeHUD;
