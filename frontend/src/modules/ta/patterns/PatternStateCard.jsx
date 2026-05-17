/**
 * PatternStateCard
 * ================
 * 
 * Shows pattern state, triggers, and actionability.
 * This is the decision-grade UI for the pattern.
 * 
 * DESIGN: Clean white background with black text
 * Consistent with light theme UI system
 */

import React from 'react';
import { getStateColor, getDirectionColor } from './patternRenderAdapter';

/**
 * @param {Object} props
 * @param {Object} props.pattern - Normalized pattern from adaptPatternV2
 */
export function PatternStateCard({ pattern }) {
  if (!pattern) {
    return (
      <div style={{
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        background: '#ffffff',
        padding: '16px',
      }}>
        <div style={{ fontSize: '14px', color: '#64748b' }}>No pattern detected</div>
      </div>
    );
  }
  
  // State colors mapping for light theme
  const stateStyles = {
    CLEAR: { bg: '#dcfce7', border: '#22c55e', text: '#15803d' },
    CONFLICTED: { bg: '#fee2e2', border: '#ef4444', text: '#dc2626' },
    COMPRESSION: { bg: '#dbeafe', border: '#3b82f6', text: '#2563eb' },
    WEAK: { bg: '#fef3c7', border: '#f59e0b', text: '#d97706' },
    NONE: { bg: '#f1f5f9', border: '#94a3b8', text: '#64748b' },
  };
  
  const dirStyles = {
    bullish: { text: '#15803d', icon: '▲' },
    bearish: { text: '#dc2626', icon: '▼' },
    neutral: { text: '#64748b', icon: '◆' },
  };
  
  const state = stateStyles[pattern.state] || stateStyles.NONE;
  const dir = dirStyles[pattern.direction] || dirStyles.neutral;
  
  return (
    <div style={{
      borderRadius: '12px',
      border: '1px solid #e2e8f0',
      background: '#ffffff',
      padding: '20px',
    }}>
      {/* Header: Pattern + State */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '10px', fontWeight: '600', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>
            Primary Pattern
          </div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: dir.text }}>{dir.icon}</span>
            {pattern.title}
          </div>
        </div>
        
        <div style={{
          padding: '6px 12px',
          borderRadius: '8px',
          background: state.bg,
          border: `1px solid ${state.border}`,
        }}>
          <div style={{ fontSize: '12px', fontWeight: '700', color: state.text }}>
            {pattern.state}
          </div>
        </div>
      </div>
      
      {/* Summary */}
      {pattern.summary && (
        <div style={{ fontSize: '14px', color: '#475569', lineHeight: '1.5', marginBottom: '16px' }}>
          {pattern.summary}
        </div>
      )}
      
      {/* Stats Row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '13px', marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: '#64748b' }}>Confidence:</span>
          <span style={{ color: '#0f172a', fontWeight: '600' }}>
            {(pattern.confidence * 100).toFixed(0)}%
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: '#64748b' }}>Direction:</span>
          <span style={{ fontWeight: '600', color: dir.text }}>
            {pattern.direction}
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: '#64748b' }}>Action:</span>
          <span style={{ 
            fontWeight: '600', 
            color: pattern.actionability === 'HIGH' ? '#15803d' :
                   pattern.actionability === 'MEDIUM' ? '#d97706' : '#64748b'
          }}>
            {pattern.actionability}
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: '#64748b' }}>Tradeable:</span>
          <span style={{ fontWeight: '600', color: pattern.tradeable ? '#15803d' : '#dc2626' }}>
            {pattern.tradeable ? 'Yes' : 'No'}
          </span>
        </div>
      </div>
      
      {/* Triggers - CRITICAL */}
      {(pattern.trigger.up || pattern.trigger.down) && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '10px', fontWeight: '600', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
            Wait Conditions
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
            {pattern.trigger.up && (
              <div style={{
                borderRadius: '8px',
                background: '#f0fdf4',
                border: '1px solid #22c55e',
                padding: '12px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#15803d', fontWeight: '600', fontSize: '14px' }}>
                  <span>▲</span>
                  <span>Breakout: {pattern.trigger.up.toLocaleString()}</span>
                </div>
                {pattern.trigger.upMessage && (
                  <div style={{ fontSize: '12px', color: '#166534', marginTop: '6px' }}>
                    {pattern.trigger.upMessage}
                  </div>
                )}
              </div>
            )}
            
            {pattern.trigger.down && (
              <div style={{
                borderRadius: '8px',
                background: '#fef2f2',
                border: '1px solid #ef4444',
                padding: '12px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', fontWeight: '600', fontSize: '14px' }}>
                  <span>▼</span>
                  <span>Breakdown: {pattern.trigger.down.toLocaleString()}</span>
                </div>
                {pattern.trigger.downMessage && (
                  <div style={{ fontSize: '12px', color: '#991b1b', marginTop: '6px' }}>
                    {pattern.trigger.downMessage}
                  </div>
                )}
              </div>
            )}
          </div>
          
          {pattern.trigger.invalidation && (
            <div style={{
              borderRadius: '8px',
              background: '#fffbeb',
              border: '1px solid #f59e0b',
              padding: '10px',
              marginTop: '10px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#d97706', fontSize: '13px', fontWeight: '600' }}>
                <span>✗</span>
                <span>Invalidation: {pattern.trigger.invalidation.toLocaleString()}</span>
              </div>
            </div>
          )}
          
          {pattern.trigger.nearest && (
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
              Nearest trigger: {pattern.trigger.nearest.direction?.toUpperCase()} at {pattern.trigger.nearest.level?.toLocaleString()} ({pattern.trigger.nearest.percent}% away)
            </div>
          )}
        </div>
      )}
      
      {/* Alternatives */}
      {pattern.alternatives && pattern.alternatives.length > 0 && (
        <div style={{ paddingTop: '12px', borderTop: '1px solid #e2e8f0' }}>
          <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '8px' }}>Alternatives:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {pattern.alternatives.map((alt, i) => (
              <span 
                key={i}
                style={{
                  fontSize: '12px',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  background: alt.bias === 'bullish' ? '#f0fdf4' :
                              alt.bias === 'bearish' ? '#fef2f2' : '#f1f5f9',
                  color: alt.bias === 'bullish' ? '#15803d' :
                         alt.bias === 'bearish' ? '#dc2626' : '#64748b',
                  fontWeight: '500',
                }}
              >
                {alt.type.replace(/_/g, ' ')} ({(alt.confidence * 100).toFixed(0)}%)
              </span>
            ))}
          </div>
        </div>
      )}
      
      {/* Regime Context */}
      {pattern.regimeContext && (
        <div style={{ paddingTop: '12px', borderTop: '1px solid #e2e8f0', marginTop: '12px', fontSize: '12px', color: '#64748b' }}>
          Regime: {pattern.regimeContext.regime} | Trend: {pattern.regimeContext.trend}
        </div>
      )}
    </div>
  );
}

export default PatternStateCard;
