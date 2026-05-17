/**
 * PatternsBlock — Primary + Alternative Patterns
 * ===============================================
 * 
 * Displays:
 * - Primary pattern (always active)
 * - Alternative patterns (clickable to show on chart)
 */

import React from 'react';
import styled from 'styled-components';
import { Triangle, TrendingUp, TrendingDown, Minus, Eye, EyeOff, ChevronRight } from 'lucide-react';

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

const PatternCard = styled.div`
  padding: 14px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  ${props => props.$primary ? `
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
    border: 2px solid #3b82f6;
  ` : `
    background: #f8fafc;
    border: 1px solid ${props.$active ? '#3b82f6' : '#e2e8f0'};
  `}
  
  &:hover {
    border-color: #3b82f6;
    transform: translateY(-1px);
  }
`;

const PatternHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
`;

const PatternInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const PatternIcon = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${props => {
    if (props.$direction === 'bullish') return 'rgba(5, 165, 132, 0.15)';
    if (props.$direction === 'bearish') return 'rgba(239, 68, 68, 0.15)';
    return 'rgba(59, 130, 246, 0.15)';
  }};
  color: ${props => {
    if (props.$direction === 'bullish') return '#05A584';
    if (props.$direction === 'bearish') return '#ef4444';
    return '#3b82f6';
  }};
`;

const PatternName = styled.div`
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
`;

const PatternDirection = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: ${props => {
    if (props.$direction === 'bullish') return '#05A584';
    if (props.$direction === 'bearish') return '#ef4444';
    return '#64748b';
  }};
  text-transform: capitalize;
`;

const PatternScore = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ScoreValue = styled.span`
  font-size: 14px;
  font-weight: 700;
  color: ${props => {
    if (props.$value >= 0.7) return '#05A584';
    if (props.$value >= 0.5) return '#f59e0b';
    return '#94a3b8';
  }};
`;

const ActiveBadge = styled.span`
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: ${props => props.$active ? 'rgba(59, 130, 246, 0.15)' : 'transparent'};
  color: ${props => props.$active ? '#3b82f6' : '#94a3b8'};
  display: flex;
  align-items: center;
  gap: 4px;
`;

const PatternMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #64748b;
`;

const MetaItem = styled.span`
  display: flex;
  align-items: center;
  gap: 4px;
`;

const AlternativesList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
`;

const AlternativeLabel = styled.div`
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
`;

const ShowButton = styled.button`
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: ${props => props.$active ? '#3b82f6' : '#ffffff'};
  color: ${props => props.$active ? '#ffffff' : '#64748b'};
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.$active ? '#2563eb' : '#f1f5f9'};
    border-color: #3b82f6;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
`;

const formatPatternName = (type) => {
  if (!type) return 'Unknown';
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

const getPatternIcon = (direction) => {
  if (direction === 'bullish') return <TrendingUp size={16} />;
  if (direction === 'bearish') return <TrendingDown size={16} />;
  return <Triangle size={16} />;
};

const PatternsBlock = ({ 
  primaryPattern, 
  alternativePatterns, 
  activePatternId, 
  onPatternClick 
}) => {
  if (!primaryPattern) {
    return (
      <Container data-testid="patterns-block">
        <Title>Patterns</Title>
        <EmptyState>
          No significant pattern detected for current timeframe.
        </EmptyState>
      </Container>
    );
  }

  const isPrimaryActive = !activePatternId || activePatternId === 'primary';

  return (
    <Container data-testid="patterns-block">
      <Title>Patterns</Title>
      
      {/* Primary Pattern */}
      <PatternCard 
        $primary 
        $active={isPrimaryActive}
        onClick={() => onPatternClick?.('primary')}
        data-testid="primary-pattern"
      >
        <PatternHeader>
          <PatternInfo>
            <PatternIcon $direction={primaryPattern.direction}>
              {getPatternIcon(primaryPattern.direction)}
            </PatternIcon>
            <div>
              <PatternName>{formatPatternName(primaryPattern.type)}</PatternName>
              <PatternDirection $direction={primaryPattern.direction}>
                {primaryPattern.direction || 'Neutral'}
              </PatternDirection>
            </div>
          </PatternInfo>
          <PatternScore>
            <ScoreValue $value={primaryPattern.total_score}>
              {Math.round((primaryPattern.total_score || primaryPattern.confidence || 0.5) * 100)}%
            </ScoreValue>
            <ActiveBadge $active={isPrimaryActive}>
              {isPrimaryActive ? <Eye size={12} /> : <EyeOff size={12} />}
              {isPrimaryActive ? 'Active' : 'Show'}
            </ActiveBadge>
          </PatternScore>
        </PatternHeader>
        <PatternMeta>
          {primaryPattern.touch_count > 0 && (
            <MetaItem>Touches: {primaryPattern.touch_count}</MetaItem>
          )}
          {primaryPattern.containment > 0 && (
            <MetaItem>Containment: {Math.round(primaryPattern.containment * 100)}%</MetaItem>
          )}
        </PatternMeta>
      </PatternCard>

      {/* Alternative Patterns */}
      {alternativePatterns && alternativePatterns.length > 0 && (
        <AlternativesList>
          <AlternativeLabel>Alternatives</AlternativeLabel>
          {alternativePatterns.slice(0, 2).map((alt, index) => {
            const altId = `alt-${index}`;
            const isActive = activePatternId === altId;
            
            return (
              <PatternCard 
                key={index}
                $active={isActive}
                onClick={() => onPatternClick?.(altId)}
                data-testid={`alternative-pattern-${index}`}
              >
                <PatternHeader>
                  <PatternInfo>
                    <PatternIcon $direction={alt.direction}>
                      {getPatternIcon(alt.direction)}
                    </PatternIcon>
                    <div>
                      <PatternName style={{ fontSize: 13 }}>
                        {formatPatternName(alt.type)}
                      </PatternName>
                      <PatternDirection $direction={alt.direction}>
                        {alt.direction || 'Neutral'}
                      </PatternDirection>
                    </div>
                  </PatternInfo>
                  <ShowButton $active={isActive}>
                    {isActive ? <Eye size={12} /> : <ChevronRight size={12} />}
                    {isActive ? 'Active' : 'Show'}
                  </ShowButton>
                </PatternHeader>
              </PatternCard>
            );
          })}
        </AlternativesList>
      )}
    </Container>
  );
};

export default PatternsBlock;
