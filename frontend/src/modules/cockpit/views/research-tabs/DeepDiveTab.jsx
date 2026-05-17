/**
 * Deep Dive Tab — Advanced Layer
 * ================================
 * 
 * "Це не для всіх — це depth layer"
 * 
 * Contains:
 * - Full Technical Summary
 * - Key Drivers + Conflicts
 * - Full Breakdown (narrative + raw metrics)
 * - Debug/Audit info
 */

import React from 'react';
import styled from 'styled-components';
import { FileText, AlertCircle, CheckCircle, Database, Layers } from 'lucide-react';

// Import existing components
import { NarrativeSummary, buildNarrative } from '../../../../components/chart-engine/narrative';
import ExplanationPanel from '../../components/ExplanationPanel';
import DeepAnalysisBlocks from '../../components/DeepAnalysisBlocks';
import PatternActivationLayer from '../../components/PatternActivationLayer';
import StoryLine from '../../components/StoryLine';
import RenderPlanReasons from '../../components/RenderPlanReasons';

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

const SummaryHeader = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px;
  background: #0f172a;
  border-radius: 10px;
  color: #ffffff;
`;

const SummaryItem = styled.div`
  text-align: center;
  
  .label {
    font-size: 10px;
    color: #94a3b8;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  
  .value {
    font-size: 16px;
    font-weight: 700;
    color: ${p => p.$highlight === 'bullish' ? '#22c55e' :
                  p.$highlight === 'bearish' ? '#ef4444' :
                  p.$highlight === 'high' ? '#22c55e' :
                  '#f1f5f9'};
  }
`;

const DriversGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const DriversList = styled.div`
  padding: 16px;
  background: ${p => p.$type === 'drivers' ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.05)'};
  border-radius: 10px;
  border: 1px solid ${p => p.$type === 'drivers' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)'};
  
  .title {
    font-size: 11px;
    font-weight: 700;
    color: ${p => p.$type === 'drivers' ? '#16a34a' : '#dc2626'};
    text-transform: uppercase;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid ${p => p.$type === 'drivers' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)'};
    
    &:last-child {
      border-bottom: none;
    }
    
    .name {
      flex: 1;
      font-size: 12px;
      color: #0f172a;
    }
    
    .signal {
      font-size: 10px;
      font-weight: 600;
      color: ${p => p.$type === 'drivers' ? '#16a34a' : '#dc2626'};
      text-transform: uppercase;
    }
  }
`;

const MetricsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
`;

const MetricCard = styled.div`
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  
  .label {
    font-size: 10px;
    color: #94a3b8;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  
  .value {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    font-family: 'Gilroy', 'Inter', sans-serif;
  }
`;

const DeepDiveTab = ({
  setupData,
  decision,
  primaryPattern,
  symbol,
  selectedTF,
  explanation,
  unifiedSetup,
  technicalBias,
  biasConfidence,
  activeElements,
  onToggleElement,
  liquidity,
  displacement,
  chochValidation,
  poi,
  tradeSetup,
  renderPlan,
}) => {
  // Extract data
  const bias = decision?.bias || 'neutral';
  const confidence = Math.round((decision?.confidence || 0) * 100);
  const regime = setupData?.structure_context?.market_state || 'unknown';
  const quality = decision?.tradeability || 'low';
  
  // Drivers and conflicts
  const drivers = setupData?.key_drivers || decision?.drivers || [];
  const conflicts = setupData?.conflicts || decision?.conflicts || [];
  
  // Raw metrics
  const rawMetrics = {
    pattern_confidence: primaryPattern?.confidence,
    bias_strength: decision?.strength,
    volatility: setupData?.structure_context?.volatility,
    trend_strength: setupData?.structure_context?.trend_strength,
    levels_count: setupData?.levels?.length || 0,
    signals_count: setupData?.indicator_result?.length || 0,
  };
  
  return (
    <Container data-testid="deep-dive-tab">
      {/* Full Technical Summary */}
      <Card>
        <SectionTitle>
          <FileText />
          Full Technical Summary
        </SectionTitle>
        <SummaryHeader data-testid="tech-summary">
          <SummaryItem>
            <div className="label">Symbol</div>
            <div className="value">{symbol}</div>
          </SummaryItem>
          <SummaryItem>
            <div className="label">Timeframe</div>
            <div className="value">{selectedTF}</div>
          </SummaryItem>
          <SummaryItem $highlight={bias}>
            <div className="label">Bias</div>
            <div className="value">{bias.replace(/_/g, ' ').toUpperCase()}</div>
          </SummaryItem>
          <SummaryItem $highlight={confidence > 60 ? 'high' : 'neutral'}>
            <div className="label">Confidence</div>
            <div className="value">{confidence}%</div>
          </SummaryItem>
        </SummaryHeader>
        <div style={{ 
          marginTop: '12px', 
          padding: '12px', 
          background: '#f8fafc', 
          borderRadius: '8px',
          fontSize: '13px',
          color: '#475569',
          lineHeight: '1.6'
        }}>
          <strong>Regime:</strong> {regime.replace(/_/g, ' ')} · <strong>Quality:</strong> {quality.replace(/_/g, ' ')}
          {setupData?.interpretation && (
            <div style={{ marginTop: '8px' }}>{setupData.interpretation}</div>
          )}
        </div>
      </Card>
      
      {/* Key Drivers + Conflicts */}
      <DriversGrid>
        <DriversList $type="drivers">
          <div className="title">
            <CheckCircle size={12} />
            Key Drivers
          </div>
          {drivers.length > 0 ? (
            drivers.slice(0, 8).map((d, i) => (
              <div className="item" key={i}>
                <span className="name">{d.name || d}</span>
                <span className="signal">{d.signal || 'active'}</span>
              </div>
            ))
          ) : (
            <div style={{ color: '#94a3b8', fontSize: '12px' }}>No drivers identified</div>
          )}
        </DriversList>
        
        <DriversList $type="conflicts">
          <div className="title">
            <AlertCircle size={12} />
            Conflicts / Risks
          </div>
          {conflicts.length > 0 ? (
            conflicts.slice(0, 8).map((c, i) => (
              <div className="item" key={i}>
                <span className="name">{c.description || c}</span>
                <span className="signal">warning</span>
              </div>
            ))
          ) : (
            <div style={{ color: '#94a3b8', fontSize: '12px' }}>No conflicts detected</div>
          )}
        </DriversList>
      </DriversGrid>
      
      {/* Story Line */}
      <StoryLine 
        liquidity={liquidity}
        displacement={displacement}
        chochValidation={chochValidation}
        structure={setupData?.structure}
        decision={decision}
        pattern={primaryPattern}
      />
      
      {/* Narrative Summary */}
      {decision && (
        <NarrativeSummary
          narrative={buildNarrative({
            liquidity,
            displacement,
            chochValidation,
            poi,
            decision,
            tradeSetup,
          })}
          decision={decision}
        />
      )}
      
      {/* Raw Metrics */}
      <Card>
        <SectionTitle>
          <Database />
          Raw Metrics
        </SectionTitle>
        <MetricsGrid data-testid="raw-metrics">
          {Object.entries(rawMetrics).map(([key, value]) => (
            <MetricCard key={key}>
              <div className="label">{key.replace(/_/g, ' ')}</div>
              <div className="value">
                {value === undefined || value === null ? '—' : 
                 typeof value === 'number' ? value.toFixed(3) : String(value)}
              </div>
            </MetricCard>
          ))}
        </MetricsGrid>
      </Card>
      
      {/* Render Plan Reasons */}
      {renderPlan && (
        <Card>
          <RenderPlanReasons renderPlan={renderPlan} />
        </Card>
      )}
      
      {/* Explanation Panel */}
      <ExplanationPanel explanation={explanation} />
      
      {/* Pattern Activation Layer */}
      <PatternActivationLayer
        setup={unifiedSetup}
        activeElements={activeElements}
        onToggleElement={onToggleElement}
      />
      
      {/* Deep Analysis Blocks */}
      <DeepAnalysisBlocks
        setup={unifiedSetup}
        technicalBias={technicalBias}
        biasConfidence={biasConfidence}
      />
    </Container>
  );
};

export default DeepDiveTab;
