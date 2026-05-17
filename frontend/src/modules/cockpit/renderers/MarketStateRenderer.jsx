/**
 * MarketStateRenderer
 * ===================
 * 
 * Renders Layer A: Market State as CONTEXT badge.
 * NOT a pattern - this is background context.
 * 
 * Shows: trend, channel, volatility, momentum, wyckoff
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react';

const StateContainer = styled.div`
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 5;
`;

const StateBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  backdrop-filter: blur(4px);
  
  background: ${({ $type }) => {
    switch ($type) {
      case 'uptrend': return 'rgba(5, 165, 132, 0.85)';
      case 'downtrend': return 'rgba(239, 68, 68, 0.85)';
      case 'sideways': return 'rgba(100, 116, 139, 0.85)';
      case 'high': return 'rgba(245, 158, 11, 0.85)';
      case 'compression': return 'rgba(139, 92, 246, 0.85)';
      default: return 'rgba(15, 23, 42, 0.85)';
    }
  }};
  color: #fff;
  
  svg { width: 12px; height: 12px; }
`;

const TrendIcon = ({ trend }) => {
  if (trend === 'uptrend') return <TrendingUp />;
  if (trend === 'downtrend') return <TrendingDown />;
  return <Activity />;
};

export const MarketStateRenderer = ({ marketState }) => {
  if (!marketState) return null;

  const {
    trend_direction,
    trend_strength,
    volatility_regime,
    momentum_regime,
    wyckoff_phase,
  } = marketState;

  // Hide if no valid trend data (avoids "UNKNOWN" badge)
  const hasValidTrend = trend_direction && 
    trend_direction !== 'unknown' && 
    trend_direction !== 'neutral';

  return (
    <StateContainer data-testid="market-state-renderer">
      {/* Trend - only if valid */}
      {hasValidTrend && (
        <StateBadge $type={trend_direction}>
          <TrendIcon trend={trend_direction} />
          <span>{trend_direction?.replace('_', ' ').toUpperCase()}</span>
          {trend_strength && trend_strength !== 'no_trend' && (
            <span style={{ opacity: 0.7 }}>({trend_strength})</span>
          )}
        </StateBadge>
      )}
      
      {/* Volatility */}
      {volatility_regime && volatility_regime !== 'normal_volatility' && (
        <StateBadge $type={volatility_regime.includes('high') ? 'high' : volatility_regime.includes('compression') ? 'compression' : 'default'}>
          <Zap />
          <span>{volatility_regime.replace('_', ' ')}</span>
        </StateBadge>
      )}
      
      {/* Wyckoff Phase */}
      {wyckoff_phase && wyckoff_phase !== 'unknown' && (
        <StateBadge $type="default" style={{ background: 'rgba(59, 130, 246, 0.85)' }}>
          <span>{wyckoff_phase.toUpperCase()}</span>
        </StateBadge>
      )}
    </StateContainer>
  );
};

export default MarketStateRenderer;
