/**
 * RenderPlanReasons — Why is this on the chart?
 * ==============================================
 * Plain text only. No borders, no backgrounds, no colors.
 * Compact inline display.
 */

import React from 'react';
import styled from 'styled-components';

const Container = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 8px;
  font-size: 11px;
  color: #64748b;
`;

const Label = styled.span`
  font-weight: 600;
  color: #94a3b8;
  margin-right: 2px;
`;

const ReasonText = styled.span`
  font-weight: 500;
  color: #64748b;
`;

const Separator = styled.span`
  color: #cbd5e1;
  margin: 0 2px;
`;

const KEY_LABELS = {
  ema_20: 'EMA20', ema_50: 'EMA50', ema_200: 'EMA200',
  bollinger_bands: 'BB', vwap: 'VWAP',
  rsi: 'RSI', macd: 'MACD', stochastic: 'Stoch', adx: 'ADX', volume: 'Vol',
  fib: 'Fib', poi: 'POI', liquidity: 'Liq',
  choch: 'CHOCH', displacement: 'Disp',
  mtf: 'MTF', structure: 'Struct',
};

const RenderPlanReasons = ({ renderPlan }) => {
  if (!renderPlan?.reason_map) return null;

  const reasons = Object.entries(renderPlan.reason_map);
  if (reasons.length === 0) return null;

  return (
    <Container data-testid="render-plan-reasons">
      <Label>Why:</Label>
      {reasons.map(([key], i) => (
        <ReasonText key={key} data-testid={`reason-${key}`}>
          {i > 0 && <Separator>·</Separator>}
          {KEY_LABELS[key] || key}
        </ReasonText>
      ))}
    </Container>
  );
};

export default RenderPlanReasons;
