/**
 * ScenariosBlock — Trading Scenarios Display
 * ==========================================
 * 
 * Shows Primary and Alternative scenarios with:
 * - Title and direction
 * - Probability percentage
 * - Summary description
 * - Action implication
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Minus, AlertCircle, ArrowRight } from 'lucide-react';

const Container = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Title = styled.div`
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
`;

const ScenarioCard = styled.div`
  padding: 14px 16px;
  border-radius: 10px;
  background: ${props => {
    if (props.$type === 'primary') return 'linear-gradient(135deg, rgba(5, 165, 132, 0.08) 0%, rgba(5, 165, 132, 0.02) 100%)';
    if (props.$type === 'structure') return 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%)';
    return '#f8fafc';
  }};
  border: 1px solid ${props => {
    if (props.$type === 'primary') return 'rgba(5, 165, 132, 0.2)';
    if (props.$type === 'structure') return 'rgba(59, 130, 246, 0.2)';
    return '#e2e8f0';
  }};
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: ${props => {
      if (props.$type === 'primary') return '#05A584';
      if (props.$type === 'structure') return '#3b82f6';
      return '#cbd5e1';
    }};
    transform: translateY(-1px);
  }
`;

const ScenarioHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
`;

const ScenarioTitle = styled.div`
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const DirectionIcon = styled.span`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: ${props => {
    if (props.$direction === 'bullish') return 'rgba(5, 165, 132, 0.15)';
    if (props.$direction === 'bearish') return 'rgba(239, 68, 68, 0.15)';
    return 'rgba(100, 116, 139, 0.15)';
  }};
  color: ${props => {
    if (props.$direction === 'bullish') return '#05A584';
    if (props.$direction === 'bearish') return '#ef4444';
    return '#64748b';
  }};
`;

const Probability = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: ${props => {
    if (props.$value >= 0.6) return '#05A584';
    if (props.$value >= 0.4) return '#f59e0b';
    return '#94a3b8';
  }};
`;

const ProbabilityBar = styled.div`
  width: 40px;
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
`;

const ProbabilityFill = styled.div`
  height: 100%;
  width: ${props => props.$value * 100}%;
  background: ${props => {
    if (props.$value >= 0.6) return '#05A584';
    if (props.$value >= 0.4) return '#f59e0b';
    return '#94a3b8';
  }};
  border-radius: 2px;
`;

const ScenarioSummary = styled.p`
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  margin: 0;
`;

const TriggerInvalidation = styled.div`
  display: flex;
  gap: 16px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e2e8f0;
  font-size: 11px;
`;

const TriggerItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  
  .label {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: ${props => props.$type === 'trigger' ? '#05A584' : '#ef4444'};
  }
  
  .value {
    color: #475569;
  }
`;

const ActionBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: ${props => {
    if (props.$action?.includes('long') || props.$action?.includes('buy')) return 'rgba(5, 165, 132, 0.1)';
    if (props.$action?.includes('short') || props.$action?.includes('sell')) return 'rgba(239, 68, 68, 0.1)';
    return 'rgba(100, 116, 139, 0.1)';
  }};
  color: ${props => {
    if (props.$action?.includes('long') || props.$action?.includes('buy')) return '#05A584';
    if (props.$action?.includes('short') || props.$action?.includes('sell')) return '#ef4444';
    return '#64748b';
  }};
`;

const TypeBadge = styled.span`
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 6px;
  border-radius: 4px;
  background: ${props => {
    if (props.$type === 'primary') return 'rgba(5, 165, 132, 0.15)';
    if (props.$type === 'structure') return 'rgba(59, 130, 246, 0.15)';
    return 'rgba(100, 116, 139, 0.15)';
  }};
  color: ${props => {
    if (props.$type === 'primary') return '#05A584';
    if (props.$type === 'structure') return '#3b82f6';
    return '#64748b';
  }};
`;

const getDirectionIcon = (direction) => {
  if (direction === 'bullish') return <TrendingUp size={14} />;
  if (direction === 'bearish') return <TrendingDown size={14} />;
  return <Minus size={14} />;
};

const ScenariosBlock = ({ scenarios, onScenarioClick }) => {
  if (!scenarios || scenarios.length === 0) {
    return (
      <Container data-testid="scenarios-block">
        <Title>Scenarios</Title>
        <ScenarioCard $type="neutral">
          <ScenarioHeader>
            <ScenarioTitle>
              <AlertCircle size={16} color="#64748b" />
              No clear scenario
            </ScenarioTitle>
          </ScenarioHeader>
          <ScenarioSummary>
            Market lacks dominant structure. Wait for clearer signals.
          </ScenarioSummary>
        </ScenarioCard>
      </Container>
    );
  }

  return (
    <Container data-testid="scenarios-block">
      <Title>Scenarios</Title>
      {scenarios.map((scenario, index) => (
        <ScenarioCard 
          key={index}
          $type={scenario.type}
          onClick={() => onScenarioClick?.(scenario)}
          data-testid={`scenario-${scenario.type}`}
        >
          <ScenarioHeader>
            <ScenarioTitle>
              <DirectionIcon $direction={scenario.direction}>
                {getDirectionIcon(scenario.direction)}
              </DirectionIcon>
              {scenario.title}
              <TypeBadge $type={scenario.type}>
                {scenario.type}
              </TypeBadge>
            </ScenarioTitle>
            <Probability $value={scenario.probability}>
              {Math.round(scenario.probability * 100)}%
              <ProbabilityBar>
                <ProbabilityFill $value={scenario.probability} />
              </ProbabilityBar>
            </Probability>
          </ScenarioHeader>
          <ScenarioSummary>{scenario.summary}</ScenarioSummary>
          
          {/* Trigger + Invalidation (V2) */}
          {(scenario.trigger || scenario.invalidation) && (
            <TriggerInvalidation>
              {scenario.trigger && (
                <TriggerItem $type="trigger">
                  <span className="label">Trigger</span>
                  <span className="value">{scenario.trigger}</span>
                </TriggerItem>
              )}
              {scenario.invalidation && (
                <TriggerItem $type="invalidation">
                  <span className="label">Invalidation</span>
                  <span className="value">{scenario.invalidation}</span>
                </TriggerItem>
              )}
            </TriggerInvalidation>
          )}
          
          {scenario.action && (
            <ActionBadge $action={scenario.action}>
              <ArrowRight size={10} />
              {scenario.action.replace(/_/g, ' ')}
            </ActionBadge>
          )}
        </ScenarioCard>
      ))}
    </Container>
  );
};

export default ScenariosBlock;
