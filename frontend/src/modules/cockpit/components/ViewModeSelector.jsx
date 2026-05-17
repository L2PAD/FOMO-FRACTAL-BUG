/**
 * ViewModeSelector Component
 * ==========================
 * Toggle between visibility modes:
 * - Auto: Smart context-aware selection
 * - Classic TA: Indicators + Patterns + Fib
 * - Smart Money: POI + Liquidity + CHOCH
 * - Minimal: Essential elements only
 */

import React from 'react';
import styled from 'styled-components';
import { Eye, TrendingUp, DollarSign, Minimize2 } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const SelectorContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 2px;
`;

const ModeButton = styled.button`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: ${({ $active }) => $active ? '#0f172a' : 'transparent'};
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: ${({ $active }) => $active ? '#ffffff' : '#64748b'};
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;          /* UI FIX 2026-04-30: prevent "Classic TA" from wrapping to 2 lines */
  flex-shrink: 0;               /* UI FIX 2026-04-30 */
  
  &:hover {
    color: ${({ $active }) => $active ? '#ffffff' : '#0f172a'};
    background: ${({ $active }) => $active ? '#0f172a' : 'rgba(15, 23, 42, 0.05)'};
  }
  
  svg {
    width: 13px;
    height: 13px;
    flex-shrink: 0;
  }
  
  .label {
    @media (max-width: 1200px) {
      display: none;
    }
  }
`;

const Tooltip = styled.span`
  position: relative;
  
  &:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
  }
  
  .tooltip-text {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    margin-bottom: 8px;
    padding: 6px 10px;
    background: #0f172a;
    color: #f1f5f9;
    font-size: 10px;
    white-space: nowrap;
    border-radius: 6px;
    z-index: 1000;
    transition: all 0.2s ease;
    
    &::after {
      content: '';
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      border: 5px solid transparent;
      border-top-color: #0f172a;
    }
  }
`;

// ============================================
// MODES CONFIG
// ============================================

const MODES = [
  {
    id: 'auto',
    label: 'Auto',
    icon: Eye,
    tooltip: 'Smart auto-selection based on context',
  },
  {
    id: 'classic',
    label: 'Classic TA',
    icon: TrendingUp,
    tooltip: 'Indicators + Patterns + Fibonacci',
  },
  {
    id: 'smart',
    label: 'Smart Money',
    icon: DollarSign,
    tooltip: 'POI + Liquidity + CHOCH',
  },
  {
    id: 'minimal',
    label: 'Minimal',
    icon: Minimize2,
    tooltip: 'Only essential elements',
  },
];

// ============================================
// COMPONENT
// ============================================

const ViewModeSelector = ({ 
  mode = 'auto', 
  onChange,
}) => {
  return (
    <SelectorContainer data-testid="view-mode-selector">
      {MODES.map(({ id, label, icon: Icon, tooltip }) => (
        <Tooltip key={id}>
          <ModeButton
            $active={mode === id}
            onClick={() => onChange?.(id)}
          >
            <Icon />
            <span className="label">{label}</span>
          </ModeButton>
          <span className="tooltip-text">{tooltip}</span>
        </Tooltip>
      ))}
    </SelectorContainer>
  );
};

export default ViewModeSelector;
