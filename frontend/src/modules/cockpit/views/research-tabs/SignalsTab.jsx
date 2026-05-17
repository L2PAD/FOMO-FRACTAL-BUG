/**
 * Signals Tab — Indicators & Brain
 * ==================================
 * 
 * "Чому ми так думаємо"
 * 
 * Contains:
 * - Indicator Confluence (bullish/bearish)
 * - Indicator List (EMA, MACD, ICHI, DMI, etc.)
 * - TA Brain (score, signals, drivers)
 * - Why This Pattern (geometry, structure, level)
 */

import React from 'react';
import styled from 'styled-components';
import { Activity, Brain, BarChart2, TrendingUp, TrendingDown, Minus, Zap, AlertCircle } from 'lucide-react';

// Import existing components
import IndicatorPanes from '../../components/IndicatorPanes';
import IndicatorControlBar from '../../components/IndicatorControlBar';
import ConfidenceExplanation from '../../components/ConfidenceExplanation';
import TALayersPanel from '../../components/TALayersPanel';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Card = styled.div`
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
`;

const SectionTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  
  svg {
    width: 12px;
    height: 12px;
  }
`;

const ConfluenceBar = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 12px;
`;

const ConfluenceSide = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  
  .label {
    font-size: 11px;
    font-weight: 600;
    color: ${p => p.$type === 'bullish' ? '#16a34a' : '#dc2626'};
    text-transform: uppercase;
  }
  
  .value {
    font-size: 28px;
    font-weight: 700;
    color: ${p => p.$type === 'bullish' ? '#16a34a' : '#dc2626'};
  }
`;

const StrengthBar = styled.div`
  flex: 2;
  
  .bar-container {
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
    display: flex;
  }
  
  .bullish-bar {
    height: 100%;
    background: #22c55e;
    transition: width 0.3s ease;
  }
  
  .bearish-bar {
    height: 100%;
    background: #ef4444;
    transition: width 0.3s ease;
  }
  
  .label {
    text-align: center;
    font-size: 10px;
    color: #94a3b8;
    margin-top: 6px;
    text-transform: uppercase;
  }
`;

const IndicatorGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
`;

const IndicatorCard = styled.div`
  padding: 12px;
  background: ${p => p.$signal === 'bullish' ? 'rgba(34, 197, 94, 0.06)' :
                     p.$signal === 'bearish' ? 'rgba(239, 68, 68, 0.06)' :
                     '#f8fafc'};
  border: 1px solid ${p => p.$signal === 'bullish' ? 'rgba(34, 197, 94, 0.15)' :
                          p.$signal === 'bearish' ? 'rgba(239, 68, 68, 0.15)' :
                          '#e2e8f0'};
  border-radius: 8px;
  
  .name {
    font-size: 11px;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  
  .signal {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    font-weight: 600;
    color: ${p => p.$signal === 'bullish' ? '#16a34a' :
                  p.$signal === 'bearish' ? '#dc2626' : '#64748b'};
  }
  
  .description {
    font-size: 10px;
    color: #94a3b8;
    margin-top: 4px;
  }
`;

const TABrainCard = styled.div`
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  color: #ffffff;
`;

const BrainScore = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  border-right: 1px solid rgba(255,255,255,0.1);
  
  .score {
    font-size: 36px;
    font-weight: 800;
    color: ${p => p.$score > 0 ? '#22c55e' : p.$score < 0 ? '#ef4444' : '#94a3b8'};
  }
  
  .label {
    font-size: 10px;
    color: #94a3b8;
    text-transform: uppercase;
    margin-top: 4px;
  }
`;

const BrainDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    
    .label {
      font-size: 11px;
      color: #94a3b8;
    }
    
    .value {
      font-size: 12px;
      font-weight: 600;
      color: #f1f5f9;
    }
  }
`;

const DriversGrid = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
`;

const DriverBadge = styled.span`
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  background: ${p => p.$signal === 'bullish' ? 'rgba(34, 197, 94, 0.15)' :
                     p.$signal === 'bearish' ? 'rgba(239, 68, 68, 0.15)' :
                     'rgba(255,255,255,0.1)'};
  color: ${p => p.$signal === 'bullish' ? '#86efac' :
                p.$signal === 'bearish' ? '#fca5a5' : '#94a3b8'};
`;

const WhyPatternCard = styled.div`
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  
  .reason-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid #e2e8f0;
    
    &:last-child {
      border-bottom: none;
    }
    
    .category {
      width: 80px;
      font-size: 10px;
      font-weight: 700;
      color: #64748b;
      text-transform: uppercase;
    }
    
    .bar {
      flex: 1;
      height: 6px;
      background: #e2e8f0;
      border-radius: 3px;
      overflow: hidden;
      
      .fill {
        height: 100%;
        background: #3b82f6;
        border-radius: 3px;
      }
    }
    
    .value {
      width: 40px;
      text-align: right;
      font-size: 11px;
      font-weight: 600;
      color: #0f172a;
    }
  }
`;

const SignalsTab = ({
  setupData,
  taContext,
  decision,
  activeIndicators,
  onIndicatorToggle,
  confidenceExplanation,
  unified, // Pass 3: optional unified-state injection
}) => {
  // Extract confluence data
  const bullishCount = taContext?.indicators?.bullish || 0;
  const bearishCount = taContext?.indicators?.bearish || 0;
  const totalSignals = bullishCount + bearishCount;
  const bullishPct = totalSignals > 0 ? Math.round((bullishCount / totalSignals) * 100) : 50;
  const bearishPct = 100 - bullishPct;
  
  // TA Brain data
  const taScore = taContext?.summary?.aggregated_score || 0;
  const taConfidence = Math.round((taContext?.summary?.aggregated_confidence || 0) * 100);
  const drivers = taContext?.top_drivers || [];
  
  // Indicator signals
  const indicatorSignals = setupData?.indicator_result || setupData?.ta_context?.indicators?.signals || [];
  
  // Pattern explanation (why this pattern)
  const patternReasons = setupData?.pattern_reasons || {
    geometry: 0.7,
    structure: 0.5,
    level: 0.6,
  };
  
  // Format names - remove underscores and capitalize
  const formatName = (name) => {
    if (!name) return '-';
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };
  
  return (
    <Container data-testid="signals-tab">
      {/* Indicator Confluence */}
      <Card>
        <SectionTitle>
          <Activity />
          Indicator Confluence
        </SectionTitle>
        <ConfluenceBar data-testid="confluence-bar">
          <ConfluenceSide $type="bullish">
            <div className="label">Bullish</div>
            <div className="value">{bullishPct}%</div>
          </ConfluenceSide>
          <StrengthBar>
            <div className="bar-container">
              <div className="bullish-bar" style={{ width: `${bullishPct}%` }} />
              <div className="bearish-bar" style={{ width: `${bearishPct}%` }} />
            </div>
            <div className="label">Confluence Strength</div>
          </StrengthBar>
          <ConfluenceSide $type="bearish">
            <div className="label">Bearish</div>
            <div className="value">{bearishPct}%</div>
          </ConfluenceSide>
        </ConfluenceBar>
      </Card>
      
      {/* TA Brain */}
      <TABrainCard data-testid="ta-brain">
        <BrainScore $score={taScore}>
          <div className="score">{taScore.toFixed(2)}</div>
          <div className="label">TA Score</div>
        </BrainScore>
        <BrainDetails>
          <div className="row">
            <span className="label">Confidence</span>
            <span className="value">{taConfidence}%</span>
          </div>
          <div className="row">
            <span className="label">Active Signals</span>
            <span className="value">{totalSignals}</span>
          </div>
          <div className="row">
            <span className="label">Bias</span>
            <span className="value" style={{
              color: taScore > 0.1 ? '#86efac' : taScore < -0.1 ? '#fca5a5' : '#94a3b8'
            }}>
              {taScore > 0.1 ? 'BULLISH' : taScore < -0.1 ? 'BEARISH' : 'NEUTRAL'}
            </span>
          </div>
          <DriversGrid>
            {drivers.slice(0, 6).map((d, i) => (
              <DriverBadge key={i} $signal={d.signal}>
                {formatName(d.name)}
              </DriverBadge>
            ))}
          </DriversGrid>
        </BrainDetails>
      </TABrainCard>
      
      {/* Indicator List */}
      <Card>
        <SectionTitle>
          <BarChart2 />
          Indicator Signals
        </SectionTitle>
        <IndicatorGrid data-testid="indicator-grid">
          {indicatorSignals.slice(0, 12).map((ind, i) => (
            <IndicatorCard 
              key={i} 
              $signal={ind.direction?.toLowerCase()}
              onClick={() => onIndicatorToggle && onIndicatorToggle(ind.name?.toLowerCase())}
              style={{ cursor: onIndicatorToggle ? 'pointer' : 'default' }}
            >
              <div className="name">{formatName(ind.name)}</div>
              <div className="signal">
                {ind.direction === 'bullish' && <TrendingUp size={12} />}
                {ind.direction === 'bearish' && <TrendingDown size={12} />}
                {(!ind.direction || ind.direction === 'neutral') && <Minus size={12} />}
                {formatName(ind.direction) || 'Neutral'}
              </div>
              {ind.description && <div className="description">{ind.description}</div>}
            </IndicatorCard>
          ))}
        </IndicatorGrid>
      </Card>
      
      {/* Indicator Control Bar */}
      {setupData?.indicator_insights && (
        <Card style={{ padding: 0 }}>
          <IndicatorControlBar 
            insights={setupData.indicator_insights}
            activeIndicators={activeIndicators}
            onToggle={onIndicatorToggle}
          />
        </Card>
      )}
      
      {/* Indicator Panes */}
      {(activeIndicators?.rsi || activeIndicators?.macd) && setupData?.indicators?.panes?.length > 0 && (
        <Card>
          <SectionTitle>
            <Activity />
            Oscillator Panes
          </SectionTitle>
          <IndicatorPanes 
            indicators={setupData.indicators}
            visiblePanes={Object.entries(activeIndicators || {}).filter(([_, v]) => v).map(([k]) => k)}
            paneHeight={85}
          />
        </Card>
      )}
      
      {/* Why This Pattern */}
      <Card>
        <SectionTitle>
          <Zap />
          Why This Pattern
        </SectionTitle>
        <WhyPatternCard data-testid="why-pattern">
          <div className="reason-row">
            <span className="category">Geometry</span>
            <div className="bar">
              <div className="fill" style={{ width: `${(patternReasons.geometry || 0) * 100}%` }} />
            </div>
            <span className="value">{Math.round((patternReasons.geometry || 0) * 100)}%</span>
          </div>
          <div className="reason-row">
            <span className="category">Structure</span>
            <div className="bar">
              <div className="fill" style={{ width: `${(patternReasons.structure || 0) * 100}%` }} />
            </div>
            <span className="value">{Math.round((patternReasons.structure || 0) * 100)}%</span>
          </div>
          <div className="reason-row">
            <span className="category">Level</span>
            <div className="bar">
              <div className="fill" style={{ width: `${(patternReasons.level || 0) * 100}%` }} />
            </div>
            <span className="value">{Math.round((patternReasons.level || 0) * 100)}%</span>
          </div>
        </WhyPatternCard>
      </Card>
      
      {/* TA Layers Panel - Comprehensive 10-Layer Analysis */}
      {setupData?.ta_layers && (
        <TALayersPanel
          taLayers={setupData.ta_layers}
          probability={setupData.probability}
          scenarios={setupData.scenarios}
          activeRange={setupData.active_range}
        />
      )}
      
      {/* Confidence Explanation */}
      <ConfidenceExplanation explanation={confidenceExplanation} />
    </Container>
  );
};

export default SignalsTab;
