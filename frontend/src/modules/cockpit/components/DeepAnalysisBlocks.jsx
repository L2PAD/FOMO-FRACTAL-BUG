/**
 * DeepAnalysisBlocks Component
 * ============================
 * Shows detailed analysis in 6 sections:
 * 1. Technical Summary
 * 2. Primary Setup
 * 3. Market Structure
 * 4. Key Drivers
 * 5. Conflicts / Risks
 * 6. Setup Breakdown (text)
 */

import React from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Shield, 
  AlertTriangle, 
  Activity,
  Layers,
  Zap,
  FileText
} from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  
  @media (max-width: 1200px) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const Block = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 16px;
  
  &.full-width {
    grid-column: 1 / -1;
  }
`;

const BlockHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  
  .title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    
    svg {
      width: 16px;
      height: 16px;
      color: #64748b;
    }
  }
`;

const Badge = styled.span`
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  background: ${({ $type }) => {
    switch ($type) {
      case 'bullish': return '#e8f9f1';
      case 'bearish': return '#fef2f2';
      case 'high': return '#fef2f2';
      case 'medium': return '#fef3c7';
      case 'low': return '#f0f9ff';
      default: return '#f8fafc';
    }
  }};
  color: ${({ $type }) => {
    switch ($type) {
      case 'bullish': return '#05A584';
      case 'bearish': return '#ef4444';
      case 'high': return '#ef4444';
      case 'medium': return '#d97706';
      case 'low': return '#3b82f6';
      default: return '#64748b';
    }
  }};
`;

const MetricRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  
  &:last-child {
    border-bottom: none;
  }
  
  .label {
    font-size: 12px;
    color: #64748b;
  }
  
  .value {
    font-size: 13px;
    font-weight: 600;
    color: ${({ $color }) => $color || '#0f172a'};
    font-variant-numeric: tabular-nums;
  }
`;

const ProgressBar = styled.div`
  height: 6px;
  background: #eef1f5;
  border-radius: 3px;
  overflow: hidden;
  margin-top: 4px;
  
  .fill {
    height: 100%;
    border-radius: 3px;
    background: ${({ $color }) => $color || '#05A584'};
    width: ${({ $value }) => Math.min($value, 100)}%;
    transition: width 0.3s ease;
  }
`;

const DriverItem = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  
  &:last-child {
    border-bottom: none;
  }
  
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: ${({ $color }) => $color || '#05A584'};
    flex-shrink: 0;
  }
  
  .content {
    flex: 1;
    
    .name {
      font-size: 12px;
      font-weight: 600;
      color: #0f172a;
    }
    
    .desc {
      font-size: 11px;
      color: #64748b;
      margin-top: 2px;
    }
  }
  
  .strength {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
  }
`;

const ConflictItem = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  background: ${({ $severity }) => 
    $severity === 'high' ? '#fef2f2' : 
    $severity === 'medium' ? '#fffbeb' : '#f8fafc'};
  border-radius: 8px;
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  .icon {
    color: ${({ $severity }) => 
      $severity === 'high' ? '#ef4444' : 
      $severity === 'medium' ? '#f59e0b' : '#64748b'};
    flex-shrink: 0;
  }
  
  .content {
    flex: 1;
    
    .name {
      font-size: 12px;
      font-weight: 600;
      color: #0f172a;
    }
    
    .desc {
      font-size: 11px;
      color: #64748b;
      margin-top: 2px;
    }
  }
`;

const BreakdownText = styled.div`
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
  
  strong {
    color: #0f172a;
    font-weight: 600;
  }
  
  .highlight {
    color: #05A584;
    font-weight: 600;
  }
  
  .warning {
    color: #f59e0b;
    font-weight: 600;
  }
`;

const LevelList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const LevelTag = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: ${({ $type }) => 
    $type === 'support' ? '#e8f9f1' : 
    $type === 'resistance' ? '#fef2f2' : 
    $type?.includes('fib') ? '#ede9fe' : '#f8fafc'};
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: ${({ $type }) => 
    $type === 'support' ? '#05A584' : 
    $type === 'resistance' ? '#ef4444' : 
    $type?.includes('fib') ? '#7c3aed' : '#64748b'};
  
  .price {
    font-variant-numeric: tabular-nums;
  }
`;

// ============================================
// COMPONENT
// ============================================

const DeepAnalysisBlocks = ({ setup = null, technicalBias = 'neutral', biasConfidence = 0 }) => {
  if (!setup) {
    return (
      <Container data-testid="deep-analysis-blocks">
        <Block className="full-width">
          <BlockHeader>
            <span className="title"><Activity /> Analysis</span>
          </BlockHeader>
          <div style={{ color: '#94a3b8', fontSize: 13 }}>No setup data available</div>
        </Block>
      </Container>
    );
  }

  const { 
    setup_type,
    direction,
    confidence,
    confluence_score,
    patterns = [],
    indicators = [],
    levels = [],
    structure = [],
    primary_confluence,
    conflicts = [],
    entry_zone,
    invalidation,
    targets = [],
    current_price,
    market_regime,
    explanation,
  } = setup;

  const formatPrice = (v) => v ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '-';
  const isBullish = direction === 'bullish';

  return (
    <Container data-testid="deep-analysis-blocks">
      {/* Block 1: Technical Summary */}
      <Block>
        <BlockHeader>
          <span className="title">
            {isBullish ? <TrendingUp /> : <TrendingDown />}
            Technical Summary
          </span>
          <Badge $type={technicalBias}>{technicalBias}</Badge>
        </BlockHeader>
        
        <MetricRow>
          <span className="label">Asset</span>
          <span className="value">{setup.asset || '-'}</span>
        </MetricRow>
        <MetricRow>
          <span className="label">Timeframe</span>
          <span className="value">{setup.timeframe?.toUpperCase() || '-'}</span>
        </MetricRow>
        <MetricRow>
          <span className="label">Technical Bias</span>
          <span className="value" $color={isBullish ? '#05A584' : '#ef4444'}>{direction?.replace(/_/g, ' ').toUpperCase()}</span>
        </MetricRow>
        <MetricRow>
          <span className="label">Confidence</span>
          <span className="value">{Math.round((biasConfidence || confidence || 0) * 100)}%</span>
        </MetricRow>
        <ProgressBar $value={(biasConfidence || confidence || 0) * 100} $color={isBullish ? '#05A584' : '#ef4444'}>
          <div className="fill" />
        </ProgressBar>
        <MetricRow style={{ marginTop: 8 }}>
          <span className="label">Market Regime</span>
          <span className="value">{market_regime?.replace(/_/g, ' ') || '-'}</span>
        </MetricRow>
      </Block>

      {/* Block 2: Primary Setup */}
      <Block>
        <BlockHeader>
          <span className="title"><Target /> Primary Setup</span>
        </BlockHeader>
        
        <MetricRow>
          <span className="label">Setup Type</span>
          <span className="value">{setup_type?.replace(/_/g, ' ') || '-'}</span>
        </MetricRow>
        <MetricRow>
          <span className="label">Direction</span>
          <span className="value" $color={isBullish ? '#05A584' : '#ef4444'}>{direction?.replace(/_/g, ' ').toUpperCase()}</span>
        </MetricRow>
        <MetricRow>
          <span className="label">Confluence Score</span>
          <span className="value">{Math.round((confluence_score || 0) * 100)}%</span>
        </MetricRow>
        <ProgressBar $value={(confluence_score || 0) * 100} $color="#3b82f6">
          <div className="fill" />
        </ProgressBar>
        
        {entry_zone && (
          <MetricRow style={{ marginTop: 8 }}>
            <span className="label">Entry Zone</span>
            <span className="value">{formatPrice(entry_zone.low)} - {formatPrice(entry_zone.high)}</span>
          </MetricRow>
        )}
        {invalidation && (
          <MetricRow $color="#ef4444">
            <span className="label">Invalidation</span>
            <span className="value">{formatPrice(invalidation)}</span>
          </MetricRow>
        )}
        {targets.length > 0 && (
          <MetricRow $color="#3b82f6">
            <span className="label">Targets</span>
            <span className="value">{targets.slice(0, 2).map(t => formatPrice(t)).join(' / ')}</span>
          </MetricRow>
        )}
      </Block>

      {/* Block 3: Market Structure */}
      <Block>
        <BlockHeader>
          <span className="title"><Layers /> Market Structure</span>
        </BlockHeader>
        
        {structure.length > 0 ? (
          <>
            {/* Count structure types */}
            {['HH', 'HL', 'LH', 'LL', 'BOS', 'CHOCH'].map(type => {
              const count = structure.filter(s => s.type === type).length;
              if (count === 0) return null;
              const isBull = ['HH', 'HL'].includes(type);
              return (
                <MetricRow key={type}>
                  <span className="label">{type}</span>
                  <span className="value" style={{ color: isBull ? '#05A584' : '#ef4444' }}>×{count}</span>
                </MetricRow>
              );
            })}
          </>
        ) : (
          <div style={{ color: '#94a3b8', fontSize: 12 }}>No structure data</div>
        )}
        
        <div style={{ marginTop: 12 }}>
          <span style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>Key Levels</span>
          <LevelList style={{ marginTop: 8 }}>
            {levels.slice(0, 4).map((l, i) => (
              <LevelTag key={i} $type={l.type}>
                <span>{l.type?.replace(/_/g, ' ')}</span>
                <span className="price">{formatPrice(l.price)}</span>
              </LevelTag>
            ))}
          </LevelList>
        </div>
      </Block>

      {/* Block 4: Key Drivers */}
      <Block>
        <BlockHeader>
          <span className="title"><Zap /> Key Drivers</span>
        </BlockHeader>
        
        {/* Top Pattern */}
        {patterns[0] && (
          <DriverItem $color="#3b82f6">
            <span className="dot" />
            <div className="content">
              <div className="name">{patterns[0].type?.replace(/_/g, ' ')}</div>
              <div className="desc">Primary pattern detected</div>
            </div>
            <span className="strength">{Math.round((patterns[0].confidence || 0) * 100)}%</span>
          </DriverItem>
        )}
        
        {/* Top Indicators */}
        {indicators.slice(0, 3).map((ind, i) => (
          <DriverItem key={i} $color={ind.direction === 'bullish' ? '#05A584' : ind.direction === 'bearish' ? '#ef4444' : '#8b5cf6'}>
            <span className="dot" />
            <div className="content">
              <div className="name">{ind.name}</div>
              <div className="desc">{ind.signal_type?.replace(/_/g, ' ')}</div>
            </div>
            <span className="strength">{Math.round((ind.strength || 0) * 100)}%</span>
          </DriverItem>
        ))}
        
        {/* Confluence */}
        {primary_confluence && (
          <DriverItem $color="#f59e0b" style={{ marginTop: 4 }}>
            <span className="dot" />
            <div className="content">
              <div className="name">Confluence</div>
              <div className="desc">{primary_confluence.components?.slice(0, 2).join(', ')}</div>
            </div>
            <span className="strength">{Math.round((primary_confluence.score || 0) * 100)}%</span>
          </DriverItem>
        )}
      </Block>

      {/* Block 5: Conflicts / Risks */}
      <Block>
        <BlockHeader>
          <span className="title"><AlertTriangle /> Conflicts / Risks</span>
          {conflicts.length > 0 && <Badge $type={conflicts[0]?.severity}>{conflicts.length} found</Badge>}
        </BlockHeader>
        
        {conflicts.length > 0 ? (
          conflicts.slice(0, 3).map((c, i) => (
            <ConflictItem key={i} $severity={c.severity}>
              <AlertTriangle size={16} className="icon" />
              <div className="content">
                <div className="name">{c.name}</div>
                <div className="desc">{c.description}</div>
              </div>
            </ConflictItem>
          ))
        ) : (
          <div style={{ color: '#05A584', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Shield size={16} />
            No significant conflicts detected
          </div>
        )}
      </Block>

      {/* Block 6: Setup Breakdown */}
      <Block>
        <BlockHeader>
          <span className="title"><FileText /> Setup Breakdown</span>
        </BlockHeader>
        
        <BreakdownText>
          {explanation ? (
            explanation
          ) : (
            <>
              <strong>Detected Pattern:</strong> {patterns[0]?.type?.replace(/_/g, ' ') || 'None'}<br/>
              <strong>Indicator Confirmation:</strong> {indicators.filter(i => i.direction === direction).length} aligned signals<br/>
              <strong>Support/Resistance:</strong> {levels.filter(l => l.type === 'support').length} support, {levels.filter(l => l.type === 'resistance').length} resistance levels<br/>
              <strong>Structure:</strong> {structure.length > 0 ? `${structure.filter(s => ['HH','HL'].includes(s.type)).length} bullish, ${structure.filter(s => ['LH','LL'].includes(s.type)).length} bearish points` : 'No data'}
            </>
          )}
        </BreakdownText>
      </Block>
    </Container>
  );
};

export default DeepAnalysisBlocks;
