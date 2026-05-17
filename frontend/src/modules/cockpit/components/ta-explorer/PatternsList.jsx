/**
 * PatternsList.jsx — Shows all detected patterns ranked by FINAL score (V2)
 * 
 * DESIGN: Dark card with white text, clear hierarchy
 */

import React from 'react';
import styled from 'styled-components';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 14px;
`;

const Header = styled.div`
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 12px;
`;

const Row = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  background: ${props => props.$isFirst ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.02)'};
  border-left: 3px solid ${props => props.$isFirst ? '#3b82f6' : 'transparent'};
  
  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }
`;

const Left = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Rank = styled.span`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  width: 20px;
  font-weight: 500;
`;

const Type = styled.span`
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
`;

const ModeBadge = styled.span`
  font-size: 10px;
  padding: 3px 6px;
  border-radius: 4px;
  font-weight: 600;
  background: ${props => 
    props.$mode === 'strict' ? 'rgba(34, 197, 94, 0.2)' : 
    props.$mode === 'regime' ? 'rgba(59, 130, 246, 0.2)' : 
    'rgba(255, 255, 255, 0.1)'
  };
  color: ${props => 
    props.$mode === 'strict' ? '#22c55e' : 
    props.$mode === 'regime' ? '#3b82f6' : 
    '#ffffff'
  };
`;

const BiasBadge = styled.span`
  font-size: 10px;
  padding: 3px 6px;
  border-radius: 4px;
  font-weight: 600;
  background: ${props => 
    props.$bias === 'bullish' ? 'rgba(34, 197, 94, 0.2)' : 
    props.$bias === 'bearish' ? 'rgba(239, 68, 68, 0.2)' : 
    'transparent'
  };
  color: ${props => 
    props.$bias === 'bullish' ? '#22c55e' : 
    props.$bias === 'bearish' ? '#ef4444' : 
    'rgba(255, 255, 255, 0.6)'
  };
`;

const Right = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const ScoreGroup = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
`;

const FinalScore = styled.span`
  font-size: 14px;
  font-weight: 700;
  color: ${props => props.$score > 75 ? '#22c55e' : props.$score > 50 ? '#eab308' : 'rgba(255, 255, 255, 0.6)'};
`;

const BaseScore = styled.span`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
`;

const Stage = styled.span`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
  min-width: 55px;
  text-align: right;
`;

const NoData = styled.div`
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  padding: 16px;
  text-align: center;
`;

export default function PatternsList({ patterns, title = "Detected Patterns", showAll = false }) {
  if (!patterns?.length) {
    return (
      <Card>
        <Header>{title}</Header>
        <NoData>No patterns detected</NoData>
      </Card>
    );
  }
  
  const displayPatterns = showAll ? patterns : patterns.slice(0, 3);
  
  const formatType = (type) => {
    return type
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };
  
  return (
    <Card data-testid="patterns-list">
      <Header>{title}</Header>
      
      {displayPatterns.map((pattern, index) => {
        // Use final_score if available (V2), otherwise fall back to score
        const finalScore = pattern.final_score ?? (pattern.score <= 1 ? pattern.score * 100 : pattern.score);
        const baseScore = pattern.base_score ?? (pattern.score <= 1 ? pattern.score * 100 : pattern.score);
        
        return (
          <Row key={index} $isFirst={index === 0}>
            <Left>
              <Rank>#{index + 1}</Rank>
              <Type>{formatType(pattern.type)}</Type>
              <ModeBadge $mode={pattern.mode}>{pattern.mode}</ModeBadge>
              <BiasBadge $bias={pattern.bias}>{pattern.bias}</BiasBadge>
            </Left>
            
            <Right>
              <ScoreGroup>
                <FinalScore $score={finalScore}>
                  {finalScore.toFixed(0)}
                </FinalScore>
                {pattern.final_score && pattern.base_score && (
                  <BaseScore>base: {baseScore.toFixed(0)}</BaseScore>
                )}
              </ScoreGroup>
              <Stage>{pattern.stage}</Stage>
            </Right>
          </Row>
        );
      })}
      
      {!showAll && patterns.length > 3 && (
        <NoData>+{patterns.length - 3} more patterns</NoData>
      )}
    </Card>
  );
}
