/**
 * PatternRenderer
 * ===============
 * Renders active pattern overlay
 */

import React from 'react';
import styled from 'styled-components';

const PatternBox = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.95);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  
  .name { text-transform: capitalize; }
  .confidence { opacity: 0.9; font-size: 11px; margin-left: 6px; }
  .direction { 
    font-size: 10px; 
    margin-top: 4px;
    padding: 2px 6px;
    background: rgba(255,255,255,0.2);
    border-radius: 4px;
    display: inline-block;
  }
`;

export const PatternRenderer = ({ pattern }) => {
  if (!pattern || !pattern.type) return null;

  const name = pattern.type.replace(/_/g, ' ');
  const confidence = pattern.confidence ? Math.round(pattern.confidence * 100) : null;
  const direction = pattern.direction_bias;

  return (
    <PatternBox data-testid="pattern-renderer">
      <span className="name">{name}</span>
      {confidence && <span className="confidence">{confidence}%</span>}
      {direction && <div className="direction">{direction}</div>}
    </PatternBox>
  );
};

export default PatternRenderer;
