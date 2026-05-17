/**
 * Overview Tab — Decision Layer
 * ==============================
 * 
 * "Що відбувається + що робити"
 * 
 * Contains:
 * - Market State Bar (Macro/Mid/Short)
 * - Core Insight (Interpretation)
 * - Dominant Pattern + Lifecycle
 * - Probability Block
 * - What to Watch (levels)
 * - Mini Chart
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Minus, Target, Eye, AlertCircle, BarChart2, CheckCircle, XCircle, Zap, AlertTriangle, AlertOctagon } from 'lucide-react';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Card = styled.div`
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
`;

const SectionTitle = styled.div`
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
`;

const MarketStateBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 14px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
`;

const StateBadge = styled.span`
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  background: transparent;
  color: ${p => p.$type === 'bullish' ? '#16a34a' :
                p.$type === 'bearish' ? '#dc2626' :
                '#475569'};
`;

const InsightBox = styled.div`
  padding: 14px 16px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;

  .line1 {
    font-size: 14px;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 6px;
  }

  .line2 {
    font-size: 13px;
    color: #64748b;
    line-height: 1.5;
  }
`;

const PatternCard = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: transparent;
  border: 1px solid ${p => p.$direction === 'bullish' ? 'rgba(34, 197, 94, 0.35)' :
                           p.$direction === 'bearish' ? 'rgba(239, 68, 68, 0.35)' :
                           '#e2e8f0'};
  border-radius: 8px;
`;

const PatternName = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  text-transform: capitalize;
`;

const ContextFitBadge = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
`;

const ContextFitLabel = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;

  .icon {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    color: ${p => p.$label === 'HIGH'
      ? '#16a34a'
      : p.$label === 'LOW'
      ? '#dc2626'
      : '#64748b'};
  }

  .text {
    .title {
      font-size: 13px;
      font-weight: 600;
      color: #0f172a;
    }
    .subtitle {
      font-size: 11px;
      color: #64748b;
      margin-top: 2px;
    }
  }
`;

const ContextFitScore = styled.div`
  text-align: right;

  .value {
    font-size: 22px;
    font-weight: 700;
    color: ${p => p.$label === 'HIGH'
      ? '#16a34a'
      : p.$label === 'LOW'
      ? '#dc2626'
      : '#0f172a'};
  }

  .label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #94a3b8;
  }
`;

const ContextReasons = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;

  .reason {
    padding: 3px 8px;
    background: transparent;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-size: 11px;
    color: #475569;
    display: flex;
    align-items: center;
    gap: 4px;

    &.positive {
      background: transparent;
      border-color: rgba(34, 197, 94, 0.35);
      color: #16a34a;
    }

    &.negative {
      background: transparent;
      border-color: rgba(239, 68, 68, 0.35);
      color: #dc2626;
    }
  }
`;

const LifecycleBadge = styled.span`
  padding: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  background: transparent;
  color: ${p => p.$stage === 'confirmed' || p.$stage === 'confirmed_up' || p.$stage === 'confirmed_down'
    ? '#16a34a'
    : p.$stage === 'invalidated'
    ? '#dc2626'
    : '#2563eb'};
    ? '#ef4444'
    : '#3b82f6'};
`;

const DriftAlert = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: transparent;
  border: 1px solid ${p => p.$severity === 'HIGH'
    ? 'rgba(239, 68, 68, 0.35)'
    : p.$severity === 'MEDIUM'
    ? 'rgba(249, 115, 22, 0.35)'
    : 'rgba(234, 179, 8, 0.35)'};
  border-radius: 8px;

  .icon {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    color: ${p => p.$severity === 'HIGH'
      ? '#ef4444'
      : p.$severity === 'MEDIUM'
      ? '#f97316'
      : '#eab308'};
  }

  .content {
    flex: 1;

    .title {
      font-size: 13px;
      font-weight: 600;
      color: ${p => p.$severity === 'HIGH'
        ? '#dc2626'
        : p.$severity === 'MEDIUM'
        ? '#ea580c'
        : '#ca8a04'};
      margin-bottom: 2px;
    }

    .message {
      font-size: 11px;
      color: #64748b;
    }
  }

  .badge {
    padding: 0;
    background: transparent;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    color: ${p => p.$severity === 'HIGH'
      ? '#dc2626'
      : p.$severity === 'MEDIUM'
      ? '#ea580c'
      : '#ca8a04'};
  }
`;

const ProbabilityRow = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const ProbabilityCard = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: transparent;
  border: 1px solid ${p => p.$type === 'up' ? 'rgba(34, 197, 94, 0.35)' : 'rgba(239, 68, 68, 0.35)'};
  border-radius: 8px;

  .label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: ${p => p.$type === 'up' ? '#16a34a' : '#dc2626'};
  }

  .value {
    font-size: 22px;
    font-weight: 700;
    color: ${p => p.$type === 'up' ? '#16a34a' : '#dc2626'};
  }
`;

const WatchLevels = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const LevelCard = styled.div`
  padding: 12px 14px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-left: 3px solid ${p => p.$type === 'breakout' ? '#22c55e' : '#ef4444'};
  border-radius: 8px;

  .label {
    font-size: 10px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 4px;
  }

  .price {
    font-size: 16px;
    font-weight: 700;
    color: ${p => p.$type === 'breakout' ? '#16a34a' : '#dc2626'};
  }

  .hint {
    font-size: 11px;
    color: #94a3b8;
    margin-top: 4px;
  }
`;

const MiniChartPlaceholder = styled.div`
  height: 180px;
  background: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 12px;
  border: 1px dashed #e2e8f0;
`;

const OverviewTab = ({ 
  setupData, 
  mtfContext, 
  primaryPattern, 
  decision, 
  levels,
  selectedTF,
  contextFit,
  context,
  historical,
  probabilityV3,
  regimeDrift,
}) => {
  // Extract market state
  const marketState = mtfContext?.summary || {};
  const macro = marketState.macro || 'Neutral';
  const mid = marketState.mid || 'Developing';
  const short = marketState.short || 'Consolidation';
  
  // Context Fit data
  const fitLabel = contextFit?.label || 'MEDIUM';
  const fitScore = contextFit?.score || 1.0;
  const fitReasons = contextFit?.reasons || [];
  const fitRecommendation = contextFit?.recommendation || '';
  const fitAligned = contextFit?.aligned ?? true;
  
  // Market context
  const regime = context?.regime || 'range';
  const ctxStructure = context?.structure || 'neutral';
  const impulse = context?.impulse || 'none';
  const volatility = context?.volatility || 'mid';
  
  // Historical Context data
  const histFit = historical?.fit || {};
  const histLabel = histFit?.label || 'INSUFFICIENT';
  const histWinrate = histFit?.winrate;
  const histSamples = histFit?.samples || 0;
  const histSummary = historical?.summary || 'No historical data available';
  const histStats = historical?.stats || {};
  
  // Drift data (from probability V3 or historical)
  const drift = probabilityV3?.drift || historical?.drift || {};
  const driftLabel = drift?.label || 'INSUFFICIENT';
  const driftDelta = drift?.delta;
  const driftMessage = drift?.message || '';
  
  // Expectation data
  const expectation = probabilityV3?.expectation || historical?.expectation || {};
  const expectedMove = expectation?.move_pct;
  const expectedTime = expectation?.resolution_h;
  const expectationLabel = expectation?.label || '';
  const expectationConfidence = expectation?.confidence || 'LOW';
  
  // Final probability V3 data
  const finalConfidence = probabilityV3?.final_confidence;
  const baseConfidence = probabilityV3?.base_confidence;
  const totalMultiplier = probabilityV3?.total_multiplier;
  
  // Core insight
  const line1 = setupData?.interpretation || 
    (primaryPattern?.type ? `${primaryPattern.type} pattern active` : 'Analyzing market structure');
  const line2 = setupData?.what_next || setupData?.narrative?.what_next || 
    'Waiting for confirmation signal';
  
  // Pattern info
  const patternType = primaryPattern?.type?.replace(/_/g, ' ') || 'No pattern';
  const lifecycle = primaryPattern?.lifecycle || 'forming';
  const confidence = Math.round((primaryPattern?.confidence || 0) * 100);
  const direction = primaryPattern?.direction || decision?.bias || 'neutral';
  
  // Probability
  const probUp = Math.round((decision?.bullish_prob || setupData?.probability?.up || 0.5) * 100);
  const probDown = Math.round((decision?.bearish_prob || setupData?.probability?.down || 0.5) * 100);
  
  // Levels
  const resistances = levels?.filter(l => l.type === 'resistance') || [];
  const supports = levels?.filter(l => l.type === 'support') || [];
  const breakoutLevel = resistances[0]?.price || setupData?.breakout_level;
  const breakdownLevel = supports[0]?.price || setupData?.breakdown_level;
  
  return (
    <Container data-testid="overview-tab">
      {/* Market State Bar */}
      <MarketStateBar data-testid="market-state-bar">
        <span style={{ color: '#94a3b8', fontSize: '11px' }}>Macro:</span>
        <StateBadge $type={macro.toLowerCase().includes('bull') ? 'bullish' : 
                          macro.toLowerCase().includes('bear') ? 'bearish' : 'neutral'}>
          {macro}
        </StateBadge>
        <span style={{ color: '#475569' }}>·</span>
        <span style={{ color: '#94a3b8', fontSize: '11px' }}>Mid-term:</span>
        <StateBadge $type={mid.toLowerCase().includes('bull') ? 'bullish' : 
                          mid.toLowerCase().includes('bear') ? 'bearish' : 'neutral'}>
          {mid}
        </StateBadge>
        <span style={{ color: '#475569' }}>·</span>
        <span style={{ color: '#94a3b8', fontSize: '11px' }}>Short-term:</span>
        <StateBadge $type={short.toLowerCase().includes('bull') ? 'bullish' : 
                          short.toLowerCase().includes('bear') ? 'bearish' : 'neutral'}>
          {short}
        </StateBadge>
      </MarketStateBar>
      
      {/* Core Insight */}
      <Card>
        <SectionTitle>Core Insight</SectionTitle>
        <InsightBox data-testid="core-insight">
          <div className="line1">{line1}</div>
          <div className="line2">{line2}</div>
        </InsightBox>
      </Card>
      
      {/* Context Fit Block - NEW */}
      <Card>
        <SectionTitle>
          <Zap size={12} style={{ display: 'inline', marginRight: '6px' }} />
          Context Fit
        </SectionTitle>
        <ContextFitBadge $label={fitLabel} data-testid="context-fit-badge">
          <ContextFitLabel $label={fitLabel}>
            <div className="icon">
              {fitLabel === 'HIGH' && <CheckCircle size={18} />}
              {fitLabel === 'MEDIUM' && <Target size={18} />}
              {fitLabel === 'LOW' && <XCircle size={18} />}
            </div>
            <div className="text">
              <div className="title">
                {fitAligned ? 'Pattern aligned with context' : 'Pattern conflicts with context'}
              </div>
              <div className="subtitle">
                {regime.charAt(0).toUpperCase() + regime.slice(1)} · {ctxStructure.charAt(0).toUpperCase() + ctxStructure.slice(1)} structure · {volatility} volatility
              </div>
            </div>
          </ContextFitLabel>
          <ContextFitScore $label={fitLabel}>
            <div className="value">{Math.round(fitScore * 100)}%</div>
            <div className="label">{fitLabel}</div>
          </ContextFitScore>
        </ContextFitBadge>
        {fitReasons.length > 0 && (
          <ContextReasons data-testid="context-reasons">
            {fitReasons.slice(0, 4).map((reason, i) => (
              <span 
                key={i} 
                className={`reason ${reason.includes('+') || reason.toLowerCase().includes('aligned') || reason.toLowerCase().includes('supports') ? 'positive' : 
                                     reason.includes('-') || reason.toLowerCase().includes('weak') || reason.toLowerCase().includes('conflict') ? 'negative' : ''}`}
              >
                {reason.includes('+') || reason.toLowerCase().includes('aligned') || reason.toLowerCase().includes('supports') || reason.toLowerCase().includes('optimal') 
                  ? <CheckCircle size={10} /> 
                  : reason.includes('-') || reason.toLowerCase().includes('weak') || reason.toLowerCase().includes('conflict')
                  ? <XCircle size={10} />
                  : null}
                {reason}
              </span>
            ))}
          </ContextReasons>
        )}
        {fitRecommendation && (
          <div style={{ marginTop: '12px', padding: '10px', background: '#f8fafc', borderRadius: '8px', fontSize: '12px', color: '#475569' }}>
            {fitRecommendation}
          </div>
        )}
      </Card>
      
      {/* REGIME DRIFT ALERT — Shows when context has changed */}
      {regimeDrift?.drift_detected && regimeDrift?.severity !== 'NONE' && (
        <DriftAlert $severity={regimeDrift.severity} data-testid="regime-drift-alert">
          <div className="icon">
            {regimeDrift.severity === 'HIGH' && <AlertOctagon size={20} />}
            {regimeDrift.severity === 'MEDIUM' && <AlertTriangle size={20} />}
            {regimeDrift.severity === 'LOW' && <AlertCircle size={20} />}
          </div>
          <div className="content">
            <div className="title">
              {regimeDrift.severity === 'HIGH' && 'Context Changed — Re-evaluate'}
              {regimeDrift.severity === 'MEDIUM' && 'Context Shifted — Monitor'}
              {regimeDrift.severity === 'LOW' && 'Minor Context Change'}
            </div>
            <div className="message">
              {regimeDrift.changes?.map((c, i) => (
                <span key={i}>
                  {c.field}: {c.from} → {c.to}
                  {i < regimeDrift.changes.length - 1 && ' · '}
                </span>
              ))}
            </div>
          </div>
          <div className="badge">{regimeDrift.severity}</div>
        </DriftAlert>
      )}
      
      {/* Historical Fit Block - Pattern × Context × History */}
      <Card>
        <SectionTitle>
          <BarChart2 size={12} style={{ display: 'inline', marginRight: '6px' }} />
          Historical Performance
        </SectionTitle>
        <ContextFitBadge 
          $label={histLabel === 'STRONG' ? 'HIGH' : histLabel === 'WEAK' || histLabel === 'POOR' ? 'LOW' : 'MEDIUM'} 
          data-testid="historical-fit-badge"
        >
          <ContextFitLabel $label={histLabel === 'STRONG' ? 'HIGH' : histLabel === 'WEAK' || histLabel === 'POOR' ? 'LOW' : 'MEDIUM'}>
            <div className="icon">
              {(histLabel === 'STRONG' || histLabel === 'GOOD') && <CheckCircle size={18} />}
              {histLabel === 'NEUTRAL' && <Target size={18} />}
              {(histLabel === 'WEAK' || histLabel === 'POOR') && <XCircle size={18} />}
              {histLabel === 'INSUFFICIENT' && <AlertCircle size={18} />}
            </div>
            <div className="text">
              <div className="title">
                {histLabel === 'STRONG' ? 'Strong historical performance' :
                 histLabel === 'GOOD' ? 'Good historical track record' :
                 histLabel === 'NEUTRAL' ? 'Average historical performance' :
                 histLabel === 'WEAK' ? 'Below average historically' :
                 histLabel === 'POOR' ? 'Poor historical performance' :
                 'Insufficient historical data'}
              </div>
              <div className="subtitle">
                {histSamples > 0 ? `${histSamples} similar setups analyzed` : 'Need 10+ samples for analysis'}
                {histStats?.avg_move_pct && ` · Avg move: ${histStats.avg_move_pct}%`}
                {histStats?.avg_resolution_h && ` · Avg time: ${histStats.avg_resolution_h}h`}
              </div>
            </div>
          </ContextFitLabel>
          <ContextFitScore $label={histLabel === 'STRONG' ? 'HIGH' : histLabel === 'WEAK' || histLabel === 'POOR' ? 'LOW' : 'MEDIUM'}>
            {histWinrate !== null && histWinrate !== undefined ? (
              <>
                <div className="value">{Math.round(histWinrate * 100)}%</div>
                <div className="label">winrate</div>
              </>
            ) : (
              <>
                <div className="value" style={{ fontSize: '16px' }}>N/A</div>
                <div className="label">winrate</div>
              </>
            )}
          </ContextFitScore>
        </ContextFitBadge>
        {histSummary && histLabel !== 'INSUFFICIENT' && (
          <div style={{ marginTop: '12px', padding: '10px 12px', background: 'transparent', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px', color: '#475569' }}>
            {histLabel === 'STRONG' || histLabel === 'GOOD' 
              ? '✓ ' : histLabel === 'WEAK' || histLabel === 'POOR' 
              ? '✗ ' : '○ '}
            {histSummary}
          </div>
        )}
        
        {/* Drift + Expectation Row */}
        {(driftLabel !== 'INSUFFICIENT' || expectedMove) && (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: expectedMove ? '1fr 1fr' : '1fr',
            gap: '10px',
            marginTop: '12px' 
          }}>
            {/* Drift Block */}
            {driftLabel !== 'INSUFFICIENT' && (
              <div style={{
                padding: '12px',
                background: 'transparent',
                borderRadius: '8px',
                border: `1px solid ${driftLabel.includes('IMPROVING') ? 'rgba(34, 197, 94, 0.35)' :
                                     driftLabel.includes('DEGRADING') ? 'rgba(239, 68, 68, 0.35)' :
                                     '#e2e8f0'}`,
              }} data-testid="drift-block">
                <div style={{ fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Recent Trend
                </div>
                <div style={{ 
                  fontSize: '14px', 
                  fontWeight: 700, 
                  color: driftLabel.includes('IMPROVING') ? '#16a34a' :
                         driftLabel.includes('DEGRADING') ? '#dc2626' : '#475569',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {driftLabel.includes('IMPROVING') && '↑'}
                  {driftLabel.includes('DEGRADING') && '↓'}
                  {driftLabel === 'STABLE' && '→'}
                  {driftLabel.replace('STRONG_', '')}
                  {driftDelta && (
                    <span style={{ fontSize: '11px', fontWeight: 500, opacity: 0.8 }}>
                      ({driftDelta > 0 ? '+' : ''}{Math.round(driftDelta * 100)}%)
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {/* Expectation Block */}
            {expectedMove && (
              <div style={{
                padding: '12px',
                background: 'transparent',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
              }} data-testid="expectation-block">
                <div style={{ fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Expected Outcome
                </div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                  ~{expectedMove}% move
                  {expectedTime && (
                    <span style={{ fontWeight: 500, color: '#64748b', marginLeft: '6px' }}>
                      in ~{expectedTime < 24 ? `${Math.round(expectedTime)}h` : `${(expectedTime / 24).toFixed(1)}d`}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>
                  Confidence: {expectationConfidence}
                </div>
              </div>
            )}
          </div>
        )}
        
        {/* Final Confidence (if V3 available) */}
        {finalConfidence !== undefined && baseConfidence !== undefined && totalMultiplier && totalMultiplier !== 1 && (
          <div style={{
            marginTop: '12px',
            padding: '10px 12px',
            background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
            borderRadius: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }} data-testid="confidence-adjustment">
            <span style={{ fontSize: '12px', color: '#475569' }}>
              Confidence adjusted by intelligence stack
            </span>
            <span style={{ 
              fontSize: '13px', 
              fontWeight: 700, 
              color: totalMultiplier > 1 ? '#16a34a' : totalMultiplier < 1 ? '#dc2626' : '#475569' 
            }}>
              {Math.round(baseConfidence * 100)}% → {Math.round(finalConfidence * 100)}%
              <span style={{ fontSize: '10px', fontWeight: 500, marginLeft: '4px', opacity: 0.7 }}>
                (×{totalMultiplier.toFixed(2)})
              </span>
            </span>
          </div>
        )}
      </Card>
      
      {/* Dominant Pattern + Lifecycle */}
      <Card>
        <SectionTitle>Dominant Pattern</SectionTitle>
        <PatternCard $direction={direction} data-testid="dominant-pattern">
          <div>
            <PatternName>{patternType}</PatternName>
            <div style={{ 
              fontSize: '12px', 
              color: '#64748b', 
              marginTop: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              {direction === 'bullish' && <TrendingUp size={14} color="#22c55e" />}
              {direction === 'bearish' && <TrendingDown size={14} color="#ef4444" />}
              {direction === 'neutral' && <Minus size={14} color="#94a3b8" />}
              <span style={{ 
                color: direction === 'bullish' ? '#22c55e' : 
                       direction === 'bearish' ? '#ef4444' : '#64748b',
                fontWeight: 600,
                textTransform: 'uppercase',
              }}>
                {direction.replace(/_/g, ' ')}
              </span>
              <span>·</span>
              <span>{confidence}% confidence</span>
            </div>
          </div>
          <LifecycleBadge $stage={lifecycle}>{lifecycle}</LifecycleBadge>
        </PatternCard>
      </Card>
      
      {/* Probability */}
      <Card>
        <SectionTitle>Probability</SectionTitle>
        <ProbabilityRow data-testid="probability-block">
          <ProbabilityCard $type="up">
            <div className="label">
              <TrendingUp size={16} />
              Breakout ▲
            </div>
            <div className="value">{probUp}%</div>
          </ProbabilityCard>
          <ProbabilityCard $type="down">
            <div className="label">
              <TrendingDown size={16} />
              Breakdown ▼
            </div>
            <div className="value">{probDown}%</div>
          </ProbabilityCard>
        </ProbabilityRow>
      </Card>
      
      {/* What to Watch */}
      <Card>
        <SectionTitle>
          <Eye size={12} style={{ display: 'inline', marginRight: '6px' }} />
          What to Watch
        </SectionTitle>
        <WatchLevels data-testid="watch-levels">
          <LevelCard $type="breakout">
            <div className="label">▲ Breakout</div>
            <div className="price">{breakoutLevel ? `$${breakoutLevel.toLocaleString()}` : '—'}</div>
            <div className="hint">resistance break</div>
          </LevelCard>
          <LevelCard $type="breakdown">
            <div className="label">▼ Breakdown</div>
            <div className="price">{breakdownLevel ? `$${breakdownLevel.toLocaleString()}` : '—'}</div>
            <div className="hint">support break</div>
          </LevelCard>
        </WatchLevels>
      </Card>
      
      {/* Mini Chart removed - Chart is shown in main view above all tabs */}
    </Container>
  );
};

export default OverviewTab;
