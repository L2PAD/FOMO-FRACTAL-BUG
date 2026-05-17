/**
 * TALayersPanel — 10 Layer TA Decision System UI
 * ===============================================
 * 
 * Displays:
 * - Market State (Structure, Impulse, Regime)
 * - Probability (Bullish/Bearish %)
 * - Scenarios (Break Up/Down targets)
 * - Narrative (Human-readable analysis)
 */

import React from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Target, Activity, Layers } from 'lucide-react';

const Container = styled.div`
  background: #0f172a;
  border-radius: 12px;
  padding: 20px;
  margin: 10px 0;
  color: #ffffff;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
`;

const Title = styled.div`
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #ffffff;
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
`;

const Cell = styled.div`
  text-align: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
`;

const CellLabel = styled.div`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
`;

const CellValue = styled.div`
  font-size: 15px;
  font-weight: 700;
  color: ${props => props.color || '#ffffff'};
`;

const ProbabilityBar = styled.div`
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin: 8px 0;
`;

const ProbSegment = styled.div`
  height: 100%;
  background: ${props => props.color};
  width: ${props => props.width}%;
`;

const ScenariosGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 12px 0;
`;

const ScenarioCard = styled.div`
  background: ${props => props.bullish ? 'rgba(22, 163, 74, 0.1)' : 'rgba(220, 38, 38, 0.1)'};
  border: 1px solid ${props => props.bullish ? 'rgba(22, 163, 74, 0.3)' : 'rgba(220, 38, 38, 0.3)'};
  border-radius: 8px;
  padding: 10px;
`;

const ScenarioTitle = styled.div`
  font-size: 10px;
  color: ${props => props.bullish ? '#22c55e' : '#ef4444'};
  font-weight: 600;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
`;

const ScenarioTarget = styled.div`
  font-size: 16px;
  font-weight: 700;
  color: ${props => props.bullish ? '#22c55e' : '#ef4444'};
`;

const ScenarioProb = styled.div`
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
`;

const Narrative = styled.div`
  background: rgba(59, 130, 246, 0.15);
  border-left: 3px solid #3b82f6;
  padding: 12px 14px;
  border-radius: 0 8px 8px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #ffffff;
`;

const TALayersPanel = ({ taLayers, probability, scenarios, activeRange }) => {
  if (!taLayers) return null;

  const structure = taLayers.structure || {};
  const impulse = taLayers.impulse || {};
  const regime = taLayers.regime || {};
  const prob = probability || taLayers.probability || {};
  const scen = scenarios || taLayers.scenarios || {};
  const narrative = taLayers.narrative || '';

  const getTrendColor = (trend) => {
    if (trend === 'bullish') return '#22c55e';
    if (trend === 'bearish') return '#ef4444';
    return '#94a3b8';
  };

  const getRegimeColor = (r) => {
    if (r === 'range') return '#3b82f6';
    if (r === 'trend') return '#f59e0b';
    if (r === 'compression') return '#a855f7';
    return '#94a3b8';
  };

  return (
    <Container data-testid="ta-layers-panel">
      <Header>
        <Layers size={14} color="#3b82f6" />
        <Title>10-Layer Market Analysis</Title>
      </Header>

      {/* Market State Grid */}
      <Grid>
        <Cell>
          <CellLabel>Structure</CellLabel>
          <CellValue color={getTrendColor(structure.trend)}>
            {(structure.trend || 'neutral').toUpperCase()}
          </CellValue>
        </Cell>

        <Cell>
          <CellLabel>Impulse</CellLabel>
          <CellValue color={getTrendColor(impulse.direction)}>
            {impulse.has_impulse ? impulse.direction?.toUpperCase() : 'NONE'}
          </CellValue>
          {impulse.has_impulse && (
            <div style={{ fontSize: '9px', color: '#64748b' }}>
              {impulse.strength} • {impulse.bars_ago}b ago
            </div>
          )}
        </Cell>

        <Cell>
          <CellLabel>Regime</CellLabel>
          <CellValue color={getRegimeColor(regime.regime)}>
            {(regime.regime || 'unknown').toUpperCase()}
          </CellValue>
          {regime.state && (
            <div style={{ fontSize: '9px', color: '#64748b' }}>
              {regime.state}
            </div>
          )}
        </Cell>

        <Cell>
          <CellLabel>Bias</CellLabel>
          <CellValue color={getTrendColor(prob.dominant_bias)}>
            {(prob.dominant_bias || 'neutral').toUpperCase()}
          </CellValue>
          <div style={{ fontSize: '9px', color: '#64748b' }}>
            {prob.confidence || 'low'} confidence
          </div>
        </Cell>
      </Grid>

      {/* Probability Bar */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '11px', color: '#22c55e' }}>
            <TrendingUp size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Bullish {prob.bullish || 50}%
          </span>
          <span style={{ fontSize: '11px', color: '#ef4444' }}>
            Bearish {prob.bearish || 50}%
            <TrendingDown size={12} style={{ marginLeft: '4px', verticalAlign: 'middle' }} />
          </span>
        </div>
        <ProbabilityBar>
          <ProbSegment color="#22c55e" width={prob.bullish || 50} />
          <ProbSegment color="#ef4444" width={prob.bearish || 50} />
        </ProbabilityBar>
      </div>

      {/* Scenarios */}
      {scen.break_up && scen.break_down && (
        <ScenariosGrid>
          <ScenarioCard bullish>
            <ScenarioTitle bullish>
              <TrendingUp size={12} />
              BREAK UP
            </ScenarioTitle>
            <ScenarioTarget bullish>
              ${scen.break_up.target?.toLocaleString() || '—'}
            </ScenarioTarget>
            <ScenarioProb>{scen.break_up.probability}% probability</ScenarioProb>
          </ScenarioCard>

          <ScenarioCard>
            <ScenarioTitle>
              <TrendingDown size={12} />
              BREAK DOWN
            </ScenarioTitle>
            <ScenarioTarget>
              ${scen.break_down.target?.toLocaleString() || '—'}
            </ScenarioTarget>
            <ScenarioProb>{scen.break_down.probability}% probability</ScenarioProb>
          </ScenarioCard>
        </ScenariosGrid>
      )}

      {/* Active Range Info */}
      {activeRange && (
        <div style={{
          background: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '8px',
          padding: '10px',
          marginBottom: '12px',
        }}>
          <div style={{ fontSize: '10px', color: '#3b82f6', fontWeight: '600', marginBottom: '6px' }}>
            <Activity size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            ACTIVE RANGE
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '9px', color: '#64748b' }}>RESISTANCE</div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#ef4444' }}>
                ${activeRange.top?.toLocaleString()}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '9px', color: '#64748b' }}>WIDTH</div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#94a3b8' }}>
                {activeRange.width_pct?.toFixed(1)}%
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '9px', color: '#64748b' }}>SUPPORT</div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#22c55e' }}>
                ${activeRange.bottom?.toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Narrative */}
      {narrative && (
        <Narrative>
          {narrative}
        </Narrative>
      )}
    </Container>
  );
};

export default TALayersPanel;
