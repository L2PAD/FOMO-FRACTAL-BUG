/**
 * ExecutionRenderer Component
 * ============================
 * Renders execution state OVERLAY on chart.
 * 
 * IMPORTANT: This component is an OVERLAY - it should NOT block chart rendering.
 * Chart renders independently with candles. Execution is optional overlay layer.
 * 
 * 3 States:
 * - VALID: E1/E2/E3 entries, STOP line, TP1/TP2/TP3 targets
 * - WAITING: Entry zone exists but price not in position  
 * - NO_TRADE/LOADING: Small badge only (NO blocking overlay)
 * 
 * FIX: Removed blocking overlay for null/no_data states.
 * Chart always renders. Execution overlay is secondary.
 */

import React from 'react';
import styled from 'styled-components';

// ============================================
// STYLED COMPONENTS
// ============================================

const StatusOverlay = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 100;
  padding: 16px 24px;
  border-radius: 12px;
  background: ${({ $status }) => 
    $status === 'no_trade' ? 'rgba(100, 116, 139, 0.9)' :
    $status === 'waiting' ? 'rgba(245, 158, 11, 0.9)' :
    'transparent'
  };
  backdrop-filter: blur(4px);
`;

const StatusTitle = styled.div`
  font-size: 18px;
  font-weight: 800;
  color: ${({ $status }) => 
    $status === 'no_trade' ? '#e2e8f0' :
    $status === 'waiting' ? '#1f2937' :
    '#ffffff'
  };
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
`;

const StatusSubtitle = styled.div`
  font-size: 12px;
  font-weight: 500;
  color: ${({ $status }) => 
    $status === 'no_trade' ? '#94a3b8' :
    $status === 'waiting' ? '#374151' :
    '#94a3b8'
  };
  text-align: center;
  max-width: 200px;
`;

const ExecutionBadge = styled.div`
  position: absolute;
  top: 12px;
  right: 220px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: ${({ $status }) => 
    $status === 'valid' ? 'rgba(34, 197, 94, 0.95)' :
    $status === 'waiting' ? 'rgba(245, 158, 11, 0.95)' :
    $status === 'loading' ? 'rgba(59, 130, 246, 0.85)' :
    'rgba(100, 116, 139, 0.85)'
  };
  color: ${({ $status }) => 
    $status === 'valid' ? '#ffffff' :
    $status === 'waiting' ? '#1f2937' :
    '#ffffff'
  };
  border-radius: 8px;
  font-weight: 700;
  font-size: 12px;
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  z-index: 100;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const ExecutionCard = styled.div`
  position: absolute;
  bottom: 60px;
  right: 12px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid ${({ $direction }) => 
    $direction === 'long' ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'
  };
  border-radius: 10px;
  padding: 12px 16px;
  min-width: 160px;
  max-width: 200px;
  backdrop-filter: blur(8px);
  z-index: 100;
  
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    
    .direction {
      font-size: 13px;
      font-weight: 800;
      color: ${({ $direction }) => 
        $direction === 'long' ? '#22c55e' : '#ef4444'
      };
      text-transform: uppercase;
    }
    
    .rr {
      margin-left: auto;
      font-size: 12px;
      font-weight: 700;
      color: #f59e0b;
    }
  }
  
  .levels {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .level-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    
    .label {
      color: #94a3b8;
      font-weight: 600;
    }
    
    .value {
      font-weight: 700;
      font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
      
      &.entry { color: #fbbf24; }
      &.stop { color: #ef4444; }
      &.target { color: #22c55e; }
    }
  }
`;

// ============================================
// HELPER FUNCTIONS
// ============================================

const formatPrice = (price) => {
  if (!price) return '-';
  return price.toLocaleString(undefined, { 
    minimumFractionDigits: 2, 
    maximumFractionDigits: 2 
  });
};

const getStatusIcon = (status) => {
  if (status === 'valid') return '✓';
  if (status === 'waiting') return '◔';
  return '✗';
};

// ============================================
// COMPONENT
// ============================================

/**
 * ChartState type for proper state separation:
 * - 'loading' - Data is being fetched
 * - 'no_data' - No candles/market data available  
 * - 'ready' - Chart has data, execution overlay can render
 */

const ExecutionRenderer = ({ execution, showOverlay = true, chartState = 'ready' }) => {
  // ========================================
  // STATE 1: LOADING - Badge only, NO overlay
  // Chart component handles loading state independently
  // ========================================
  if (chartState === 'loading') {
    return (
      <ExecutionBadge $status="loading" data-testid="execution-badge">
        ◔ LOADING
      </ExecutionBadge>
    );
  }

  // ========================================
  // STATE 2: NO EXECUTION DATA - Hide badge, let chart render
  // FIX: Removed "ANALYZING" badge - it's confusing
  // ========================================
  if (!execution) {
    return null;  // Don't show anything - chart renders independently
  }

  const status = execution.status || (execution.valid ? 'valid' : 'no_trade');
  const reason = execution.reason || 'No valid setup found';

  // ========================================
  // STATE 3: NO TRADE - Now handled by unified NoTradeIndicator
  // DO NOT render anything here - avoids duplicate badges
  // ========================================
  if (status === 'no_trade') {
    return null;
  }

  // ========================================
  // WAITING STATE
  // ========================================
  if (status === 'waiting') {
    const direction = execution.direction || 'long';
    const entryPlan = execution.entry_plan || {};
    const stopPlan = execution.stop_plan || {};
    const targets = execution.targets || [];
    
    return (
      <>
        <ExecutionBadge $status="waiting" data-testid="execution-badge">
          {getStatusIcon('waiting')} WAITING
        </ExecutionBadge>
        {showOverlay && (
          <StatusOverlay $status="waiting" data-testid="execution-overlay">
            <StatusTitle $status="waiting">WAITING</StatusTitle>
            <StatusSubtitle $status="waiting">{reason}</StatusSubtitle>
          </StatusOverlay>
        )}
        {/* Still show card with levels */}
        <ExecutionCard $direction={direction} data-testid="execution-card">
          <div className="header">
            <span className="direction">{direction}</span>
            {execution.rr && <span className="rr">R:R {execution.rr}</span>}
          </div>
          <div className="levels">
            {entryPlan.levels?.map((price, i) => (
              <div className="level-row" key={`e${i}`}>
                <span className="label">E{i + 1}</span>
                <span className="value entry">${formatPrice(price)}</span>
              </div>
            ))}
            {stopPlan.price && (
              <div className="level-row">
                <span className="label">STOP</span>
                <span className="value stop">${formatPrice(stopPlan.price)}</span>
              </div>
            )}
            {targets.map((t, i) => (
              <div className="level-row" key={`tp${i}`}>
                <span className="label">TP{i + 1}</span>
                <span className="value target">${formatPrice(t.price)}</span>
              </div>
            ))}
          </div>
        </ExecutionCard>
      </>
    );
  }

  // ========================================
  // VALID STATE - Full execution display
  // ========================================
  const direction = execution.direction || 'long';
  const entryPlan = execution.entry_plan || {};
  const stopPlan = execution.stop_plan || {};
  const targets = execution.targets || [];
  
  // Extract entry levels
  const entryLevels = entryPlan.levels || [];
  const entryZone = entryPlan.zone || [];
  const stopPrice = stopPlan.price;

  return (
    <>
      <ExecutionBadge $status="valid" data-testid="execution-badge">
        {getStatusIcon('valid')} {direction.toUpperCase()}
      </ExecutionBadge>
      
      <ExecutionCard $direction={direction} data-testid="execution-card">
        <div className="header">
          <span className="direction">{direction}</span>
          {execution.rr && <span className="rr">R:R {execution.rr}</span>}
        </div>
        <div className="levels">
          {/* Entry Zone */}
          {entryZone.length === 2 && (
            <div className="level-row">
              <span className="label">ENTRY</span>
              <span className="value entry">
                ${formatPrice(entryZone[0])} - ${formatPrice(entryZone[1])}
              </span>
            </div>
          )}
          
          {/* Individual Entry Levels */}
          {entryLevels.map((price, i) => (
            <div className="level-row" key={`e${i}`}>
              <span className="label">E{i + 1}</span>
              <span className="value entry">${formatPrice(price)}</span>
            </div>
          ))}
          
          {/* Stop */}
          {stopPrice && (
            <div className="level-row">
              <span className="label">STOP</span>
              <span className="value stop">${formatPrice(stopPrice)}</span>
            </div>
          )}
          
          {/* Targets */}
          {targets.slice(0, 3).map((t, i) => (
            <div className="level-row" key={`tp${i}`}>
              <span className="label">TP{i + 1}</span>
              <span className="value target">${formatPrice(t.price)}</span>
            </div>
          ))}
        </div>
      </ExecutionCard>
    </>
  );
};

export default ExecutionRenderer;
