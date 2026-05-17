import React from 'react';
import { Trophy, Clock } from 'lucide-react';
import ActiveCorridorsPanel from '../../ActiveCorridorsPanel';
import LiquidityMapPanel from '../../LiquidityMapPanel';

const GRAPH_MODES = [
  { id: null,             label: 'All',            icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
  { id: 'smart_money',    label: 'Smart Money',    icon: 'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6' },
  { id: 'cex_flow',       label: 'CEX Flow',       icon: 'M3 12h4l3-9 4 18 3-9h4' },
  { id: 'token_rotation', label: 'Token Rot.',     icon: 'M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2' },
  { id: 'entity',         label: 'Entity',         icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75' },
  { id: 'risk',           label: 'Risk',           icon: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01' },
];

const TB = {
  height: '28px', padding: '0 10px', borderRadius: '6px', border: 'none',
  cursor: 'pointer', fontSize: '11px', fontWeight: 600, display: 'flex',
  alignItems: 'center', gap: '5px', whiteSpace: 'nowrap',
  transition: 'background-color 0.15s ease', backgroundColor: 'transparent', color: '#e2e8f0',
};

const GraphToolbar = React.memo(({
  graphMode, onModeChange,
  activeToolPanel, setActiveToolPanel,
  showLeaderboard, setShowLeaderboard,
  showPlayback, setShowPlayback,
  filteredGraphEdgesCount, selectedEntityId,
  onCorridorClick, onRouteClick,
  onPlaybackToggle,
}) => {
  return (
    <div data-testid="graph-toolbar" style={{
      position: 'absolute', top: '12px', left: '12px', zIndex: 10,
      display: 'flex', flexDirection: 'column', gap: '4px',
      padding: '5px 6px',
      backgroundColor: 'rgba(10, 14, 26, 0.88)',
      borderRadius: '8px',
      border: '1px solid rgba(148, 163, 184, 0.08)',
      backdropFilter: 'blur(12px)',
    }}>
      {/* Row 1 — Graph Modes */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '3px', flexWrap: 'wrap' }}>
        {GRAPH_MODES.map(mode => {
          const isActive = graphMode === mode.id;
          return (
            <button key={mode.id || 'all'} data-testid={`graph-mode-${mode.id || 'all'}`}
              onClick={() => onModeChange(mode.id)}
              style={{ ...TB, ...(isActive ? { backgroundColor: 'rgba(139, 92, 246, 0.2)', color: '#a78bfa' } : {}) }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={mode.icon} />
              </svg>
              {mode.label}
            </button>
          );
        })}
      </div>
      {/* Row 2 — Tools */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '3px', flexWrap: 'wrap' }}>
        <ActiveCorridorsPanel onCorridorClick={onCorridorClick} inline
          isOpen={activeToolPanel === 'corridors'}
          onToggle={(open) => setActiveToolPanel(open ? 'corridors' : null)}
          style={{ height: '28px', padding: '0 10px', borderRadius: '6px', border: 'none', color: '#e2e8f0' }} />
        <LiquidityMapPanel inline
          isOpen={activeToolPanel === 'liquidity'}
          onToggle={(open) => setActiveToolPanel(open ? 'liquidity' : null)}
          edgesShown={filteredGraphEdgesCount}
          entityId={selectedEntityId}
          onRouteClick={onRouteClick}
          style={{ height: '28px', padding: '0 10px', borderRadius: '6px', border: 'none', color: '#e2e8f0' }} />
        <button data-testid="graph-leaderboard-btn"
          onClick={() => setShowLeaderboard(!showLeaderboard)}
          style={{ ...TB, ...(showLeaderboard ? { backgroundColor: 'rgba(245, 158, 11, 0.25)', color: '#fbbf24' } : {}) }}>
          <Trophy size={12} />
          Leaderboard
        </button>
        <button data-testid="graph-playback-btn"
          onClick={onPlaybackToggle}
          style={{ ...TB, ...(showPlayback ? { backgroundColor: 'rgba(59, 130, 246, 0.25)', color: '#60a5fa' } : {}) }}>
          <Clock size={12} />
          Playback
        </button>
      </div>
    </div>
  );
});

GraphToolbar.displayName = 'GraphToolbar';

export default GraphToolbar;
