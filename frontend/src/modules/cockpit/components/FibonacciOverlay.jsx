/**
 * FibonacciOverlay Component
 * ==========================
 * Renders Fibonacci retracement and extension levels on chart.
 * 
 * Shows:
 * - Swing high/low markers
 * - Retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)
 * - Extension levels (100%, 127.2%, 161.8%)
 * - Key levels (50%, 61.8%, 161.8%) highlighted
 */

import React from 'react';
import styled from 'styled-components';

// ============================================
// STYLED COMPONENTS
// ============================================

const FibCard = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 160px;
  max-width: 200px;
  backdrop-filter: blur(8px);
  z-index: 100;
  
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(245, 158, 11, 0.2);
    
    .icon {
      width: 20px;
      height: 20px;
      border-radius: 4px;
      background: rgba(245, 158, 11, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      color: #f59e0b;
    }
    
    .title {
      font-size: 11px;
      font-weight: 600;
      color: #f1f5f9;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    .direction {
      margin-left: auto;
      font-size: 10px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      
      &.bullish {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
      }
      &.bearish {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
      }
    }
  }
  
  .swing-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(245, 158, 11, 0.1);
    
    .swing-row {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      
      .label {
        color: #64748b;
      }
      .value {
        font-weight: 600;
        color: #cbd5e1;
      }
    }
  }
  
  .levels {
    display: flex;
    flex-direction: column;
    gap: 3px;
    
    .level-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 10px;
      padding: 2px 0;
      
      &.key-level {
        .ratio {
          color: #f59e0b;
          font-weight: 700;
        }
        .price {
          color: #f59e0b;
        }
      }
      
      .ratio {
        color: #94a3b8;
        font-weight: 500;
      }
      .price {
        font-weight: 600;
        color: #cbd5e1;
      }
    }
  }
  
  .section-label {
    font-size: 9px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 6px 0 4px 0;
  }
`;

// ============================================
// COMPONENT
// ============================================

const FibonacciOverlay = ({ fibonacci }) => {
  if (!fibonacci?.fib_set) return null;
  
  const { fib_set } = fibonacci;
  const {
    swing_high,
    swing_low,
    direction,
    retracement_levels = [],
    extension_levels = [],
  } = fib_set;
  
  const formatPrice = (price) => {
    if (price >= 1000) {
      return `$${price.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    }
    return `$${price.toFixed(2)}`;
  };
  
  return (
    <FibCard data-testid="fibonacci-overlay">
      <div className="header">
        <div className="icon">Φ</div>
        <span className="title">Fibonacci</span>
        <span className={`direction ${direction}`}>
          {direction === 'bullish' ? '↗' : '↘'} {direction.toUpperCase()}
        </span>
      </div>
      
      <div className="swing-info">
        <div className="swing-row">
          <span className="label">High</span>
          <span className="value">{formatPrice(swing_high.price)}</span>
        </div>
        <div className="swing-row">
          <span className="label">Low</span>
          <span className="value">{formatPrice(swing_low.price)}</span>
        </div>
      </div>
      
      <div className="levels">
        <div className="section-label">Retracement</div>
        {retracement_levels.slice(0, 5).map((level, i) => (
          <div 
            key={`ret-${i}`} 
            className={`level-row ${level.is_key_level ? 'key-level' : ''}`}
          >
            <span className="ratio">{level.label}</span>
            <span className="price">{formatPrice(level.price)}</span>
          </div>
        ))}
        
        <div className="section-label">Extension</div>
        {extension_levels.slice(0, 3).map((level, i) => (
          <div 
            key={`ext-${i}`} 
            className={`level-row ${level.is_key_level ? 'key-level' : ''}`}
          >
            <span className="ratio">{level.label}</span>
            <span className="price">{formatPrice(level.price)}</span>
          </div>
        ))}
      </div>
    </FibCard>
  );
};

export default FibonacciOverlay;
