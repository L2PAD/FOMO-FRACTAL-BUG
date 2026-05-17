/**
 * PatternIntelligenceCard — Unified Decision Scorecard V2
 * ========================================================
 * 
 * PRINCIPLE: User sees in 3 seconds:
 * 1. What's happening (market state + pattern + lifecycle)
 * 2. What it means (core idea / next action)
 * 3. What to do (watch levels)
 * 4. Why system thinks so (probability + evidence)
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, Target, AlertCircle, ChevronRight, Clock } from 'lucide-react';

// Format pattern type
const formatType = (type) => {
  if (!type) return 'Unknown';
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Format lifecycle state
const formatLifecycle = (state) => {
  if (!state) return 'Forming';
  return state.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Get lifecycle color
const getLifecycleColor = (state) => {
  if (state === 'confirmed_up') return '#22c55e';
  if (state === 'confirmed_down') return '#ef4444';
  if (state === 'invalidated') return '#64748b';
  return '#94a3b8';
};

// Get header background based on lifecycle
const getHeaderBackground = (state) => {
  if (state === 'confirmed_up') return 'rgba(34, 197, 94, 0.1)';
  if (state === 'confirmed_down') return 'rgba(239, 68, 68, 0.1)';
  if (state === 'invalidated') return 'rgba(100, 116, 139, 0.1)';
  return 'rgba(245, 158, 11, 0.1)'; // forming = yellow
};

// Get header border based on lifecycle
const getHeaderBorder = (state) => {
  if (state === 'confirmed_up') return '#22c55e';
  if (state === 'confirmed_down') return '#ef4444';
  if (state === 'invalidated') return '#64748b';
  return '#f59e0b'; // forming
};

const PatternIntelligenceCard = ({ data }) => {
  if (!data) return null;

  const { 
    market_state, 
    dominant, 
    mtf, 
    next_action, 
    watch_levels,
    probabilities,
    live_probability,
    bayesian_probability,
    similarity,
    performance  // NEW: Performance stats
  } = data;

  const lifecycle = dominant?.lifecycle || 'forming';

  return (
    <div 
      data-testid="pattern-intelligence-card"
      style={{
        background: '#0a0f14',
        border: '1px solid #1e293b',
        borderRadius: '12px',
        overflow: 'hidden',
        marginTop: '12px',
      }}
    >
      {/* 1. HEADER — Market State + Pattern + Lifecycle */}
      <div 
        style={{
          padding: '12px 16px',
          background: getHeaderBackground(lifecycle),
          borderBottom: `2px solid ${getHeaderBorder(lifecycle)}`,
        }}
      >
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: '#94a3b8',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          marginBottom: '4px',
        }}>
          {market_state || 'ANALYZING'}
        </div>
        
        {dominant && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span style={{
              fontSize: '16px',
              fontWeight: 700,
              color: '#ffffff',
            }}>
              {formatType(dominant.type)}
            </span>
            <span 
              style={{
                fontSize: '10px',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '2px 8px',
                borderRadius: '4px',
                background: `${getLifecycleColor(lifecycle)}20`,
                color: getLifecycleColor(lifecycle),
              }}
            >
              {formatLifecycle(lifecycle)}
            </span>
          </div>
        )}
      </div>

      <div style={{ padding: '12px 16px' }}>
        {/* 2. CORE IDEA — What it means */}
        {next_action && (
          <div style={{
            fontSize: '13px',
            color: '#ffffff',
            marginBottom: '12px',
            lineHeight: 1.4,
          }}>
            {next_action}
          </div>
        )}

        {/* 3. KEY NUMBERS — Confidence + MTF */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: '#64748b',
          marginBottom: '12px',
        }}>
          <span>
            Conf: <span style={{ color: '#f59e0b', fontWeight: 600 }}>
              {Math.round((dominant?.confidence || 0) * 100)}%
            </span>
          </span>
          {mtf && (
            <span style={{ color: '#60a5fa' }}>
              {mtf.timeframe}: {mtf.state}
            </span>
          )}
        </div>

        {/* 4. WATCH LEVELS — What to watch */}
        {watch_levels && watch_levels.length > 0 && (
          <div style={{ marginBottom: '12px' }}>
            {watch_levels.slice(0, 2).map((lvl, idx) => (
              <div 
                key={idx}
                style={{
                  fontSize: '12px',
                  color: lvl.type === 'breakout_up' ? '#22c55e' : 
                         lvl.type === 'breakdown' ? '#ef4444' : '#94a3b8',
                  marginBottom: '4px',
                }}
              >
                {lvl.type === 'breakout_up' ? '▲' : '▼'} {Math.round(lvl.price || 0).toLocaleString()}
                {lvl.label && <span style={{ color: '#64748b', marginLeft: '6px' }}>— {lvl.label}</span>}
              </div>
            ))}
          </div>
        )}

        {/* 5. LIVE PROBABILITY — Current edge */}
        {(live_probability || probabilities) && (
          <div style={{
            borderTop: '1px solid #1e293b',
            paddingTop: '12px',
            marginBottom: '8px',
          }}>
            <div style={{
              fontSize: '10px',
              fontWeight: 600,
              color: '#64748b',
              marginBottom: '6px',
              textTransform: 'uppercase',
            }}>
              {live_probability ? 'Live Probability' : 'Probability'}
            </div>
            
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <TrendingUp size={12} color="#22c55e" />
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#22c55e' }}>
                  {Math.round(((live_probability?.breakout_up || probabilities?.breakout_up) || 0) * 100)}%
                </span>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <TrendingDown size={12} color="#ef4444" />
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#ef4444' }}>
                  {Math.round(((live_probability?.breakdown || probabilities?.breakdown) || 0) * 100)}%
                </span>
              </div>
              
              {(probabilities?.edge || live_probability?.edge) && (
                <span style={{
                  marginLeft: 'auto',
                  fontSize: '10px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  background: (probabilities?.edge || live_probability?.edge) === 'bullish' 
                    ? 'rgba(34, 197, 94, 0.15)' 
                    : 'rgba(239, 68, 68, 0.15)',
                  color: (probabilities?.edge || live_probability?.edge) === 'bullish' 
                    ? '#22c55e' 
                    : '#ef4444',
                }}>
                  {probabilities?.edge || live_probability?.edge} edge
                </span>
              )}
            </div>
          </div>
        )}

        {/* 6. BAYESIAN / PRIOR (if available) */}
        {bayesian_probability && (
          <div style={{
            fontSize: '10px',
            color: '#475569',
            marginBottom: '8px',
          }}>
            prior: ▲{Math.round((bayesian_probability.prior_up || 0) * 100)}% → 
            updated: ▲{Math.round((bayesian_probability.posterior_up || 0) * 100)}%
          </div>
        )}

        {/* 7. WHY — Evidence tags */}
        {bayesian_probability?.evidence && bayesian_probability.evidence.length > 0 && (
          <div style={{
            fontSize: '10px',
            color: '#475569',
          }}>
            {bayesian_probability.evidence.join(', ')}
          </div>
        )}

        {/* 8. PERFORMANCE — Self-learning stats */}
        {performance && (performance.win_rate !== null || performance.total_tracked > 0) && (
          <div style={{
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid #1e293b',
          }}>
            <div style={{
              fontSize: '10px',
              fontWeight: 600,
              color: '#64748b',
              marginBottom: '6px',
              textTransform: 'uppercase',
            }}>
              Historical Performance
            </div>
            
            {/* Current pattern stats (if available) */}
            {performance.win_rate !== null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Target size={12} color={performance.win_rate >= 60 ? '#22c55e' : performance.win_rate >= 45 ? '#f59e0b' : '#ef4444'} />
                  <span style={{ 
                    fontSize: '13px', 
                    fontWeight: 600, 
                    color: performance.win_rate >= 60 ? '#22c55e' : performance.win_rate >= 45 ? '#f59e0b' : '#ef4444',
                  }}>
                    {performance.win_rate}% win rate
                  </span>
                </div>
                
                <span style={{ 
                  fontSize: '11px', 
                  color: '#64748b',
                }}>
                  ({performance.samples} trades)
                </span>
                
                {performance.weight !== 1.0 && (
                  <span style={{
                    marginLeft: 'auto',
                    fontSize: '10px',
                    fontWeight: 600,
                    color: performance.weight > 1 ? '#22c55e' : '#ef4444',
                  }}>
                    {performance.weight > 1 ? '↑' : '↓'} {Math.round((performance.weight - 1) * 100)}% weight
                  </span>
                )}
              </div>
            )}
            
            {/* Show top patterns if no data for current pattern */}
            {performance.win_rate === null && performance.top_patterns && performance.top_patterns.length > 0 && (
              <div>
                <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '4px' }}>
                  No data for {performance.pattern_type}. Top tracked:
                </div>
                {performance.top_patterns.slice(0, 2).map((p, idx) => (
                  <div key={idx} style={{ 
                    fontSize: '11px', 
                    color: p.winrate >= 60 ? '#22c55e' : '#f59e0b',
                    marginBottom: '2px',
                  }}>
                    {p.pattern}: {p.winrate}% ({p.samples} trades)
                  </div>
                ))}
              </div>
            )}
            
            {/* Total tracked */}
            {performance.total_tracked > 0 && (
              <div style={{ 
                fontSize: '10px', 
                color: '#475569',
                marginTop: '4px',
              }}>
                {performance.total_tracked} total setups tracked
              </div>
            )}
          </div>
        )}

        {/* Similarity count */}
        {similarity && similarity.count > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginTop: '8px',
            paddingTop: '8px',
            borderTop: '1px solid #1e293b',
            fontSize: '11px',
            color: '#7c3aed',
          }}>
            <Clock size={12} />
            {similarity.count} similar patterns in history
          </div>
        )}
      </div>
    </div>
  );
};

export default PatternIntelligenceCard;
