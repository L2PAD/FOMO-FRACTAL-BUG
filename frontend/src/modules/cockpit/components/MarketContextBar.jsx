/**
 * MarketContextBar — MTF Intelligence Summary
 * =============================================
 * 
 * Shows unified multi-timeframe market understanding.
 * This is the MAIN output — not the chart.
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Minus, Activity, Layers, AlertTriangle } from 'lucide-react';

const ContextBar = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  margin: 0 0 16px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
`;

const TopRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const BiasSummary = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const BiasIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${props => {
    if (props.$bias === 'bullish') return 'rgba(5, 165, 132, 0.15)';
    if (props.$bias === 'bearish') return 'rgba(239, 68, 68, 0.15)';
    return 'rgba(100, 116, 139, 0.15)';
  }};
  color: ${props => {
    if (props.$bias === 'bullish') return '#05A584';
    if (props.$bias === 'bearish') return '#ef4444';
    return '#94a3b8';
  }};
`;

const BiasText = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const BiasTitle = styled.div`
  font-size: 18px;
  font-weight: 800;
  color: ${props => {
    if (props.$bias === 'bullish') return '#05A584';
    if (props.$bias === 'bearish') return '#ef4444';
    return '#e2e8f0';
  }};
  display: flex;
  align-items: center;
  gap: 8px;
`;

const BiasConfidence = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
`;

const MTFSummary = styled.div`
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.4;
`;

const ContextItems = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

const ContextItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
`;

const ContextLabel = styled.span`
  font-size: 10px;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const StateBadge = styled.span`
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  background: ${props => {
    const s = (props.$state || '').toLowerCase();
    if (s.includes('trend_up') || s === 'markup' || s === 'bullish') return 'rgba(5, 165, 132, 0.15)';
    if (s.includes('trend_down') || s === 'markdown' || s === 'bearish') return 'rgba(239, 68, 68, 0.15)';
    if (s.includes('compression')) return 'rgba(245, 158, 11, 0.15)';
    if (s.includes('expansion')) return 'rgba(59, 130, 246, 0.15)';
    return 'rgba(100, 116, 139, 0.15)';
  }};
  color: ${props => {
    const s = (props.$state || '').toLowerCase();
    if (s.includes('trend_up') || s === 'markup' || s === 'bullish') return '#05A584';
    if (s.includes('trend_down') || s === 'markdown' || s === 'bearish') return '#ef4444';
    if (s.includes('compression')) return '#f59e0b';
    if (s.includes('expansion')) return '#3b82f6';
    return '#94a3b8';
  }};
`;

const AlignmentBadge = styled.span`
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  background: ${props => {
    if (props.$type === 'full_bullish') return 'rgba(5, 165, 132, 0.15)';
    if (props.$type === 'full_bearish') return 'rgba(239, 68, 68, 0.15)';
    return 'rgba(245, 158, 11, 0.15)';
  }};
  color: ${props => {
    if (props.$type === 'full_bullish') return '#05A584';
    if (props.$type === 'full_bearish') return '#ef4444';
    return '#f59e0b';
  }};
`;

const TFBreakdown = styled.div`
  display: flex;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
`;

const TFChip = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  color: #94a3b8;

  .tf-name {
    color: #64748b;
  }
  .tf-bias {
    color: ${props => {
      if (props.$bias === 'bullish') return '#05A584';
      if (props.$bias === 'bearish') return '#ef4444';
      return '#94a3b8';
    }};
  }
`;

const formatLabel = (s) => {
  if (!s) return 'Unknown';
  return s.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const MarketContextBar = ({ decision, mtfContext }) => {
  // Use MTF context as primary source if available
  const mtf = mtfContext || {};
  const hasMTF = !!mtf.global_bias;

  // Fallback to decision if no MTF
  const bias = hasMTF ? mtf.global_bias : decision?.bias || 'neutral';
  const confidence = hasMTF ? mtf.confidence : decision?.confidence || 0.5;
  const confPercent = Math.round((confidence || 0.5) * 100);

  const regime = decision?.regime || 'unknown';
  const phase = decision?.market_phase || 'unknown';
  const alignment = hasMTF ? mtf.alignment : decision?.alignment || 'unknown';
  const localContext = mtf.local_context;
  const summary = mtf.summary;
  const tfBreakdown = mtf.tf_breakdown || {};

  if (!decision && !hasMTF) return null;

  const getBiasIcon = () => {
    if (bias === 'bullish') return <TrendingUp size={20} />;
    if (bias === 'bearish') return <TrendingDown size={20} />;
    return <Minus size={20} />;
  };

  const formatAlignment = (a) => {
    const map = {
      'full_bullish': 'Full Bullish',
      'full_bearish': 'Full Bearish',
      'mixed': 'Mixed',
      'neutral': 'Neutral',
    };
    return map[a] || formatLabel(a);
  };

  const formatContext = (ctx) => {
    const map = {
      'relief_bounce': 'Relief Bounce',
      'pullback': 'Pullback',
      'trend_continuation': 'Trend Continuation',
      'compression': 'Compression',
      'reversal_candidate': 'Reversal Candidate',
    };
    return map[ctx] || formatLabel(ctx);
  };

  return (
    <ContextBar data-testid="market-context-bar">
      <TopRow>
        <BiasSummary>
          <BiasIcon $bias={bias}>
            {getBiasIcon()}
          </BiasIcon>
          <BiasText>
            <BiasTitle $bias={bias}>
              {formatLabel(bias)} Bias
              <BiasConfidence>({confPercent}%)</BiasConfidence>
            </BiasTitle>
            {summary && <MTFSummary>{summary}</MTFSummary>}
          </BiasText>
        </BiasSummary>

        <ContextItems>
          <ContextItem>
            <ContextLabel>Regime</ContextLabel>
            <StateBadge $state={regime}>
              {formatLabel(regime)}
            </StateBadge>
          </ContextItem>

          {localContext && localContext !== 'unknown' && (
            <ContextItem>
              <ContextLabel>Context</ContextLabel>
              <StateBadge $state={localContext}>
                {formatContext(localContext)}
              </StateBadge>
            </ContextItem>
          )}

          <ContextItem>
            <ContextLabel>Alignment</ContextLabel>
            <AlignmentBadge $type={alignment}>
              {formatAlignment(alignment)}
            </AlignmentBadge>
          </ContextItem>

          {phase && phase !== 'unknown' && (
            <ContextItem>
              <ContextLabel>Phase</ContextLabel>
              <StateBadge $state={phase}>
                {formatLabel(phase)}
              </StateBadge>
            </ContextItem>
          )}
        </ContextItems>
      </TopRow>

      {/* TF Breakdown — per-timeframe view */}
      {Object.keys(tfBreakdown).length > 0 && (
        <TFBreakdown>
          {Object.entries(tfBreakdown).map(([tf, data]) => (
            <TFChip key={tf} $bias={data.bias}>
              <span className="tf-name">{tf}</span>
              <span className="tf-bias">{formatLabel(data.bias)}</span>
            </TFChip>
          ))}
        </TFBreakdown>
      )}
    </ContextBar>
  );
};

export default MarketContextBar;
