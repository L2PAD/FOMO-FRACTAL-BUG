/**
 * RejectedList.jsx — Shows patterns that failed validation
 */

import React from 'react';
import styled from 'styled-components';

const Card = styled.div`
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
`;

const Header = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: #f87171;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
`;

const Row = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  font-size: 11px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.05);
  
  &:last-child {
    border-bottom: none;
  }
`;

const Type = styled.span`
  color: #94a3b8;
`;

const Reason = styled.span`
  color: #f87171;
  font-size: 10px;
`;

const NoData = styled.div`
  color: #64748b;
  font-size: 11px;
  padding: 12px;
  text-align: center;
`;

export default function RejectedList({ rejected }) {
  if (!rejected?.length) {
    return (
      <Card>
        <Header>Rejected Patterns</Header>
        <NoData>No patterns rejected</NoData>
      </Card>
    );
  }
  
  const formatType = (type) => {
    return type
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };
  
  return (
    <Card data-testid="rejected-list">
      <Header>
        <span>Rejected Patterns</span>
      </Header>
      
      {rejected.map((item, index) => (
        <Row key={index}>
          <Type>{formatType(item.type)}</Type>
          <Reason>{item.reason}</Reason>
        </Row>
      ))}
    </Card>
  );
}
