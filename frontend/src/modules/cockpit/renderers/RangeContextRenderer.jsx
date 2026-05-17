/**
 * RangeContextRenderer
 * ====================
 * 
 * Renders range/channel context for range_mode.
 * 
 * NOT a pattern card. This is context visualization for range markets.
 * 
 * Shows:
 * - Range boundaries (high/low)
 * - Midline
 * - Breakout triggers
 * - Position in range
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const RangeContainer = styled.div`
  position: absolute;
  top: 60px;
  left: 12px;
  padding: 10px 14px;
  background: rgba(100, 116, 139, 0.9);
  border-radius: 8px;
  font-size: 11px;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  min-width: 150px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-weight: 700;
  font-size: 12px;
  
  svg { width: 14px; height: 14px; }
`;

const Row = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  font-size: 10px;
  
  &.high { color: #fca5a5; }
  &.low { color: #86efac; }
  &.mid { color: #94a3b8; }
`;

const Bias = styled.div`
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-align: center;
  background: ${({ $bias }) => {
    if ($bias === 'bullish') return 'rgba(5, 165, 132, 0.3)';
    if ($bias === 'bearish') return 'rgba(239, 68, 68, 0.3)';
    return 'rgba(100, 116, 139, 0.3)';
  }};
`;

const PositionBar = styled.div`
  margin-top: 8px;
  height: 4px;
  background: rgba(255,255,255,0.2);
  border-radius: 2px;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    left: ${({ $position }) => Math.min(100, Math.max(0, $position))}%;
    top: -2px;
    width: 8px;
    height: 8px;
    background: #fff;
    border-radius: 50%;
    transform: translateX(-50%);
  }
`;

export const RangeContextRenderer = ({ rangeContext, marketState }) => {
  if (!rangeContext) return null;

  const {
    range_high,
    range_low,
    midline,
    position_pct,
    bias,
    breakout_trigger_up,
    breakout_trigger_down,
  } = rangeContext;

  const BiasIcon = bias === 'bullish' ? TrendingUp : bias === 'bearish' ? TrendingDown : Minus;

  return (
    <RangeContainer data-testid="range-context-renderer">
      <Header>
        <BiasIcon />
        RANGE MARKET
      </Header>
      
      <Row className="high">
        <span>Resistance</span>
        <span>${range_high?.toFixed(2)}</span>
      </Row>
      
      <Row className="mid">
        <span>Midline</span>
        <span>${midline?.toFixed(2)}</span>
      </Row>
      
      <Row className="low">
        <span>Support</span>
        <span>${range_low?.toFixed(2)}</span>
      </Row>
      
      <PositionBar $position={position_pct} />
      
      <Bias $bias={bias}>
        Bias: {bias?.toUpperCase() || 'NEUTRAL'}
      </Bias>
      
      {breakout_trigger_up && (
        <Row style={{ marginTop: 8, opacity: 0.7 }}>
          <span>Break Up</span>
          <span>${breakout_trigger_up?.toFixed(2)}</span>
        </Row>
      )}
      
      {breakout_trigger_down && (
        <Row style={{ opacity: 0.7 }}>
          <span>Break Down</span>
          <span>${breakout_trigger_down?.toFixed(2)}</span>
        </Row>
      )}
    </RangeContainer>
  );
};

export default RangeContextRenderer;
