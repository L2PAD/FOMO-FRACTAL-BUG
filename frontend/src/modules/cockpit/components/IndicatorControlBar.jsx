/**
 * IndicatorControlBar — RSI/MACD as inline toggle controls
 * =========================================================
 * 
 * NOT analytics cards — TOGGLE SWITCHES for panes.
 * 
 * Design:
 * - Compact inline row (not cards)
 * - Click = toggle pane on/off
 * - Active = highlighted
 * - Inactive = neutral
 * - Short labels only
 */

import React from 'react';
import styled from 'styled-components';
import { Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const ControlBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
`;

const ControlPill = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: ${({ $active, $color }) => $active ? `${$color}12` : '#f8fafc'};
  border: 1.5px solid ${({ $active, $color }) => $active ? $color : '#e2e8f0'};
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: ${({ $color }) => $color || '#cbd5e1'};
    background: ${({ $color }) => `${$color}08`};
  }
`;

const IconWrap = styled.span`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  
  svg {
    width: 14px;
    height: 14px;
    color: ${({ $color }) => $color || '#64748b'};
  }
`;

const Label = styled.span`
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
`;

const Value = styled.span`
  font-size: 12px;
  font-weight: 700;
  color: ${({ $color }) => $color || '#64748b'};
`;

const Separator = styled.span`
  font-size: 10px;
  color: #cbd5e1;
  margin: 0 2px;
`;

const State = styled.span`
  font-size: 11px;
  font-weight: 500;
  color: ${({ $color }) => $color || '#64748b'};
`;

const ActiveDot = styled.span`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${({ $active, $color }) => $active ? $color : 'transparent'};
  margin-left: 4px;
`;

// ============================================
// INTERPRETATION HELPERS
// ============================================

const getRSIInterpretation = (value) => {
  const v = Math.round(value);
  
  if (v < 30) return { state: 'Oversold', color: '#16a34a' };
  if (v < 40) return { state: 'Near oversold', color: '#22c55e' };
  if (v < 60) return { state: 'Neutral', color: '#64748b' };
  if (v < 70) return { state: 'Bullish', color: '#f59e0b' };
  return { state: 'Overbought', color: '#ef4444' };
};

const getMACDInterpretation = (macdData) => {
  if (!macdData) return { state: 'No data', color: '#64748b' };
  
  const { zone, momentum } = macdData;
  
  if (zone === 'above_zero') {
    if (momentum === 'growing') return { state: 'Bullish', color: '#16a34a' };
    return { state: 'Bullish fading', color: '#86efac' };
  }
  
  if (momentum === 'growing') return { state: 'Bearish', color: '#ef4444' };
  return { state: 'Bearish fading', color: '#fca5a5' };
};

// ============================================
// MAIN COMPONENT
// ============================================

const IndicatorControlBar = ({ 
  insights, 
  activeIndicators = { rsi: false, macd: false },
  onToggle 
}) => {
  if (!insights) return null;

  const { rsi, macd } = insights;
  const rsiInterp = rsi ? getRSIInterpretation(rsi.value) : null;
  const macdInterp = macd ? getMACDInterpretation(macd) : null;

  return (
    <ControlBar data-testid="indicator-control-bar">
      {/* RSI Toggle */}
      {rsi && rsiInterp && (
        <ControlPill 
          $active={activeIndicators.rsi}
          $color={rsiInterp.color}
          onClick={() => onToggle?.('rsi')}
          data-testid="rsi-toggle"
        >
          <IconWrap $color={rsiInterp.color}>
            <Activity />
          </IconWrap>
          <Label>RSI</Label>
          <Value $color={rsiInterp.color}>{Math.round(rsi.value)}</Value>
          <Separator>·</Separator>
          <State $color={rsiInterp.color}>{rsiInterp.state}</State>
          <ActiveDot $active={activeIndicators.rsi} $color={rsiInterp.color} />
        </ControlPill>
      )}

      {/* MACD Toggle */}
      {macd && macdInterp && (
        <ControlPill 
          $active={activeIndicators.macd}
          $color={macdInterp.color}
          onClick={() => onToggle?.('macd')}
          data-testid="macd-toggle"
        >
          <IconWrap $color={macdInterp.color}>
            {macdInterp.state.includes('Bullish') ? <TrendingUp /> : 
             macdInterp.state.includes('Bearish') ? <TrendingDown /> : <Minus />}
          </IconWrap>
          <Label>MACD</Label>
          <Separator>·</Separator>
          <State $color={macdInterp.color}>{macdInterp.state}</State>
          <ActiveDot $active={activeIndicators.macd} $color={macdInterp.color} />
        </ControlPill>
      )}
    </ControlBar>
  );
};

export default IndicatorControlBar;
