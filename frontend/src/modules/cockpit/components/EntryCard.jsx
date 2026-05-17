/**
 * EntryCard — Trade Setup Display
 * ================================
 * 
 * Shows trade setup ONLY when conditions are met:
 * - Pattern is confirmed (lifecycle = confirmed_up/confirmed_down)
 * - Probability threshold met (> 60%)
 * - Confidence is sufficient
 * 
 * Otherwise shows "WAIT" state.
 */

import React from 'react';
import { Target, AlertTriangle, TrendingUp, TrendingDown, Clock } from 'lucide-react';

const EntryCard = ({ setup, intelligence }) => {
  // Check if we have a valid setup
  const hasSetup = setup && setup.available;
  
  // If no setup or waiting
  if (!hasSetup) {
    const reason = setup?.reason || 'No trade setup available';
    const advice = setup?.advice || 'Waiting for confirmation';
    
    // Determine specific reason why no setup
    const getDetailedReason = () => {
      if (setup?.lifecycle === 'forming') {
        return {
          title: 'Pattern Forming',
          description: 'Pattern is still in early formation phase. Key structure points have not completed yet.',
          icon: 'forming',
          color: '#f59e0b'
        };
      }
      if (setup?.lifecycle === 'developing') {
        return {
          title: 'Pattern Developing', 
          description: 'Pattern structure is developing but not yet confirmed. Watch for breakout or breakdown.',
          icon: 'developing',
          color: '#3b82f6'
        };
      }
      if (setup?.lifecycle === 'invalidated') {
        return {
          title: 'Pattern Invalidated',
          description: 'Pattern structure has been broken. The setup is no longer valid for entry.',
          icon: 'invalidated',
          color: '#ef4444'
        };
      }
      if (setup?.confidence_low) {
        return {
          title: 'Low Confidence',
          description: `Confidence level (${Math.round((setup?.confidence || 0) * 100)}%) is below the required threshold for execution.`,
          icon: 'low_confidence',
          color: '#f59e0b'
        };
      }
      if (setup?.context_mismatch) {
        return {
          title: 'Context Mismatch',
          description: 'Current market context does not align well with the pattern. This reduces success probability.',
          icon: 'context',
          color: '#f97316'
        };
      }
      if (setup?.range_bound) {
        return {
          title: 'Range Bound',
          description: 'Price is currently range-bound without clear direction. Wait for breakout from range.',
          icon: 'range',
          color: '#64748b'
        };
      }
      return {
        title: 'Waiting for Signal',
        description: reason || 'No clear trade signal at the moment. The system is analyzing market conditions.',
        icon: 'waiting',
        color: '#64748b'
      };
    };
    
    const details = getDetailedReason();
    
    return (
      <div 
        data-testid="entry-card-wait"
        style={{
          background: '#0a0f14',
          border: `1px solid ${details.color}30`,
          borderRadius: '12px',
          padding: '16px',
          marginTop: '12px',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: `${details.color}20`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Clock size={16} color={details.color} />
            </div>
            <span style={{
              fontSize: '12px',
              fontWeight: 700,
              color: details.color,
              textTransform: 'uppercase',
            }}>
              {details.title}
            </span>
          </div>
          
          <span style={{
            fontSize: '10px',
            fontWeight: 600,
            color: '#475569',
            padding: '4px 8px',
            background: '#1e293b',
            borderRadius: '4px',
          }}>
            NO ENTRY
          </span>
        </div>
        
        {/* Description */}
        <div style={{ 
          fontSize: '13px', 
          color: '#94a3b8', 
          lineHeight: 1.5,
          marginBottom: '12px',
        }}>
          {details.description}
        </div>
        
        {/* What to watch */}
        <div style={{
          padding: '10px 12px',
          background: '#0f172a',
          borderRadius: '8px',
          borderLeft: `3px solid ${details.color}`,
        }}>
          <div style={{
            fontSize: '10px',
            fontWeight: 600,
            color: '#64748b',
            textTransform: 'uppercase',
            marginBottom: '6px',
          }}>
            What to Watch
          </div>
          <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
            {advice || 'Monitor for confirmation signals before considering entry'}
          </div>
        </div>
        
        {/* Additional context if available */}
        {(setup?.pattern || setup?.bias) && (
          <div style={{
            display: 'flex',
            gap: '12px',
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid #1e293b',
          }}>
            {setup?.pattern && (
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '2px' }}>Pattern</div>
                <div style={{ fontSize: '12px', color: '#ffffff', fontWeight: 600 }}>
                  {setup.pattern.replace(/_/g, ' ')}
                </div>
              </div>
            )}
            {setup?.bias && (
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '2px' }}>Bias</div>
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 600,
                  color: setup.bias === 'bullish' ? '#22c55e' : setup.bias === 'bearish' ? '#ef4444' : '#94a3b8',
                }}>
                  {setup.bias.charAt(0).toUpperCase() + setup.bias.slice(1)}
                </div>
              </div>
            )}
            {setup?.confidence !== undefined && (
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '2px' }}>Confidence</div>
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 600,
                  color: setup.confidence >= 0.6 ? '#22c55e' : setup.confidence >= 0.4 ? '#f59e0b' : '#ef4444',
                }}>
                  {Math.round(setup.confidence * 100)}%
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // We have a valid setup
  const isLong = setup.side === 'LONG';
  const isShort = setup.side === 'SHORT';
  const isBreakout = setup.side === 'BREAKOUT';

  // Color based on direction
  const sideColor = isLong ? '#22c55e' : isShort ? '#ef4444' : '#f59e0b';
  const sideBg = isLong ? 'rgba(34, 197, 94, 0.1)' : isShort ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)';

  return (
    <div 
      data-testid="entry-card"
      style={{
        background: '#0a0f14',
        border: `1px solid ${sideColor}30`,
        borderRadius: '12px',
        overflow: 'hidden',
        marginTop: '12px',
      }}
    >
      {/* Header */}
      <div 
        style={{
          padding: '10px 16px',
          background: sideBg,
          borderBottom: `1px solid ${sideColor}30`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={14} color={sideColor} />
          <span style={{
            fontSize: '11px',
            fontWeight: 700,
            color: sideColor,
            textTransform: 'uppercase',
          }}>
            Trade Setup
          </span>
        </div>
        
        <span style={{
          fontSize: '12px',
          fontWeight: 700,
          color: sideColor,
          padding: '2px 8px',
          borderRadius: '4px',
          background: sideBg,
        }}>
          {setup.side}
        </span>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {/* Pattern Type */}
        <div style={{
          fontSize: '13px',
          fontWeight: 600,
          color: '#ffffff',
          marginBottom: '12px',
        }}>
          {setup.pattern}
        </div>

        {/* For BREAKOUT (both directions) */}
        {isBreakout && setup.long_setup && setup.short_setup ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {/* Long Setup */}
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: 'rgba(34, 197, 94, 0.05)',
              border: '1px solid rgba(34, 197, 94, 0.2)',
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                marginBottom: '8px',
              }}>
                <TrendingUp size={12} color="#22c55e" />
                <span style={{ fontSize: '10px', fontWeight: 600, color: '#22c55e' }}>LONG</span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Entry: <span style={{ color: '#22c55e', fontWeight: 600 }}>
                  {setup.long_setup.entry?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Stop: <span style={{ color: '#ef4444' }}>
                  {setup.long_setup.stop?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Target: <span style={{ color: '#60a5fa' }}>
                  {setup.long_setup.target?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '10px', color: '#64748b' }}>
                R:R {setup.long_setup.rr_ratio}
              </div>
            </div>

            {/* Short Setup */}
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.05)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                marginBottom: '8px',
              }}>
                <TrendingDown size={12} color="#ef4444" />
                <span style={{ fontSize: '10px', fontWeight: 600, color: '#ef4444' }}>SHORT</span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Entry: <span style={{ color: '#ef4444', fontWeight: 600 }}>
                  {setup.short_setup.entry?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Stop: <span style={{ color: '#22c55e' }}>
                  {setup.short_setup.stop?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Target: <span style={{ color: '#60a5fa' }}>
                  {setup.short_setup.target?.toLocaleString()}
                </span>
              </div>
              
              <div style={{ fontSize: '10px', color: '#64748b' }}>
                R:R {setup.short_setup.rr_ratio}
              </div>
            </div>
          </div>
        ) : (
          /* Single Direction Setup */
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {/* Entry */}
            <div>
              <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '4px' }}>
                Entry
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: sideColor }}>
                {setup.entry?.toLocaleString()}
              </div>
              <div style={{ fontSize: '10px', color: '#475569' }}>
                {setup.entry_type}
              </div>
            </div>

            {/* Stop */}
            <div>
              <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '4px' }}>
                Stop
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#ef4444' }}>
                {setup.stop?.toLocaleString()}
              </div>
            </div>

            {/* Target */}
            <div>
              <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '4px' }}>
                Target
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#60a5fa' }}>
                {setup.target?.toLocaleString()}
              </div>
            </div>
          </div>
        )}

        {/* R:R Ratio */}
        {setup.rr_ratio !== undefined && !isBreakout && (
          <div style={{
            marginTop: '12px',
            padding: '8px',
            borderRadius: '6px',
            background: setup.rr_ratio >= 2 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(245, 158, 11, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Risk/Reward:</span>
            <span style={{
              fontSize: '13px',
              fontWeight: 700,
              color: setup.rr_ratio >= 2 ? '#22c55e' : '#f59e0b',
            }}>
              1:{setup.rr_ratio}
            </span>
          </div>
        )}

        {/* Notes */}
        {setup.notes && setup.notes.length > 0 && (
          <div style={{
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid #1e293b',
          }}>
            {setup.notes.map((note, idx) => (
              <div 
                key={idx}
                style={{
                  fontSize: '11px',
                  color: '#64748b',
                  marginBottom: '4px',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '6px',
                }}
              >
                <span style={{ color: '#475569' }}>•</span>
                {note}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default EntryCard;
