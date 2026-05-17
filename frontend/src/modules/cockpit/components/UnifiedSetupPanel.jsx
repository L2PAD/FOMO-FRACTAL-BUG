/**
 * UnifiedSetupPanel — Validation Chain Display
 * =============================================
 * 
 * Shows:
 * - Direction (LONG/SHORT/NO TRADE)
 * - Narrative (validation chain)
 * - Conflicts
 * - Entry context
 * 
 * If valid → shows clear action
 * If not valid → shows reason why
 */

import React from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, TrendingDown, AlertTriangle, 
  CheckCircle, XCircle, ChevronRight, Target,
  AlertOctagon, Minus
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// STYLED COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Container = styled.div`
  background: #0f172a;
  border-radius: 10px;
  border: 1px solid ${({ $valid }) => $valid ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.2)'};
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: ${({ $valid, $direction }) => {
    if (!$valid) return 'rgba(100, 116, 139, 0.1)';
    if ($direction === 'long') return 'rgba(34, 197, 94, 0.15)';
    return 'rgba(239, 68, 68, 0.15)';
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
  width: 28px;
  height: 28px;
  border-radius: 6px;
  
  ${({ $direction }) => {
    if ($direction === 'long') return 'background: rgba(34, 197, 94, 0.2);';
    if ($direction === 'short') return 'background: rgba(239, 68, 68, 0.2);';
    return 'background: rgba(100, 116, 139, 0.2);';
  }}
`;

const ValidityBadge = styled.span`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  
  ${({ $valid }) => $valid 
    ? 'background: rgba(34, 197, 94, 0.2); color: #4ade80;'
    : 'background: rgba(100, 116, 139, 0.2); color: #94a3b8;'
  }
`;

const Content = styled.div`
  padding: 16px;
`;

const NarrativeBox = styled.div`
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
  border-left: 3px solid ${({ $direction }) => {
    if ($direction === 'long') return '#22c55e';
    if ($direction === 'short') return '#ef4444';
    return '#64748b';
  }};
`;

const NarrativeText = styled.div`
  font-size: 12px;
  line-height: 1.5;
  color: #e2e8f0;
`;

const SectionTitle = styled.div`
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
`;

const ChainContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
`;

const ChainItem = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 4px;
  font-size: 11px;
  color: #86efac;
`;

const ChainArrow = styled.span`
  color: #475569;
  font-size: 12px;
`;

const ConflictsContainer = styled.div`
  margin-bottom: 16px;
`;

const ConflictItem = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 4px;
  font-size: 11px;
  color: #fca5a5;
  margin-bottom: 4px;
  
  svg {
    width: 12px;
    height: 12px;
    color: #f87171;
  }
`;

const EntryContextBox = styled.div`
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  padding: 12px;
`;

const EntryRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 11px;
  
  &:not(:last-child) {
    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  }
`;

const EntryLabel = styled.span`
  color: #94a3b8;
`;

const EntryValue = styled.span`
  font-weight: 600;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  color: #e2e8f0;
`;

const NoSetupMessage = styled.div`
  text-align: center;
  padding: 20px;
  color: #64748b;
  font-size: 12px;
`;

const ReasonBox = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(100, 116, 139, 0.1);
  border-radius: 6px;
  font-size: 12px;
  color: #94a3b8;
  
  svg {
    color: #64748b;
  }
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

const UnifiedSetupPanel = ({ setup }) => {
  const unifiedSetup = setup;
  if (!unifiedSetup) {
    return (
      <Container $valid={false} data-testid="unified-setup-panel">
        <Header $valid={false}>
          <DirectionBadge $direction="no_trade">
            <DirectionIcon $direction="no_trade">
              <Minus size={14} />
            </DirectionIcon>
            UNIFIED SETUP
          </DirectionBadge>
        </Header>
        <NoSetupMessage>No setup available</NoSetupMessage>
      </Container>
    );
  }

  const {
    valid,
    direction,
    narrative,
    chain = [],
    conflicts = [],
    entry_context,
  } = unifiedSetup;

  const isLong = direction === 'long';
  const isShort = direction === 'short';
  const isNoTrade = direction === 'no_trade' || !valid;
  
  // NO TRADE is now handled by unified NoTradeIndicator
  // Show message if no valid setup
  if (isNoTrade) {
    return (
      <Container $valid={false} data-testid="unified-setup-panel">
        <Header $valid={false} $direction="no_trade">
          <DirectionBadge $direction="no_trade">
            <DirectionIcon $direction="no_trade">
              <Minus size={14} />
            </DirectionIcon>
            NO TRADE
          </DirectionBadge>
          <ValidityBadge $valid={false}>
            <XCircle size={10} />
            Not Valid
          </ValidityBadge>
        </Header>
        <Content>
          <NarrativeBox $direction="no_trade">
            <span style={{ color: '#94a3b8', fontSize: '12px' }}>
              {narrative || 'Waiting for a valid setup...'}
            </span>
          </NarrativeBox>
        </Content>
      </Container>
    );
  }

  return (
    <Container $valid={valid} data-testid="unified-setup-panel">
      <Header $valid={valid} $direction={direction}>
        <DirectionBadge $direction={direction}>
          <DirectionIcon $direction={direction}>
            {isLong && <TrendingUp size={16} />}
            {isShort && <TrendingDown size={16} />}
          </DirectionIcon>
          {isLong && 'LONG SETUP'}
          {isShort && 'SHORT SETUP'}
        </DirectionBadge>
        <ValidityBadge $valid={valid}>
          {valid ? <CheckCircle size={12} /> : <XCircle size={12} />}
          {valid ? 'VALID' : 'INVALID'}
        </ValidityBadge>
      </Header>

      <Content>
        {/* Narrative */}
        <NarrativeBox $direction={direction} data-testid="setup-narrative">
          <NarrativeText>{narrative}</NarrativeText>
        </NarrativeBox>

        {/* Validation Chain */}
        {chain.length > 0 && (
          <>
            <SectionTitle>Validation Chain</SectionTitle>
            <ChainContainer data-testid="validation-chain">
              {chain.map((item, i) => (
                <React.Fragment key={i}>
                  <ChainItem>
                    <CheckCircle size={10} />
                    {item}
                  </ChainItem>
                  {i < chain.length - 1 && <ChainArrow>→</ChainArrow>}
                </React.Fragment>
              ))}
            </ChainContainer>
          </>
        )}

        {/* Conflicts */}
        {conflicts.length > 0 && (
          <ConflictsContainer>
            <SectionTitle>Conflicts ({conflicts.length})</SectionTitle>
            {conflicts.map((conflict, i) => (
              <ConflictItem key={i}>
                <AlertTriangle />
                {conflict}
              </ConflictItem>
            ))}
          </ConflictsContainer>
        )}

        {/* Entry Context */}
        {valid && entry_context && (
          <>
            <SectionTitle>Entry Context</SectionTitle>
            <EntryContextBox data-testid="entry-context">
              <EntryRow>
                <EntryLabel>Model:</EntryLabel>
                <EntryValue>{entry_context.model?.replace(/_/g, ' ')}</EntryValue>
              </EntryRow>
              
              {entry_context.preferred_zone && (
                <EntryRow>
                  <EntryLabel>Zone:</EntryLabel>
                  <EntryValue>
                    {entry_context.preferred_zone.type} 
                    @ {formatPrice(entry_context.preferred_zone.lower)} - {formatPrice(entry_context.preferred_zone.upper)}
                  </EntryValue>
                </EntryRow>
              )}
              
              {entry_context.fib_support && (
                <EntryRow>
                  <EntryLabel>Fib Support:</EntryLabel>
                  <EntryValue>
                    {entry_context.fib_support.level} @ {formatPrice(entry_context.fib_support.price)}
                  </EntryValue>
                </EntryRow>
              )}
              
              {entry_context.pattern_levels && (
                <>
                  <EntryRow>
                    <EntryLabel>Entry Zone:</EntryLabel>
                    <EntryValue style={{ color: '#4ade80' }}>
                      {formatPrice(entry_context.pattern_levels.entry_zone?.[0])} - {formatPrice(entry_context.pattern_levels.entry_zone?.[1])}
                    </EntryValue>
                  </EntryRow>
                  <EntryRow>
                    <EntryLabel>Stop:</EntryLabel>
                    <EntryValue style={{ color: '#f87171' }}>
                      {formatPrice(entry_context.pattern_levels.stop)}
                    </EntryValue>
                  </EntryRow>
                  <EntryRow>
                    <EntryLabel>TP1:</EntryLabel>
                    <EntryValue style={{ color: '#4ade80' }}>
                      {formatPrice(entry_context.pattern_levels.tp1)}
                    </EntryValue>
                  </EntryRow>
                </>
              )}
            </EntryContextBox>
          </>
        )}
      </Content>
    </Container>
  );
};

export default UnifiedSetupPanel;
