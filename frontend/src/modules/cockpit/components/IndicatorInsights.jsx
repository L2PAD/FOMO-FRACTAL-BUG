/**
 * IndicatorInsights Component V3
 * ==============================
 * RSI + MACD cards — concise, product-quality.
 * Click = toggle pane visibility.
 * 
 * Design:
 * - Compact cards with short labels
 * - RSI 36 · Near oversold
 * - Subtle summary below
 * - No trading language
 */

import React from 'react';
import styled from 'styled-components';
import { Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  gap: 12px;
  padding: 8px 0;
`;

const Card = styled.button`
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: ${({ $active }) => $active ? '#f0f9ff' : '#ffffff'};
  border: 1px solid ${({ $active, $color }) => $active ? $color : '#e2e8f0'};
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: ${({ $color }) => $color || '#cbd5e1'};
    background: ${({ $color }) => $color ? `${$color}08` : '#f8fafc'};
  }
`;

const IconBox = styled.div`
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${({ $color }) => $color ? `${$color}15` : '#f1f5f9'};
  border-radius: 8px;
  
  svg {
    width: 18px;
    height: 18px;
    color: ${({ $color }) => $color || '#64748b'};
  }
`;

const Content = styled.div`
  flex: 1;
  min-width: 0;
`;

const MainLabel = styled.div`
  display: flex;
  align-items: baseline;
  gap: 6px;
  
  .name {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
  }
  
  .value {
    font-size: 13px;
    font-weight: 600;
    color: ${({ $color }) => $color || '#64748b'};
  }
  
  .separator {
    color: #cbd5e1;
    font-size: 11px;
  }
  
  .state {
    font-size: 11px;
    font-weight: 600;
    color: ${({ $stateColor }) => $stateColor || '#64748b'};
    text-transform: capitalize;
  }
`;

const Summary = styled.p`
  margin: 4px 0 0 0;
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const StatusDot = styled.span`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ $active, $color }) => $active ? ($color || '#3b82f6') : '#e2e8f0'};
  flex-shrink: 0;
`;

// ============================================
// HELPERS — Interpretation Engine
// ============================================

/**
 * RSI Interpretation — Market Stage (NOT direction)
 * - < 30: Oversold (potential reversal UP)
 * - 30-40: Near oversold (selling exhausting)
 * - 40-60: Neutral
 * - 60-70: Bullish (momentum up)
 * - > 70: Overbought (potential pullback)
 */
const interpretRSI = (value, state) => {
  const v = Math.round(value);
  
  if (v < 30) {
    return {
      label: `${v}`,
      state: 'Oversold',
      summary: 'Reversal watch zone',
      stateColor: '#16a34a',
      color: '#16a34a',
    };
  }
  if (v < 40) {
    return {
      label: `${v}`,
      state: 'Near oversold',
      summary: 'Selling pressure weakening',
      stateColor: '#22c55e',
      color: '#22c55e',
    };
  }
  if (v < 60) {
    return {
      label: `${v}`,
      state: 'Neutral',
      summary: 'No directional signal',
      stateColor: '#64748b',
      color: '#64748b',
    };
  }
  if (v < 70) {
    return {
      label: `${v}`,
      state: 'Bullish',
      summary: 'Upward momentum',
      stateColor: '#f59e0b',
      color: '#f59e0b',
    };
  }
  return {
    label: `${v}`,
    state: 'Overbought',
    summary: 'Pullback watch zone',
    stateColor: '#ef4444',
    color: '#ef4444',
  };
};

/**
 * MACD Interpretation — Momentum Regime
 * Zone (above/below zero) + Direction (growing/fading)
 */
const interpretMACD = (macdData) => {
  if (!macdData) {
    return {
      label: '',
      state: 'No data',
      summary: 'Insufficient data',
      stateColor: '#64748b',
      color: '#64748b',
    };
  }
  
  const { zone, momentum, state } = macdData;
  
  if (zone === 'above_zero') {
    if (momentum === 'growing') {
      return {
        label: '',
        state: 'Bullish',
        summary: 'Momentum building',
        stateColor: '#16a34a',
        color: '#16a34a',
      };
    }
    return {
      label: '',
      state: 'Bullish fading',
      summary: 'Momentum weakening',
      stateColor: '#86efac',
      color: '#86efac',
    };
  }
  
  // Below zero
  if (momentum === 'growing') {
    return {
      label: '',
      state: 'Bearish',
      summary: 'Downward pressure',
      stateColor: '#ef4444',
      color: '#ef4444',
    };
  }
  return {
    label: '',
    state: 'Bearish fading',
    summary: 'Selling pressure easing',
    stateColor: '#fca5a5',
    color: '#fca5a5',
  };
};

// ============================================
// MAIN COMPONENT
// ============================================

const IndicatorInsights = ({ 
  insights, 
  activeIndicators = { rsi: false, macd: false },
  onToggle 
}) => {
  if (!insights) return null;

  const { rsi, macd } = insights;
  
  // Interpret RSI
  const rsiInterp = rsi ? interpretRSI(rsi.value, rsi.state) : null;
  
  // Interpret MACD
  const macdInterp = macd ? interpretMACD(macd) : null;

  return (
    <Container data-testid="indicator-insights">
      {/* RSI Card */}
      {rsi && rsiInterp && (
        <Card 
          $active={activeIndicators.rsi}
          $color={rsiInterp.color}
          onClick={() => onToggle?.('rsi')}
          data-testid="rsi-card"
        >
          <IconBox $color={rsiInterp.color}>
            <Activity />
          </IconBox>
          <Content>
            <MainLabel $color={rsiInterp.color} $stateColor={rsiInterp.stateColor}>
              <span className="name">RSI</span>
              <span className="value">{rsiInterp.label}</span>
              <span className="separator">·</span>
              <span className="state">{rsiInterp.state}</span>
            </MainLabel>
            <Summary>{rsiInterp.summary}</Summary>
          </Content>
          <StatusDot $active={activeIndicators.rsi} $color={rsiInterp.color} />
        </Card>
      )}

      {/* MACD Card */}
      {macd && macdInterp && (
        <Card 
          $active={activeIndicators.macd}
          $color={macdInterp.color}
          onClick={() => onToggle?.('macd')}
          data-testid="macd-card"
        >
          <IconBox $color={macdInterp.color}>
            {macdInterp.state.includes('Bullish') ? (
              <TrendingUp />
            ) : macdInterp.state.includes('Bearish') ? (
              <TrendingDown />
            ) : (
              <Minus />
            )}
          </IconBox>
          <Content>
            <MainLabel $color={macdInterp.color} $stateColor={macdInterp.stateColor}>
              <span className="name">MACD</span>
              <span className="separator">·</span>
              <span className="state">{macdInterp.state}</span>
            </MainLabel>
            <Summary>{macdInterp.summary}</Summary>
          </Content>
          <StatusDot $active={activeIndicators.macd} $color={macdInterp.color} />
        </Card>
      )}
    </Container>
  );
};

export default IndicatorInsights;
