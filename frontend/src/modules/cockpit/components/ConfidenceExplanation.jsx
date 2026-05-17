/**
 * ConfidenceExplanation — Why This Pattern Won
 * =============================================
 * 
 * Displays scoring breakdown with progress bars:
 * - Geometry (Pattern Shape Quality)
 * - Structure (Structure Alignment)
 * - Level (Level Confluence)
 * - Recency (Pattern Freshness)
 * - Cleanliness (Pattern Cleanliness)
 */

import React from 'react';
import styled from 'styled-components';
import { CheckCircle, AlertCircle, Info } from 'lucide-react';

const Container = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px;
`;

const Title = styled.div`
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
`;

const ScoresList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ScoreItem = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const ScoreLabel = styled.div`
  min-width: 100px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
`;

const ScoreBarContainer = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const ScoreBar = styled.div`
  flex: 1;
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
`;

const ScoreBarFill = styled.div`
  height: 100%;
  width: ${props => Math.min(100, props.$value * 100)}%;
  background: ${props => {
    if (props.$value >= 0.75) return 'linear-gradient(90deg, #05A584 0%, #10b981 100%)';
    if (props.$value >= 0.5) return 'linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)';
    return 'linear-gradient(90deg, #94a3b8 0%, #cbd5e1 100%)';
  }};
  border-radius: 4px;
  transition: width 0.3s ease;
`;

const ScoreValue = styled.div`
  min-width: 45px;
  font-size: 13px;
  font-weight: 700;
  color: ${props => {
    if (props.$value >= 0.75) return '#05A584';
    if (props.$value >= 0.5) return '#f59e0b';
    return '#94a3b8';
  }};
  text-align: right;
`;

const ScoreStatus = styled.span`
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  min-width: 70px;
  text-align: center;
  background: ${props => {
    switch (props.$status) {
      case 'strong': return 'rgba(5, 165, 132, 0.1)';
      case 'good': return 'rgba(16, 185, 129, 0.1)';
      case 'moderate': return 'rgba(245, 158, 11, 0.1)';
      default: return 'rgba(148, 163, 184, 0.1)';
    }
  }};
  color: ${props => {
    switch (props.$status) {
      case 'strong': return '#05A584';
      case 'good': return '#10b981';
      case 'moderate': return '#f59e0b';
      default: return '#94a3b8';
    }
  }};
`;

const Summary = styled.div`
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
`;

const SummaryIcon = styled.span`
  display: flex;
  align-items: center;
  color: ${props => props.$positive ? '#05A584' : '#f59e0b'};
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
`;

const scoreLabels = {
  geometry: 'Geometry',
  structure: 'Structure',
  level: 'Level',
  recency: 'Recency',
  cleanliness: 'Cleanliness'
};

const scoreTitles = {
  geometry: 'Pattern Shape Quality',
  structure: 'Structure Alignment',
  level: 'Level Confluence',
  recency: 'Pattern Freshness',
  cleanliness: 'Pattern Cleanliness'
};

const getStatus = (value) => {
  if (value >= 0.8) return 'strong';
  if (value >= 0.6) return 'good';
  if (value >= 0.4) return 'moderate';
  return 'weak';
};

const ConfidenceExplanation = ({ explanation }) => {
  if (!explanation || Object.keys(explanation).length === 0) {
    return (
      <Container data-testid="confidence-explanation">
        <Title>
          <Info size={14} />
          Why This Pattern
        </Title>
        <EmptyState>
          No pattern selected or no scoring data available.
        </EmptyState>
      </Container>
    );
  }

  // Calculate overall summary
  const scores = Object.entries(explanation).map(([key, data]) => {
    const value = typeof data === 'object' ? data.value : data;
    return { key, value };
  });
  
  const avgScore = scores.reduce((sum, s) => sum + s.value, 0) / scores.length;
  const strongCount = scores.filter(s => s.value >= 0.75).length;
  const weakCount = scores.filter(s => s.value < 0.5).length;

  return (
    <Container data-testid="confidence-explanation">
      <Title>
        <Info size={14} />
        Why This Pattern
      </Title>
      
      <ScoresList>
        {Object.entries(explanation).map(([key, data]) => {
          const value = typeof data === 'object' ? data.value : data;
          const status = typeof data === 'object' ? data.status : getStatus(value);
          const label = typeof data === 'object' ? data.label : scoreTitles[key];
          
          return (
            <ScoreItem key={key} data-testid={`score-${key}`}>
              <ScoreLabel title={label}>
                {scoreLabels[key] || key}
              </ScoreLabel>
              <ScoreBarContainer>
                <ScoreBar>
                  <ScoreBarFill $value={value} />
                </ScoreBar>
                <ScoreValue $value={value}>
                  {Math.round(value * 100)}%
                </ScoreValue>
                <ScoreStatus $status={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </ScoreStatus>
              </ScoreBarContainer>
            </ScoreItem>
          );
        })}
      </ScoresList>

      <Summary>
        <SummaryIcon $positive={avgScore >= 0.6}>
          {avgScore >= 0.6 ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
        </SummaryIcon>
        {strongCount >= 3 
          ? `Strong pattern with ${strongCount} high-confidence factors`
          : weakCount >= 2
            ? `Pattern has ${weakCount} areas that need confirmation`
            : `Moderate pattern with mixed confidence factors`
        }
      </Summary>
    </Container>
  );
};

export default ConfidenceExplanation;
