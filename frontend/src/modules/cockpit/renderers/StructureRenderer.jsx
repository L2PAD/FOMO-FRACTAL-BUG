/**
 * StructureRenderer
 * =================
 * Renders simplified market structure (swings, choch, bos)
 */

import React from 'react';
import styled from 'styled-components';

const StructureInfo = styled.div`
  position: absolute;
  bottom: 50px;
  right: 12px;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.9);
  border-radius: 6px;
  font-size: 10px;
  color: #e2e8f0;
  z-index: 5;
  backdrop-filter: blur(4px);
  min-width: 100px;
  
  .trend {
    font-weight: 700;
    text-transform: uppercase;
    color: ${({ $trend }) => 
      $trend === 'uptrend' ? '#05A584' : 
      $trend === 'downtrend' ? '#ef4444' : '#94a3b8'};
  }
  
  .event {
    margin-top: 4px;
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 600;
  }
  
  .choch { background: rgba(239, 68, 68, 0.3); color: #fca5a5; }
  .bos { background: rgba(5, 165, 132, 0.3); color: #6ee7b7; }
`;

export const StructureRenderer = ({ structure }) => {
  if (!structure) return null;

  const { trend, choch, bos, bias } = structure;
  const hasChoch = choch && choch.length > 0;
  const hasBos = bos && bos.length > 0;

  return (
    <StructureInfo $trend={trend} data-testid="structure-renderer">
      <div className="trend">{trend || 'Unknown'}</div>
      {hasChoch && (
        <div className="event choch">
          CHOCH {choch[0]?.direction || ''}
        </div>
      )}
      {hasBos && (
        <div className="event bos">
          BOS {bos[0]?.direction || ''}
        </div>
      )}
      {bias && (
        <div style={{ marginTop: 4, opacity: 0.7 }}>
          Bias: {bias}
        </div>
      )}
    </StructureInfo>
  );
};

export default StructureRenderer;
