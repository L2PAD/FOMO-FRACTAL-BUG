/**
 * MTF Header Panel
 * ================
 * 
 * Multi-Timeframe Context Display.
 * 
 * Shows:
 * - HTF (bias layer)
 * - MTF (setup layer)
 * - LTF (entry layer)
 * - Alignment status
 * - Tradeability score
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// STYLED COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Container = styled.div`
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.1);
  padding: 16px;
  margin-bottom: 16px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const Title = styled.div`
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const AlignmentBadge = styled.span`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  
  ${({ $alignment }) => {
    if ($alignment === 'aligned') return 'background: rgba(34, 197, 94, 0.15); color: #4ade80;';
    if ($alignment === 'counter_trend') return 'background: rgba(239, 68, 68, 0.15); color: #f87171;';
    return 'background: rgba(251, 191, 36, 0.15); color: #fbbf24;';
  }}
`;

const TimeframeGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
`;

const TimeframeCard = styled.div`
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid ${({ $active }) => $active ? 'rgba(99, 102, 241, 0.4)' : 'rgba(148, 163, 184, 0.1)'};
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: rgba(99, 102, 241, 0.6);
  }
`;

const TFLabel = styled.div`
  font-size: 10px;
  color: #64748b;
  margin-bottom: 4px;
  text-transform: uppercase;
`;

const TFName = styled.div`
  font-size: 16px;
  font-weight: 700;
  color: #e2e8f0;
  margin-bottom: 4px;
`;

const BiasRow = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
`;

const BiasIcon = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  
  ${({ $bias }) => {
    if ($bias === 'bullish') return 'background: rgba(34, 197, 94, 0.2); color: #22c55e;';
    if ($bias === 'bearish') return 'background: rgba(239, 68, 68, 0.2); color: #ef4444;';
    return 'background: rgba(100, 116, 139, 0.2); color: #64748b;';
  }}
`;

const BiasText = styled.span`
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  
  ${({ $bias }) => {
    if ($bias === 'bullish') return 'color: #4ade80;';
    if ($bias === 'bearish') return 'color: #f87171;';
    return 'color: #94a3b8;';
  }}
`;

const PatternInfo = styled.div`
  font-size: 10px;
  color: #64748b;
  margin-top: 4px;
`;

const BottomRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
`;

const Summary = styled.div`
  font-size: 11px;
  color: #94a3b8;
  flex: 1;
`;

const TradeabilityBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  
  ${({ $level }) => {
    if ($level === 'high') return 'background: rgba(34, 197, 94, 0.15); color: #4ade80;';
    if ($level === 'medium') return 'background: rgba(251, 191, 36, 0.15); color: #fbbf24;';
    return 'background: rgba(239, 68, 68, 0.15); color: #f87171;';
  }}
`;

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

const MTFHeaderPanel = ({ mtfOrchestration, currentTF, onTimeframeClick }) => {
  if (!mtfOrchestration) {
    return null;
  }

  const {
    global_bias,
    alignment,
    tradeability,
    summary,
    timeframes = {},
    bias_tf,
    setup_tf,
    entry_tf,
  } = mtfOrchestration;

  const renderBiasIcon = (bias) => {
    if (bias === 'bullish') return <TrendingUp size={12} />;
    if (bias === 'bearish') return <TrendingDown size={12} />;
    return <Minus size={12} />;
  };

  const tfConfig = [
    { key: bias_tf, label: 'HTF BIAS', role: 'bias' },
    { key: setup_tf, label: 'SETUP', role: 'setup' },
    { key: entry_tf, label: 'ENTRY', role: 'entry' },
  ];

  return (
    <Container data-testid="mtf-header-panel">
      <Header>
        <Title>Market Context</Title>
        <AlignmentBadge $alignment={alignment}>
          {alignment === 'aligned' && <CheckCircle size={12} />}
          {alignment === 'counter_trend' && <AlertTriangle size={12} />}
          {alignment?.replace('_', ' ')}
        </AlignmentBadge>
      </Header>

      <TimeframeGrid>
        {tfConfig.map(({ key, label, role }) => {
          const tfData = timeframes[key] || {};
          const bias = tfData.bias || 'neutral';
          const pattern = tfData.pattern;
          
          return (
            <TimeframeCard
              key={role}
              $active={currentTF === key}
              onClick={() => onTimeframeClick?.(key)}
              data-testid={`tf-card-${role}`}
            >
              <TFLabel>{label}</TFLabel>
              <TFName>{key}</TFName>
              <BiasRow>
                <BiasIcon $bias={bias}>
                  {renderBiasIcon(bias)}
                </BiasIcon>
                <BiasText $bias={bias}>{bias}</BiasText>
              </BiasRow>
              {pattern?.type && (
                <PatternInfo>{pattern.type.replace(/_/g, ' ')}</PatternInfo>
              )}
            </TimeframeCard>
          );
        })}
      </TimeframeGrid>

      <BottomRow>
        <Summary>{summary}</Summary>
        <TradeabilityBadge $level={tradeability} data-testid="tradeability-badge">
          Tradeability: {tradeability?.toUpperCase()}
        </TradeabilityBadge>
      </BottomRow>
    </Container>
  );
};

export default MTFHeaderPanel;
