/**
 * LiquidityRenderer
 * =================
 * Renders limited liquidity data (eq highs/lows, sweeps)
 */

import React from 'react';
import styled from 'styled-components';

const LiquidityInfo = styled.div`
  position: absolute;
  bottom: 100px;
  left: 12px;
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.9);
  border-radius: 6px;
  font-size: 10px;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  
  .title { font-weight: 700; margin-bottom: 4px; }
  .item { 
    font-size: 9px; 
    opacity: 0.9;
    padding: 2px 0;
  }
`;

export const LiquidityRenderer = ({ liquidity }) => {
  if (!liquidity) return null;

  const { eq, sweeps, bsl, ssl, pools } = liquidity;
  const hasEq = eq && eq.length > 0;
  const hasSweeps = sweeps && sweeps.length > 0;
  
  // Handle BSL/SSL as arrays (from render_plan format)
  const bslItems = Array.isArray(bsl) ? bsl : (bsl ? [{ price: bsl }] : []);
  const sslItems = Array.isArray(ssl) ? ssl : (ssl ? [{ price: ssl }] : []);
  
  // Also check pools format
  const poolBSL = pools?.filter(p => p.type === 'buy_side_liquidity') || [];
  const poolSSL = pools?.filter(p => p.type === 'sell_side_liquidity') || [];
  
  const allBSL = bslItems.length > 0 ? bslItems : poolBSL;
  const allSSL = sslItems.length > 0 ? sslItems : poolSSL;
  
  const hasBSL = allBSL.length > 0;
  const hasSSL = allSSL.length > 0;

  if (!hasEq && !hasSweeps && !hasBSL && !hasSSL) return null;

  return (
    <LiquidityInfo data-testid="liquidity-renderer">
      <div className="title">Liquidity</div>
      {allBSL.slice(0, 2).map((b, i) => (
        <div key={`bsl-${i}`} className="item">
          BSL: ${typeof b.price === 'number' ? b.price.toFixed(0) : b.price || 'N/A'}
        </div>
      ))}
      {allSSL.slice(0, 2).map((s, i) => (
        <div key={`ssl-${i}`} className="item">
          SSL: ${typeof s.price === 'number' ? s.price.toFixed(0) : s.price || 'N/A'}
        </div>
      ))}
      {hasEq && eq.slice(0, 2).map((e, i) => (
        <div key={i} className="item">
          EQ {e.type || 'Level'}: ${(e.price || 0).toFixed(2)}
        </div>
      ))}
      {hasSweeps && sweeps.slice(0, 1).map((s, i) => (
        <div key={i} className="item" style={{ color: '#fef3c7' }}>
          Sweep: {s.direction || s.type || 'N/A'}
        </div>
      ))}
    </LiquidityInfo>
  );
};

export default LiquidityRenderer;
