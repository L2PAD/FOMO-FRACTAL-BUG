/**
 * ConfluenceMatrix Component
 * ==========================
 * Displays indicator confluence analysis + TA Brain.
 * 
 * Shows:
 * - TA Brain expandable section (moved from TAContextPanel)
 * - Bullish indicators
 * - Bearish indicators
 * - Neutral indicators
 * - Conflicts
 * - Overall strength meter
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  AlertTriangle,
  Activity,
  Brain,
  ChevronDown,
  ChevronUp,
  Eye
} from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #eef1f5;
  
  .title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    
    svg {
      width: 16px;
      height: 16px;
      color: #3b82f6;
    }
  }
  
  .summary {
    font-size: 12px;
    color: #64748b;
  }
`;

const StrengthMeter = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #eef1f5;
  
  .label {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    min-width: 80px;
  }
  
  .meter {
    flex: 1;
    height: 8px;
    background: #f1f5f9;
    border-radius: 4px;
    position: relative;
    overflow: hidden;
    
    .fill {
      position: absolute;
      height: 100%;
      border-radius: 4px;
      transition: all 0.3s ease;
    }
    
    .fill.bearish {
      left: 0;
      background: linear-gradient(90deg, #ef4444, #fca5a5);
    }
    
    .fill.bullish {
      right: 0;
      background: linear-gradient(90deg, #86efac, #22c55e);
    }
    
    .center-line {
      position: absolute;
      left: 50%;
      top: 0;
      bottom: 0;
      width: 2px;
      background: #64748b;
      transform: translateX(-50%);
    }
  }
  
  .value {
    font-size: 14px;
    font-weight: 700;
    min-width: 60px;
    text-align: right;
    color: ${({ $bias }) => 
      $bias === 'bullish' ? '#22c55e' : 
      $bias === 'bearish' ? '#ef4444' : '#64748b'};
  }
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1px;
  background: #eef1f5;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const Column = styled.div`
  background: #ffffff;
  padding: 12px;
  
  .column-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 10px;
    
    .icon {
      width: 20px;
      height: 20px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      &.bullish {
        background: rgba(34, 197, 94, 0.1);
        color: #22c55e;
      }
      &.bearish {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
      }
      &.neutral {
        background: rgba(100, 116, 139, 0.1);
        color: #64748b;
      }
      
      svg {
        width: 12px;
        height: 12px;
      }
    }
    
    .label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64748b;
    }
    
    .count {
      margin-left: auto;
      font-size: 12px;
      font-weight: 700;
      color: #0f172a;
    }
  }
`;

const SignalList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const SignalItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: ${({ $type }) => 
    $type === 'bullish' ? 'rgba(34, 197, 94, 0.05)' : 
    $type === 'bearish' ? 'rgba(239, 68, 68, 0.05)' : '#f8fafc'};
  border-radius: 6px;
  
  .name {
    font-size: 12px;
    font-weight: 500;
    color: #0f172a;
  }
  
  .signal-type {
    font-size: 10px;
    color: #64748b;
  }
  
  .strength {
    font-size: 11px;
    font-weight: 600;
    color: ${({ $type }) => 
      $type === 'bullish' ? '#22c55e' : 
      $type === 'bearish' ? '#ef4444' : '#64748b'};
  }
`;

const ConflictsSection = styled.div`
  padding: 12px 16px;
  background: rgba(245, 158, 11, 0.05);
  border-top: 1px solid #eef1f5;
  
  .conflict-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    
    svg {
      width: 14px;
      height: 14px;
      color: #f59e0b;
    }
    
    .label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      color: #f59e0b;
    }
  }
  
  .conflict-item {
    font-size: 12px;
    color: #64748b;
    padding: 4px 0;
  }
`;

const EmptyState = styled.div`
  padding: 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
`;

// TA Brain Section Styles
const TABrainSection = styled.div`
  border-top: 1px solid #eef1f5;
`;

const TABrainHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f8fafc;
  cursor: pointer;
  user-select: none;
  
  &:hover {
    background: #f1f5f9;
  }
  
  .left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .brain-icon {
    color: #6366f1;
  }
  
  .title {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  
  .badge {
    font-size: 10px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
    
    &.bullish { background: rgba(34, 197, 94, 0.15); color: #16a34a; }
    &.bearish { background: rgba(239, 68, 68, 0.15); color: #dc2626; }
    &.neutral { background: rgba(100, 116, 139, 0.15); color: #64748b; }
  }
  
  .source-count {
    font-size: 11px;
    color: #94a3b8;
    font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  
  svg {
    color: #94a3b8;
  }
`;

const TABrainContent = styled.div`
  padding: 16px;
  
  .summary-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  
  .summary-stat {
    text-align: center;
    padding: 10px;
    background: #f8fafc;
    border-radius: 8px;
    
    .label {
      font-size: 10px;
      color: #94a3b8;
      text-transform: uppercase;
      margin-bottom: 4px;
      font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .value {
      font-size: 14px;
      font-weight: 700;
      font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
    }
  }
  
  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    margin: 12px 0 8px;
    font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
    
    svg { width: 12px; height: 12px; }
  }
  
  .drivers-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .driver-row {
    display: grid;
    grid-template-columns: auto 1fr auto auto auto;
    gap: 10px;
    align-items: center;
    padding: 6px 10px;
    background: #f8fafc;
    border-radius: 6px;
    font-size: 12px;
    font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
    
    .name { color: #0f172a; font-weight: 500; }
    .score { font-weight: 600; }
    .impact { color: #6366f1; font-size: 11px; }
  }
`;

// ============================================
// COMPONENT
// ============================================

const ConfluenceMatrix = ({ confluence, taContext }) => {
  const [taBrainExpanded, setTaBrainExpanded] = useState(false);
  if (!confluence) {
    return (
      <Container>
        <Header>
          <div className="title">
            <Activity />
            Indicator Confluence
          </div>
        </Header>
        <EmptyState>No confluence data available</EmptyState>
      </Container>
    );
  }
  
  const { 
    bullish = [], 
    bearish = [], 
    neutral = [], 
    conflicts = [],
    overall_strength = 0,
    overall_bias = 'neutral',
    confidence = 0,
    summary = ''
  } = confluence;
  
  // Calculate meter fill
  const meterWidth = Math.abs(overall_strength) * 50; // 50% max each side
  
  return (
    <Container data-testid="confluence-matrix">
      <Header>
        <div className="title">
          <Activity />
          Indicator Confluence
        </div>
        <div className="summary">{summary}</div>
      </Header>
      
      {/* Strength Meter */}
      <StrengthMeter $bias={overall_bias}>
        <span className="label">Strength</span>
        <div className="meter">
          <div className="center-line" />
          {overall_strength < 0 && (
            <div 
              className="fill bearish" 
              style={{ width: `${meterWidth}%`, right: '50%' }}
            />
          )}
          {overall_strength > 0 && (
            <div 
              className="fill bullish" 
              style={{ width: `${meterWidth}%`, left: '50%' }}
            />
          )}
        </div>
        <span className="value">
          {overall_strength > 0 ? '+' : ''}{(overall_strength * 100).toFixed(0)}%
        </span>
      </StrengthMeter>
      
      {/* Signal Columns */}
      <Grid>
        {/* Bullish */}
        <Column>
          <div className="column-header">
            <div className="icon bullish">
              <TrendingUp />
            </div>
            <span className="label">Bullish</span>
            <span className="count">{bullish.length}</span>
          </div>
          <SignalList>
            {bullish.length === 0 ? (
              <SignalItem $type="neutral">
                <span className="name">No bullish signals</span>
              </SignalItem>
            ) : (
              bullish.slice(0, 5).map((signal, i) => (
                <SignalItem key={i} $type="bullish">
                  <div>
                    <div className="name">{signal.name}</div>
                    <div className="signal-type">{signal.signal_type}</div>
                  </div>
                  <span className="strength">{(signal.strength * 100).toFixed(0)}%</span>
                </SignalItem>
              ))
            )}
          </SignalList>
        </Column>
        
        {/* Bearish */}
        <Column>
          <div className="column-header">
            <div className="icon bearish">
              <TrendingDown />
            </div>
            <span className="label">Bearish</span>
            <span className="count">{bearish.length}</span>
          </div>
          <SignalList>
            {bearish.length === 0 ? (
              <SignalItem $type="neutral">
                <span className="name">No bearish signals</span>
              </SignalItem>
            ) : (
              bearish.slice(0, 5).map((signal, i) => (
                <SignalItem key={i} $type="bearish">
                  <div>
                    <div className="name">{signal.name}</div>
                    <div className="signal-type">{signal.signal_type}</div>
                  </div>
                  <span className="strength">{(signal.strength * 100).toFixed(0)}%</span>
                </SignalItem>
              ))
            )}
          </SignalList>
        </Column>
        
        {/* Neutral */}
        <Column>
          <div className="column-header">
            <div className="icon neutral">
              <Minus />
            </div>
            <span className="label">Neutral</span>
            <span className="count">{neutral.length}</span>
          </div>
          <SignalList>
            {neutral.length === 0 ? (
              <SignalItem $type="neutral">
                <span className="name">No neutral signals</span>
              </SignalItem>
            ) : (
              neutral.slice(0, 5).map((signal, i) => (
                <SignalItem key={i} $type="neutral">
                  <div>
                    <div className="name">{signal.name}</div>
                    <div className="signal-type">{signal.signal_type}</div>
                  </div>
                  <span className="strength">{(signal.strength * 100).toFixed(0)}%</span>
                </SignalItem>
              ))
            )}
          </SignalList>
        </Column>
      </Grid>
      
      {/* Conflicts */}
      {conflicts.length > 0 && (
        <ConflictsSection>
          <div className="conflict-header">
            <AlertTriangle />
            <span className="label">Conflicts Detected</span>
          </div>
          {conflicts.map((conflict, i) => (
            <div key={i} className="conflict-item">
              {conflict.family}: {conflict.note}
            </div>
          ))}
        </ConflictsSection>
      )}
      
      {/* TA BRAIN Section — Expandable */}
      {taContext && taContext.summary && (
        <TABrainSection>
          <TABrainHeader onClick={() => setTaBrainExpanded(!taBrainExpanded)}>
            <div className="left">
              <Brain size={16} className="brain-icon" />
              <span className="title">TA Brain</span>
              <span className={`badge ${taContext.summary.aggregated_bias}`}>
                {taContext.summary.aggregated_bias}
              </span>
              <span className="source-count">
                {taContext.summary.total_sources || 0} sources | {taContext.summary.active_sources || 0} active
              </span>
            </div>
            {taBrainExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </TABrainHeader>
          
          {taBrainExpanded && (
            <TABrainContent>
              {/* Summary Stats */}
              <div className="summary-row">
                <div className="summary-stat">
                  <div className="label">Score</div>
                  <div className="value" style={{
                    color: taContext.summary.aggregated_score > 0 ? '#16a34a' : 
                           taContext.summary.aggregated_score < 0 ? '#dc2626' : '#64748b'
                  }}>
                    {taContext.summary.aggregated_score > 0 ? '+' : ''}
                    {(taContext.summary.aggregated_score || 0).toFixed(3)}
                  </div>
                </div>
                <div className="summary-stat">
                  <div className="label">Confidence</div>
                  <div className="value">
                    {((taContext.summary.aggregated_confidence || 0) * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="summary-stat">
                  <div className="label">Bullish</div>
                  <div className="value" style={{ color: '#16a34a' }}>
                    {taContext.indicators?.bullish || 0}
                  </div>
                </div>
                <div className="summary-stat">
                  <div className="label">Bearish</div>
                  <div className="value" style={{ color: '#dc2626' }}>
                    {taContext.indicators?.bearish || 0}
                  </div>
                </div>
              </div>
              
              {/* Top Drivers */}
              {taContext.top_drivers && taContext.top_drivers.length > 0 && (
                <>
                  <div className="section-title">
                    <Eye size={12} /> Top Drivers
                  </div>
                  <div className="drivers-list">
                    {taContext.top_drivers.slice(0, 7).map((d, i) => (
                      <div key={i} className="driver-row">
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: d.signal === 'bullish' ? '#16a34a' : 
                                     d.signal === 'bearish' ? '#dc2626' : '#94a3b8'
                        }} />
                        <div className="name">{d.name}</div>
                        <div style={{
                          color: d.signal === 'bullish' ? '#16a34a' : 
                                 d.signal === 'bearish' ? '#dc2626' : '#64748b',
                          fontSize: '11px'
                        }}>
                          {d.signal}
                        </div>
                        <div className="score" style={{
                          color: d.score > 0 ? '#16a34a' : d.score < 0 ? '#dc2626' : '#94a3b8'
                        }}>
                          {d.score > 0 ? '+' : ''}{(d.score || 0).toFixed(3)}
                        </div>
                        <div className="impact">{((d.impact || 0) * 100).toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </TABrainContent>
          )}
        </TABrainSection>
      )}
    </Container>
  );
};

export default ConfluenceMatrix;
