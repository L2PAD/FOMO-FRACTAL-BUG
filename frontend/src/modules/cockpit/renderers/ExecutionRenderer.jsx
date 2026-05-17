/**
 * ExecutionRenderer V2
 * ====================
 * Renders Layer F: Execution - ALWAYS VISIBLE
 * 
 * Status: valid | waiting | no_trade
 * 
 * Shows detailed reason and context, not just a badge.
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Clock, XCircle } from 'lucide-react';

const ExecutionBox = styled.div`
  position: absolute;
  top: 110px;
  right: 12px;
  padding: 12px 16px;
  background: ${({ $status, $direction }) => {
    if ($status === 'valid') {
      return $direction === 'long' ? 'rgba(5, 165, 132, 0.95)' : 'rgba(239, 68, 68, 0.95)';
    }
    if ($status === 'waiting') return 'rgba(245, 158, 11, 0.95)';
    return 'rgba(71, 85, 105, 0.95)';
  }};
  border-radius: 10px;
  font-size: 11px;
  color: #fff;
  z-index: 6;
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  min-width: 160px;
  max-width: 200px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.2);
  
  svg { width: 16px; height: 16px; }
`;

const Title = styled.div`
  font-size: 10px;
  opacity: 0.8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const StatusBadge = styled.div`
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
`;

const Row = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 11px;
  
  &.entry { color: #fff; }
  &.stop { color: #fca5a5; }
  &.target { color: #86efac; }
`;

const RR = styled.div`
  font-size: 16px;
  font-weight: 700;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.2);
  text-align: center;
`;

const Reason = styled.div`
  font-size: 10px;
  opacity: 0.9;
  margin-top: 6px;
  padding: 6px 8px;
  background: rgba(0,0,0,0.2);
  border-radius: 6px;
  line-height: 1.4;
`;

const Detail = styled.div`
  font-size: 9px;
  opacity: 0.7;
  margin-top: 4px;
`;

const StatusIcon = ({ status, direction }) => {
  if (status === 'valid') {
    return direction === 'long' ? <TrendingUp /> : <TrendingDown />;
  }
  if (status === 'waiting') return <Clock />;
  return <XCircle />;
};

export const ExecutionRenderer = ({ execution }) => {
  // ALWAYS render - execution never disappears
  if (!execution) {
    return (
      <ExecutionBox $status="no_trade" data-testid="execution-renderer">
        <Header>
          <XCircle />
          <div>
            <Title>Execution</Title>
            <StatusBadge>NO DATA</StatusBadge>
          </div>
        </Header>
        <Reason>Unable to compute execution</Reason>
      </ExecutionBox>
    );
  }

  const { status, direction, entry_zone, stop, targets, rr, reason, detail, model } = execution;

  // Valid execution
  if (status === 'valid') {
    const entryPrice = entry_zone?.ideal || entry_zone?.low;
    
    return (
      <ExecutionBox $status="valid" $direction={direction} data-testid="execution-renderer">
        <Header>
          <StatusIcon status="valid" direction={direction} />
          <div>
            <Title>{model || 'Trade Setup'}</Title>
            <StatusBadge>{direction?.toUpperCase()}</StatusBadge>
          </div>
        </Header>
        
        {entryPrice && (
          <Row className="entry">
            <span>Entry</span>
            <span>${Number(entryPrice).toFixed(2)}</span>
          </Row>
        )}
        
        {stop && (
          <Row className="stop">
            <span>Stop Loss</span>
            <span>${Number(stop).toFixed(2)}</span>
          </Row>
        )}
        
        {targets?.slice(0, 3).map((tp, i) => {
          const price = typeof tp === 'number' ? tp : tp?.price;
          return price ? (
            <Row key={i} className="target">
              <span>TP{i + 1}</span>
              <span>${Number(price).toFixed(2)}</span>
            </Row>
          ) : null;
        })}
        
        {rr && <RR>R:R {Number(rr).toFixed(1)}</RR>}
      </ExecutionBox>
    );
  }

  // Waiting
  if (status === 'waiting') {
    return (
      <ExecutionBox $status="waiting" data-testid="execution-renderer">
        <Header>
          <Clock />
          <div>
            <Title>Execution</Title>
            <StatusBadge>WAITING</StatusBadge>
          </div>
        </Header>
        <Reason>{reason || 'Waiting for confirmation'}</Reason>
        {detail && <Detail>{detail}</Detail>}
      </ExecutionBox>
    );
  }

  // No trade
  return (
    <ExecutionBox $status="no_trade" data-testid="execution-renderer">
      <Header>
        <XCircle />
        <div>
          <Title>Execution</Title>
          <StatusBadge>NO TRADE</StatusBadge>
        </div>
      </Header>
      <Reason>{reason || 'No valid setup'}</Reason>
      {detail && <Detail>{detail}</Detail>}
    </ExecutionBox>
  );
};

export default ExecutionRenderer;
