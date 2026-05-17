import React from 'react';

const GRAPH_MODES = [
  { id: null,             label: 'All',            icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
  { id: 'smart_money',    label: 'Smart Money',    icon: 'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6' },
  { id: 'cex_flow',       label: 'CEX Flow',       icon: 'M3 12h4l3-9 4 18 3-9h4' },
  { id: 'token_rotation', label: 'Token Rotation', icon: 'M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2' },
  { id: 'entity',         label: 'Entity',         icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75' },
  { id: 'risk',           label: 'Risk',           icon: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01' },
];

const GraphModeSelector = ({ activeMode, onModeChange }) => {
  return (
    <div
      data-testid="graph-mode-selector"
      style={{
        display: 'flex',
        gap: '4px',
        padding: '4px',
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        borderRadius: '10px',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        backdropFilter: 'blur(10px)',
      }}
    >
      {GRAPH_MODES.map((mode) => {
        const isActive = activeMode === mode.id;
        return (
          <button
            key={mode.id || 'all'}
            data-testid={`graph-mode-${mode.id || 'all'}`}
            onClick={() => onModeChange(mode.id)}
            title={mode.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 10px',
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '0.3px',
              transition: 'all 0.15s ease',
              backgroundColor: isActive ? 'rgba(139, 92, 246, 0.25)' : 'transparent',
              color: isActive ? '#a78bfa' : '#64748b',
              outline: isActive ? '1px solid rgba(139, 92, 246, 0.4)' : '1px solid transparent',
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d={mode.icon} />
            </svg>
            <span>{mode.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default GraphModeSelector;
