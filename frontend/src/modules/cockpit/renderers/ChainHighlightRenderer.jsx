/**
 * ChainHighlightRenderer
 * ======================
 * 
 * KILLER FEATURE: Visual storytelling
 * 
 * Shows the trading story on chart:
 * sweep -> choch -> entry
 * 
 * Interactive explanation right on the chart.
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { ChevronRight, Target, TrendingUp, TrendingDown, Zap } from 'lucide-react';

const ChainContainer = styled.div`
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  background: rgba(15, 23, 42, 0.95);
  border-radius: 10px;
  z-index: 10;
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
`;

const ChainStep = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  
  background: ${({ $type, $active }) => {
    if ($active) {
      switch ($type) {
        case 'sweep': return 'rgba(245, 158, 11, 0.8)';
        case 'displacement': return 'rgba(139, 92, 246, 0.8)';
        case 'choch': return 'rgba(239, 68, 68, 0.8)';
        case 'poi': return 'rgba(59, 130, 246, 0.8)';
        case 'entry': return 'rgba(5, 165, 132, 0.8)';
        default: return 'rgba(100, 116, 139, 0.8)';
      }
    }
    return 'rgba(255,255,255,0.1)';
  }};
  
  color: ${({ $active }) => $active ? '#fff' : '#94a3b8'};
  
  &:hover {
    background: ${({ $type }) => {
      switch ($type) {
        case 'sweep': return 'rgba(245, 158, 11, 0.6)';
        case 'displacement': return 'rgba(139, 92, 246, 0.6)';
        case 'choch': return 'rgba(239, 68, 68, 0.6)';
        case 'poi': return 'rgba(59, 130, 246, 0.6)';
        case 'entry': return 'rgba(5, 165, 132, 0.6)';
        default: return 'rgba(100, 116, 139, 0.6)';
      }
    }};
    color: #fff;
  }
  
  svg { width: 12px; height: 12px; }
`;

const Arrow = styled(ChevronRight)`
  width: 14px;
  height: 14px;
  color: #475569;
  flex-shrink: 0;
`;

const StepIcon = ({ type }) => {
  switch (type) {
    case 'sweep': return <Zap />;
    case 'displacement': return <TrendingUp />;
    case 'choch': return <TrendingDown />;
    case 'poi': return <Target />;
    case 'entry': return <Target />;
    default: return null;
  }
};

const StepLabel = ({ step }) => {
  switch (step.type) {
    case 'sweep':
      return `Sweep ${step.direction || ''}`;
    case 'displacement':
      return `Disp ${step.direction || ''}`;
    case 'choch':
      return `CHOCH ${step.direction || ''}`;
    case 'poi':
      return `Zone`;
    case 'entry':
      return `Entry ${step.direction || ''}`;
    default:
      return step.type;
  }
};

export const ChainHighlightRenderer = ({ chain, onStepClick }) => {
  const [activeStep, setActiveStep] = useState(null);

  if (!chain || chain.length === 0) return null;

  const handleClick = (step) => {
    setActiveStep(step.step);
    if (onStepClick) onStepClick(step);
  };

  return (
    <ChainContainer data-testid="chain-highlight-renderer">
      {chain.map((step, idx) => (
        <React.Fragment key={step.step}>
          <ChainStep 
            $type={step.type}
            $active={activeStep === step.step}
            onClick={() => handleClick(step)}
          >
            <StepIcon type={step.type} />
            <StepLabel step={step} />
          </ChainStep>
          {idx < chain.length - 1 && <Arrow />}
        </React.Fragment>
      ))}
    </ChainContainer>
  );
};

export default ChainHighlightRenderer;
