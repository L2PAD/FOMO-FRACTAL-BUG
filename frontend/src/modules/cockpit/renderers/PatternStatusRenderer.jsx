/**
 * PatternStatusRenderer
 * =====================
 * 
 * Shows pattern status:
 * - If pattern exists: shows PatternRenderer
 * - If no pattern: shows "No active figure" explicitly
 * 
 * This is Layer D visualization.
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import { PatternRenderer } from './PatternRenderer';

const NoFigureBox = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 10px 14px;
  background: rgba(71, 85, 105, 0.9);
  border-radius: 8px;
  font-size: 11px;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  min-width: 140px;
  
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 10px;
  text-transform: uppercase;
  color: #94a3b8;
  
  svg { width: 14px; height: 14px; }
`;

const Status = styled.div`
  font-size: 12px;
  font-weight: 700;
`;

const Reason = styled.div`
  font-size: 9px;
  opacity: 0.7;
  margin-top: 2px;
`;

export const PatternStatusRenderer = ({ patterns }) => {
  if (!patterns) {
    return (
      <NoFigureBox data-testid="pattern-status-no-figure">
        <Header><AlertCircle /> Pattern Layer</Header>
        <Status>No active figure</Status>
        <Reason>No data available</Reason>
      </NoFigureBox>
    );
  }

  const { primary, has_figure, status, reason } = patterns;

  // If we have a valid pattern, render it
  if (has_figure && primary) {
    return <PatternRenderer pattern={primary} />;
  }

  // No active figure - show explicit status
  return (
    <NoFigureBox data-testid="pattern-status-no-figure">
      <Header><AlertCircle /> Pattern Layer</Header>
      <Status>No active figure</Status>
      {reason && <Reason>{reason}</Reason>}
    </NoFigureBox>
  );
};

export default PatternStatusRenderer;
