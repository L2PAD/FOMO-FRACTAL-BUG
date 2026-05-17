/**
 * TradeSetupCard.jsx — Trade Setup Display
 * 
 * CRITICAL RULE: Only shows actionable setup when confidence = CLEAR
 * When not tradeable, shows reason and advice
 */

import React from 'react';
import styled from 'styled-components';

const Card = styled.div`
  background: ${props => props.$available ? 
    'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(15, 23, 42, 0.9) 100%)' : 
    'rgba(15, 23, 42, 0.8)'
  };
  border: 1px solid ${props => props.$available ? 
    'rgba(34, 197, 94, 0.4)' : 
    'rgba(239, 68, 68, 0.3)'
  };
  border-radius: 8px;
  padding: 16px;
  margin-top: 12px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const Title = styled.h3`
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const Badge = styled.span`
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  background: ${props => 
    props.$type === 'long' ? 'rgba(34, 197, 94, 0.2)' : 
    props.$type === 'short' ? 'rgba(239, 68, 68, 0.2)' : 
    props.$type === 'breakout' ? 'rgba(59, 130, 246, 0.2)' : 
    'rgba(148, 163, 184, 0.2)'
  };
  color: ${props => 
    props.$type === 'long' ? '#22c55e' : 
    props.$type === 'short' ? '#ef4444' : 
    props.$type === 'breakout' ? '#3b82f6' : 
    '#94a3b8'
  };
`;

const NotAvailable = styled.div`
  text-align: center;
  padding: 20px 0;
`;

const NotAvailableIcon = styled.div`
  font-size: 24px;
  margin-bottom: 8px;
`;

const Reason = styled.div`
  font-size: 12px;
  color: #f87171;
  font-weight: 500;
  margin-bottom: 8px;
`;

const Advice = styled.div`
  font-size: 11px;
  color: #94a3b8;
`;

const SetupGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 12px;
`;

const SetupItem = styled.div`
  text-align: center;
  padding: 12px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.6);
`;

const SetupLabel = styled.div`
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  margin-bottom: 4px;
`;

const SetupValue = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: ${props => 
    props.$type === 'entry' ? '#f1f5f9' : 
    props.$type === 'stop' ? '#ef4444' : 
    props.$type === 'target' ? '#22c55e' : 
    '#f1f5f9'
  };
`;

const RRBadge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  background: ${props => 
    props.$rr >= 2 ? 'rgba(34, 197, 94, 0.2)' : 
    props.$rr >= 1.5 ? 'rgba(234, 179, 8, 0.2)' : 
    'rgba(239, 68, 68, 0.2)'
  };
  color: ${props => 
    props.$rr >= 2 ? '#22c55e' : 
    props.$rr >= 1.5 ? '#eab308' : 
    '#ef4444'
  };
`;

const Notes = styled.ul`
  margin: 12px 0 0 0;
  padding: 0 0 0 16px;
  font-size: 11px;
  color: #94a3b8;
  
  li {
    margin-bottom: 4px;
  }
`;

const BreakoutContainer = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const BreakoutSide = styled.div`
  padding: 12px;
  border-radius: 6px;
  background: ${props => props.$side === 'long' ? 
    'rgba(34, 197, 94, 0.1)' : 
    'rgba(239, 68, 68, 0.1)'
  };
  border: 1px solid ${props => props.$side === 'long' ? 
    'rgba(34, 197, 94, 0.2)' : 
    'rgba(239, 68, 68, 0.2)'
  };
`;

const BreakoutTitle = styled.div`
  font-size: 11px;
  font-weight: 600;
  color: ${props => props.$side === 'long' ? '#22c55e' : '#ef4444'};
  margin-bottom: 8px;
`;

const BreakoutRow = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 4px;
  
  .label {
    color: #64748b;
  }
  
  .value {
    color: #f1f5f9;
    font-weight: 500;
  }
`;

export default function TradeSetupCard({ setup }) {
  if (!setup) {
    return null;
  }
  
  const isAvailable = setup.available === true;
  const side = (setup.side || '').toLowerCase();
  
  if (!isAvailable) {
    return (
      <Card $available={false} data-testid="trade-setup-unavailable">
        <Header>
          <Title>Trade Setup</Title>
          <Badge $type="none">NOT AVAILABLE</Badge>
        </Header>
        
        <NotAvailable>
          <NotAvailableIcon>⚠️</NotAvailableIcon>
          <Reason>{setup.reason}</Reason>
          <Advice>{setup.advice}</Advice>
        </NotAvailable>
      </Card>
    );
  }
  
  // BREAKOUT setup (Range) — shows both directions
  if (side === 'breakout' && setup.long_setup && setup.short_setup) {
    return (
      <Card $available={true} data-testid="trade-setup-breakout">
        <Header>
          <Title>Trade Setup — {setup.pattern}</Title>
          <Badge $type="breakout">BREAKOUT</Badge>
        </Header>
        
        <BreakoutContainer>
          <BreakoutSide $side="long">
            <BreakoutTitle $side="long">LONG SETUP</BreakoutTitle>
            <BreakoutRow>
              <span className="label">Entry:</span>
              <span className="value">${setup.long_setup.entry?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">Stop:</span>
              <span className="value">${setup.long_setup.stop?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">Target:</span>
              <span className="value">${setup.long_setup.target?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">R:R</span>
              <RRBadge $rr={setup.long_setup.rr_ratio}>
                {setup.long_setup.rr_ratio}
              </RRBadge>
            </BreakoutRow>
          </BreakoutSide>
          
          <BreakoutSide $side="short">
            <BreakoutTitle $side="short">SHORT SETUP</BreakoutTitle>
            <BreakoutRow>
              <span className="label">Entry:</span>
              <span className="value">${setup.short_setup.entry?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">Stop:</span>
              <span className="value">${setup.short_setup.stop?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">Target:</span>
              <span className="value">${setup.short_setup.target?.toLocaleString()}</span>
            </BreakoutRow>
            <BreakoutRow>
              <span className="label">R:R</span>
              <RRBadge $rr={setup.short_setup.rr_ratio}>
                {setup.short_setup.rr_ratio}
              </RRBadge>
            </BreakoutRow>
          </BreakoutSide>
        </BreakoutContainer>
        
        {setup.notes?.length > 0 && (
          <Notes>
            {setup.notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </Notes>
        )}
      </Card>
    );
  }
  
  // DIRECTIONAL setup (Long or Short)
  return (
    <Card $available={true} data-testid="trade-setup-directional">
      <Header>
        <Title>Trade Setup — {setup.pattern}</Title>
        <Badge $type={side}>{side.toUpperCase()}</Badge>
      </Header>
      
      <SetupGrid>
        <SetupItem>
          <SetupLabel>Entry</SetupLabel>
          <SetupValue $type="entry">
            ${setup.entry?.toLocaleString()}
          </SetupValue>
        </SetupItem>
        
        <SetupItem>
          <SetupLabel>Stop Loss</SetupLabel>
          <SetupValue $type="stop">
            ${setup.stop?.toLocaleString()}
          </SetupValue>
        </SetupItem>
        
        <SetupItem>
          <SetupLabel>Target</SetupLabel>
          <SetupValue $type="target">
            ${setup.target?.toLocaleString()}
          </SetupValue>
        </SetupItem>
      </SetupGrid>
      
      <div style={{ textAlign: 'center' }}>
        <RRBadge $rr={setup.rr_ratio}>
          Risk/Reward: {setup.rr_ratio}
        </RRBadge>
      </div>
      
      {setup.notes?.length > 0 && (
        <Notes>
          {setup.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </Notes>
      )}
    </Card>
  );
}
