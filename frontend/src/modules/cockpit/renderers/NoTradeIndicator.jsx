/**
 * NoTradeIndicator — Single unified "No Trade" status
 * ====================================================
 * 
 * REPLACES multiple "NO TRADE" indicators across:
 * - PatternStatusRenderer (No active figure)
 * - ExecutionRenderer (EXECUTION NO TRADE)
 * - SetupOverlay (NO TRADE badge)
 * 
 * POSITION: Left side (under MarketState badge)
 * TOGGLE: Via TA Overlay button
 */

import React from 'react';
import styled from 'styled-components';
import { XCircle } from 'lucide-react';

const Container = styled.div`
  position: absolute;
  top: 12px;
  left: 170px;
  padding: 8px 14px;
  background: rgba(71, 85, 105, 0.9);
  border-radius: 8px;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 11px;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 200px;
  
  svg {
    width: 14px;
    height: 14px;
    color: #f87171;
    flex-shrink: 0;
  }
`;

const Text = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const Status = styled.div`
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const Reason = styled.div`
  font-size: 9px;
  opacity: 0.8;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

/**
 * NoTradeIndicator
 * 
 * @param {boolean} isVisible - Controlled by TA Overlay toggle
 * @param {string} reason - Why no trade (e.g. "No active figure", "unified setup invalid")
 * @param {string} detail - Additional context
 */
export const NoTradeIndicator = ({ isVisible = true, reason, detail }) => {
  if (!isVisible) return null;
  
  return (
    <Container data-testid="no-trade-indicator">
      <XCircle />
      <Text>
        <Status>No Trade</Status>
        {reason && <Reason>{reason}</Reason>}
      </Text>
    </Container>
  );
};

export default NoTradeIndicator;
