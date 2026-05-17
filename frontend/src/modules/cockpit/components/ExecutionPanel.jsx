/**
 * Execution Panel
 * ===============
 * 
 * Prop-trader level execution display.
 * 
 * Shows:
 * - Entry ladder (E1, E2, E3)
 * - Stop loss with reason
 * - Target levels (TP1, TP2, TP3)
 * - Position management rules
 * - Risk profile & size factor
 * - R:R ratio
 */

import React from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, TrendingDown, Target, AlertOctagon,
  ArrowDown, ArrowUp, Shield, Percent, Layers
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// STYLED COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Container = styled.div`
  background: #0f172a;
  border-radius: 12px;
  border: 1px solid ${({ $valid }) => $valid ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.2)'};
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: ${({ $valid, $direction }) => {
    if (!$valid) return 'rgba(100, 116, 139, 0.1)';
    if ($direction === 'long') return 'rgba(34, 197, 94, 0.12)';
    return 'rgba(239, 68, 68, 0.12)';
  }};
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
`;

const DirectionBadge = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  
  ${({ $direction }) => {
    if ($direction === 'long') return 'color: #22c55e;';
    if ($direction === 'short') return 'color: #ef4444;';
    return 'color: #64748b;';
  }}
`;

const DirectionIcon = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  
  ${({ $direction }) => {
    if ($direction === 'long') return 'background: rgba(34, 197, 94, 0.2);';
    if ($direction === 'short') return 'background: rgba(239, 68, 68, 0.2);';
    return 'background: rgba(100, 116, 139, 0.2);';
  }}
`;

const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const RiskBadge = styled.span`
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  
  ${({ $profile }) => {
    if ($profile === 'normal') return 'background: rgba(34, 197, 94, 0.2); color: #4ade80;';
    if ($profile === 'reduced') return 'background: rgba(251, 191, 36, 0.2); color: #fbbf24;';
    return 'background: rgba(239, 68, 68, 0.2); color: #f87171;';
  }}
`;

const RRBadge = styled.span`
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
`;

const Content = styled.div`
  padding: 16px;
`;

const Section = styled.div`
  margin-bottom: 16px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const SectionTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  
  svg {
    width: 12px;
    height: 12px;
  }
`;

const EntryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
`;

const EntryCard = styled.div`
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
`;

const EntryLabel = styled.div`
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
`;

const EntryPrice = styled.div`
  font-size: 13px;
  font-weight: 700;
  color: #3b82f6;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const EntrySize = styled.div`
  font-size: 10px;
  color: #94a3b8;
`;

const StopCard = styled.div`
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const StopInfo = styled.div``;

const StopPrice = styled.div`
  font-size: 14px;
  font-weight: 700;
  color: #ef4444;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const StopReason = styled.div`
  font-size: 10px;
  color: #94a3b8;
`;

const TargetsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
`;

const TargetCard = styled.div`
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
`;

const TargetLabel = styled.div`
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
`;

const TargetPrice = styled.div`
  font-size: 13px;
  font-weight: 700;
  color: #22c55e;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const TargetSize = styled.div`
  font-size: 10px;
  color: #94a3b8;
`;

const ManagementList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const ManagementItem = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 4px;
  font-size: 11px;
  color: #94a3b8;
  
  svg {
    width: 14px;
    height: 14px;
    color: #6366f1;
  }
`;

const InvalidMessage = styled.div`
  padding: 20px;
  text-align: center;
  color: #64748b;
`;

const InvalidReason = styled.div`
  font-size: 12px;
  margin-top: 8px;
  color: #94a3b8;
`;

const SizeFactorBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 6px;
`;

const SizeBarLabel = styled.span`
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
`;

const SizeBarTrack = styled.div`
  flex: 1;
  height: 6px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 3px;
  overflow: hidden;
`;

const SizeBarFill = styled.div`
  height: 100%;
  width: ${({ $factor }) => ($factor || 0) * 100}%;
  background: ${({ $factor }) => {
    if ($factor >= 0.8) return '#22c55e';
    if ($factor >= 0.5) return '#fbbf24';
    return '#ef4444';
  }};
  border-radius: 3px;
  transition: width 0.3s ease;
`;

const SizeBarValue = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: #e2e8f0;
  min-width: 40px;
  text-align: right;
`;

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

const formatPrice = (price) => {
  if (!price) return '—';
  if (price >= 10000) return `$${price.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  if (price >= 100) return `$${price.toLocaleString('en-US', { maximumFractionDigits: 1 })}`;
  return `$${price.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
};

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

const ExecutionPanel = ({ executionPlan }) => {
  if (!executionPlan) {
    return null;
  }

  const {
    valid,
    direction,
    model,
    risk_profile,
    size_factor,
    entry_plan,
    stop_plan,
    targets = [],
    management,
    rr,
    reason,
  } = executionPlan;

  const isLong = direction === 'long';
  const isShort = direction === 'short';

  if (!valid) {
    return (
      <Container $valid={false} data-testid="execution-panel">
        <Header $valid={false}>
          <DirectionBadge $direction="none">
            <DirectionIcon $direction="none">
              <AlertOctagon size={16} />
            </DirectionIcon>
            NO EXECUTION
          </DirectionBadge>
        </Header>
        <InvalidMessage>
          <AlertOctagon size={24} color="#64748b" />
          <InvalidReason>{reason || 'Execution plan not available'}</InvalidReason>
        </InvalidMessage>
      </Container>
    );
  }

  return (
    <Container $valid={valid} data-testid="execution-panel">
      <Header $valid={valid} $direction={direction}>
        <DirectionBadge $direction={direction}>
          <DirectionIcon $direction={direction}>
            {isLong && <TrendingUp size={16} />}
            {isShort && <TrendingDown size={16} />}
          </DirectionIcon>
          {isLong ? 'LONG' : 'SHORT'} EXECUTION
        </DirectionBadge>
        <HeaderRight>
          <RiskBadge $profile={risk_profile}>
            {risk_profile}
          </RiskBadge>
          {rr && (
            <RRBadge>R:R {rr}</RRBadge>
          )}
        </HeaderRight>
      </Header>

      <Content>
        {/* Entry Plan */}
        {entry_plan && (
          <Section>
            <SectionTitle>
              <Layers size={12} />
              Entry Ladder ({entry_plan.type})
            </SectionTitle>
            <EntryGrid>
              {entry_plan.entries?.map((entry, i) => (
                <EntryCard key={i}>
                  <EntryLabel>{entry.label || `E${i + 1}`}</EntryLabel>
                  <EntryPrice>{formatPrice(entry.price)}</EntryPrice>
                  <EntrySize>{entry.size_pct}%</EntrySize>
                </EntryCard>
              ))}
            </EntryGrid>
          </Section>
        )}

        {/* Stop Loss */}
        {stop_plan && (
          <Section>
            <SectionTitle>
              <Shield size={12} />
              Stop Loss
            </SectionTitle>
            <StopCard>
              <StopInfo>
                <StopPrice>{formatPrice(stop_plan.price)}</StopPrice>
                <StopReason>{stop_plan.reason}</StopReason>
              </StopInfo>
              <ArrowDown size={20} color="#ef4444" />
            </StopCard>
          </Section>
        )}

        {/* Targets */}
        {targets.length > 0 && (
          <Section>
            <SectionTitle>
              <Target size={12} />
              Targets
            </SectionTitle>
            <TargetsGrid>
              {targets.map((target, i) => (
                <TargetCard key={i}>
                  <TargetLabel>{target.name}</TargetLabel>
                  <TargetPrice>{formatPrice(target.price)}</TargetPrice>
                  <TargetSize>{target.size_pct}%</TargetSize>
                </TargetCard>
              ))}
            </TargetsGrid>
          </Section>
        )}

        {/* Position Management */}
        {management && (
          <Section>
            <SectionTitle>Management Rules</SectionTitle>
            <ManagementList>
              {management.move_stop_to_be_at && (
                <ManagementItem>
                  <Shield />
                  Move stop to breakeven at {management.move_stop_to_be_at}
                </ManagementItem>
              )}
              {management.trail_after && (
                <ManagementItem>
                  <ArrowUp />
                  Trail stop after {management.trail_after}
                </ManagementItem>
              )}
              {management.cancel_if && (
                <ManagementItem>
                  <AlertOctagon />
                  Cancel if: {management.cancel_if}
                </ManagementItem>
              )}
            </ManagementList>
          </Section>
        )}

        {/* Size Factor */}
        <SizeFactorBar>
          <SizeBarLabel>Position Size</SizeBarLabel>
          <SizeBarTrack>
            <SizeBarFill $factor={size_factor} />
          </SizeBarTrack>
          <SizeBarValue>{Math.round((size_factor || 0) * 100)}%</SizeBarValue>
        </SizeFactorBar>
      </Content>
    </Container>
  );
};

export default ExecutionPanel;
