/**
 * PatternOverlay Component
 * ========================
 * Renders pattern geometry on chart:
 * - Triangles (upper/lower lines)
 * - Channels (parallel lines)
 * - Double Top/Bottom (peaks + neckline)
 * - Head & Shoulders (shoulders, head, neckline)
 * 
 * Only shows 1 primary + 1 alternative pattern max.
 */

import React from 'react';
import styled from 'styled-components';

// ============================================
// STYLED COMPONENTS
// ============================================

const PatternCard = styled.div`
  position: absolute;
  bottom: 60px;
  left: 12px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 180px;
  max-width: 240px;
  backdrop-filter: blur(8px);
  z-index: 100;
  
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    
    .icon {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 700;
      
      &.bullish {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
      }
      &.bearish {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
      }
      &.neutral {
        background: rgba(148, 163, 184, 0.2);
        color: #94a3b8;
      }
    }
    
    .title {
      font-size: 11px;
      font-weight: 600;
      color: #f1f5f9;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
  }
  
  .type {
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 6px;
  }
  
  .meta {
    display: flex;
    flex-direction: column;
    gap: 4px;
    
    .row {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      
      .label {
        color: #64748b;
      }
      .value {
        font-weight: 600;
        color: #cbd5e1;
        
        &.bullish { color: #22c55e; }
        &.bearish { color: #ef4444; }
      }
    }
  }
  
  .score-bar {
    margin-top: 8px;
    height: 4px;
    background: rgba(100, 116, 139, 0.3);
    border-radius: 2px;
    overflow: hidden;
    
    .fill {
      height: 100%;
      border-radius: 2px;
      background: linear-gradient(90deg, #3b82f6, #22c55e);
    }
  }
`;

const AltPatternBadge = styled.div`
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 10px;
  color: #94a3b8;
  z-index: 99;
  
  .alt-type {
    font-weight: 600;
    color: #cbd5e1;
  }
`;

// ============================================
// HELPER FUNCTIONS
// ============================================

const formatPatternType = (type) => {
  const typeMap = {
    'descending_triangle': 'Descending Triangle',
    'ascending_triangle': 'Ascending Triangle',
    'symmetrical_triangle': 'Symmetrical Triangle',
    'falling_wedge': 'Falling Wedge',
    'rising_wedge': 'Rising Wedge',
    'ascending_channel': 'Ascending Channel',
    'descending_channel': 'Descending Channel',
    'horizontal_channel': 'Horizontal Channel',
    'double_top': 'Double Top',
    'double_bottom': 'Double Bottom',
    'head_shoulders': 'Head & Shoulders',
    'inverse_head_shoulders': 'Inverse H&S',
  };
  return typeMap[type] || (type ? type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Unknown Pattern');
};

const getBiasIcon = (bias) => {
  if (bias === 'bullish') return '↗';
  if (bias === 'bearish') return '↘';
  return '→';
};

// ============================================
// COMPONENT
// ============================================

const PatternOverlay = ({ patternV2, chartRef, priceSeries }) => {
  if (!patternV2) return null;
  
  const { primary_pattern, alternative_patterns = [] } = patternV2;
  
  if (!primary_pattern) return null;
  
  const alternative = alternative_patterns[0] || null;
  
  return (
    <>
      {/* Primary Pattern Card */}
      <PatternCard data-testid="pattern-overlay">
        <div className="header">
          <div className={`icon ${primary_pattern.direction_bias || primary_pattern.direction || 'neutral'}`}>
            {getBiasIcon(primary_pattern.direction_bias || primary_pattern.direction)}
          </div>
          <span className="title">Pattern Detected</span>
        </div>
        
        <div className="type">{formatPatternType(primary_pattern.type)}</div>
        
        <div className="meta">
          <div className="row">
            <span className="label">Bias</span>
            <span className={`value ${primary_pattern.direction_bias || primary_pattern.direction || 'neutral'}`}>
              {(primary_pattern.direction_bias || primary_pattern.direction || 'neutral').toUpperCase()}
            </span>
          </div>
          <div className="row">
            <span className="label">Breakout</span>
            <span className="value">${primary_pattern.breakout_level?.toLocaleString()}</span>
          </div>
          <div className="row">
            <span className="label">Invalidation</span>
            <span className="value">${(primary_pattern.invalidation_level || primary_pattern.invalidation)?.toLocaleString()}</span>
          </div>
          <div className="row">
            <span className="label">Score</span>
            <span className="value">{((primary_pattern.scores?.total || primary_pattern.total_score || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
        
        <div className="score-bar">
          <div 
            className="fill" 
            style={{ width: `${(primary_pattern.scores?.total || primary_pattern.total_score || 0) * 100}%` }}
          />
        </div>
      </PatternCard>
      
      {/* Alternative Pattern Badge */}
      {alternative && (
        <AltPatternBadge data-testid="alt-pattern-badge">
          Alt: <span className="alt-type">{formatPatternType(alternative.type)}</span>
          {' '}({(alternative.scores?.total * 100).toFixed(0)}%)
        </AltPatternBadge>
      )}
    </>
  );
};

export default PatternOverlay;
