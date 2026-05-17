/**
 * Execution Tab — Action Layer
 * =============================
 * 
 * "Що робити руками"
 * 
 * Contains:
 * - Trade Levels (resistance/invalidation)
 * - Setup Card
 * - Scenarios (bullish/bearish)
 * - Risk Block
 * - Final Action
 */

import React from 'react';
import styled from 'styled-components';
import { Target, AlertTriangle, TrendingUp, TrendingDown, Shield, Zap, CheckCircle, XCircle, Clock, AlertOctagon, AlertCircle } from 'lucide-react';

// Import existing components
import ScenariosBlock from '../../components/ScenariosBlock';
import ExecutionPanel from '../../components/ExecutionPanel';
import UnifiedSetupPanel from '../../components/UnifiedSetupPanel';
import TACompositionPanel from '../../components/TACompositionPanel';
import EntryCard from '../../components/EntryCard';

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

const LevelsGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const LevelCard = styled.div`
  padding: 16px;
  border-radius: 10px;
  background: ${p => p.$type === 'resistance' ? 'rgba(34, 197, 94, 0.06)' : 'rgba(239, 68, 68, 0.06)'};
  border: 1px solid ${p => p.$type === 'resistance' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)'};
  
  .label {
    font-size: 10px;
    font-weight: 700;
    color: ${p => p.$type === 'resistance' ? '#16a34a' : '#dc2626'};
    text-transform: uppercase;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .price {
    font-size: 22px;
    font-weight: 700;
    color: ${p => p.$type === 'resistance' ? '#16a34a' : '#dc2626'};
    margin-bottom: 4px;
  }
  
  .hint {
    font-size: 11px;
    color: #64748b;
  }
`;

const SetupCard = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
`;

const SetupItem = styled.div`
  text-align: center;
  
  .label {
    font-size: 10px;
    color: #94a3b8;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  
  .value {
    font-size: 14px;
    font-weight: 700;
    color: ${p => p.$highlight === 'bullish' ? '#16a34a' :
                  p.$highlight === 'bearish' ? '#dc2626' :
                  p.$highlight === 'high' ? '#16a34a' :
                  p.$highlight === 'medium' ? '#f59e0b' :
                  p.$highlight === 'low' ? '#dc2626' : '#0f172a'};
    text-transform: capitalize;
  }
`;

const RiskBlock = styled.div`
  padding: 16px;
  background: linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%);
  border: 1px solid #fecaca;
  border-radius: 10px;
  
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    
    .icon {
      color: #dc2626;
    }
    
    .title {
      font-size: 12px;
      font-weight: 700;
      color: #dc2626;
      text-transform: uppercase;
    }
  }
  
  .content {
    font-size: 13px;
    color: #7c2d12;
    line-height: 1.5;
  }
`;

const ActionBlock = styled.div`
  padding: 20px;
  background: ${p => p.$action === 'enter' ? 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)' :
                     p.$action === 'exit' ? 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)' :
                     'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)'};
  border: 2px solid ${p => p.$action === 'enter' ? '#22c55e' :
                          p.$action === 'exit' ? '#ef4444' : '#e2e8f0'};
  border-radius: 12px;
  text-align: center;
  
  .icon {
    margin-bottom: 10px;
    color: ${p => p.$action === 'enter' ? '#22c55e' :
                  p.$action === 'exit' ? '#ef4444' : '#94a3b8'};
  }
  
  .action {
    font-size: 18px;
    font-weight: 700;
    color: ${p => p.$action === 'enter' ? '#16a34a' :
                  p.$action === 'exit' ? '#dc2626' : '#0f172a'};
    margin-bottom: 8px;
  }
  
  .reason {
    font-size: 13px;
    color: ${p => p.$action === 'enter' ? '#15803d' :
                  p.$action === 'exit' ? '#b91c1c' : '#64748b'};
  }
`;

const BottomGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  
  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
`;

const ExecutionTab = ({
  setupData,
  decision,
  levels,
  primaryPattern,
  scenarios,
  onScenarioClick,
  taComposition,
  contextFit,
  tradeable,
  historical,
  executionPlan,
  probabilityV3,
  regimeDrift,
}) => {
  // Extract levels
  const resistances = levels?.filter(l => l.type === 'resistance') || [];
  const supports = levels?.filter(l => l.type === 'support') || [];
  
  const resistanceBreak = resistances[0]?.price || setupData?.breakout_level;
  const invalidationLevel = supports[0]?.price || setupData?.invalidation_level;
  
  // Setup data
  const patternType = primaryPattern?.type?.replace(/_/g, ' ') || 'None';
  const bias = decision?.bias || 'neutral';
  const quality = decision?.tradeability || 'low';
  
  // Context fit data
  const fitLabel = contextFit?.label || 'MEDIUM';
  
  // Execution Plan data
  const plan = executionPlan || {};
  const hasPlan = plan?.status === 'ACTIVE';
  const planEntry = plan?.entry;
  const planStop = plan?.stop;
  const planTarget = plan?.target;
  const planRR = plan?.rr;
  const planQuality = plan?.quality || 'MEDIUM';
  const planTimeH = plan?.time_window?.expected_hours;
  const planRiskPct = plan?.risk_pct;
  
  // Probability V3 data for expectation
  const expectation = probabilityV3?.expectation || {};
  const expectedMove = expectation?.move_pct;
  const finalConfidence = probabilityV3?.final_confidence;
  const fitScore = contextFit?.score || 1.0;
  
  // Historical fit data
  const histFit = historical?.fit || {};
  const histLabel = histFit?.label || 'INSUFFICIENT';
  const histWinrate = histFit?.winrate;
  
  // Regime Drift data
  const hasDrift = regimeDrift?.drift_detected && regimeDrift?.severity !== 'NONE';
  const driftSeverity = regimeDrift?.severity || 'NONE';
  const driftInvalidated = driftSeverity === 'HIGH';
  
  // Tradeable considers context, historical, AND drift
  const contextOk = fitLabel !== 'LOW';
  const historyOk = histLabel !== 'POOR';
  const driftOk = !driftInvalidated;
  const isTradeable = tradeable !== false && contextOk && historyOk && driftOk;
  
  // Determine action - now considers context fit, historical, AND regime drift
  let actionType = 'wait';
  let actionText = 'No trade — wait for confirmation';
  let actionReason = 'Structure not yet confirmed for entry';
  
  if (driftInvalidated) {
    actionType = 'exit';
    actionText = 'Context changed — plan invalidated';
    actionReason = `Market regime has shifted significantly. Re-evaluate setup.`;
  } else if (!contextOk) {
    actionType = 'wait';
    actionText = 'Context mismatch — do not trade';
    actionReason = `Pattern poorly aligned with market context (${fitLabel})`;
  } else if (!historyOk) {
    actionType = 'wait';
    actionText = 'Poor historical performance — avoid trade';
    actionReason = `This pattern historically underperforms in current context (${histLabel})`;
  } else if (hasDrift && driftSeverity === 'MEDIUM') {
    actionType = 'wait';
    actionText = 'Context shifted — proceed with caution';
    actionReason = `Market context has changed. Consider tighter stops or reduced size.`;
  } else if (quality === 'high' && decision?.confidence >= 0.6) {
    actionType = 'enter';
    actionText = 'Setup ready — consider entry';
    let extraInfo = '';
    if (fitLabel === 'HIGH') extraInfo += ' + strong context';
    if (histLabel === 'STRONG' || histLabel === 'GOOD') extraInfo += ` + ${histWinrate ? Math.round(histWinrate*100) + '% historical winrate' : 'good history'}`;
    actionReason = `${bias.toUpperCase()} bias with high confidence${extraInfo}`;
  } else if (primaryPattern?.lifecycle === 'invalidated') {
    actionType = 'exit';
    actionText = 'Setup invalidated — avoid entry';
    actionReason = 'Pattern structure broken';
  }
  
  // Risk text
  const riskText = `Define stop-loss before entry. ${
    invalidationLevel 
      ? `Invalidation below $${invalidationLevel.toLocaleString()}.`
      : 'Wait for clear invalidation level.'
  }`;
  
  return (
    <Container data-testid="execution-tab">
      {/* Trade Levels */}
      <Card>
        <SectionTitle>
          <Target />
          Trade Levels
        </SectionTitle>
        <LevelsGrid data-testid="trade-levels">
          <LevelCard $type="resistance">
            <div className="label">
              <TrendingUp size={12} />
              Resistance Break
            </div>
            <div className="price">
              {resistanceBreak ? `$${resistanceBreak.toLocaleString()}` : '—'}
            </div>
            <div className="hint">breakout target</div>
          </LevelCard>
          <LevelCard $type="invalidation">
            <div className="label">
              <AlertTriangle size={12} />
              Invalidation
            </div>
            <div className="price">
              {invalidationLevel ? `$${invalidationLevel.toLocaleString()}` : '—'}
            </div>
            <div className="hint">stop-loss zone</div>
          </LevelCard>
        </LevelsGrid>
      </Card>
      
      {/* REGIME DRIFT ALERT - Shows if context has changed */}
      {hasDrift && (
        <Card style={{
          background: driftSeverity === 'HIGH' 
            ? 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)'
            : driftSeverity === 'MEDIUM'
            ? 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)'
            : 'linear-gradient(135deg, #fefce8 0%, #fef3c7 100%)',
          border: `2px solid ${driftSeverity === 'HIGH' ? '#ef4444' 
                              : driftSeverity === 'MEDIUM' ? '#f97316' 
                              : '#eab308'}`,
        }} data-testid="drift-alert">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: driftSeverity === 'HIGH' ? 'rgba(239, 68, 68, 0.15)' 
                        : driftSeverity === 'MEDIUM' ? 'rgba(249, 115, 22, 0.15)' 
                        : 'rgba(234, 179, 8, 0.15)',
              color: driftSeverity === 'HIGH' ? '#ef4444' 
                   : driftSeverity === 'MEDIUM' ? '#f97316' 
                   : '#eab308',
            }}>
              {driftSeverity === 'HIGH' && <AlertOctagon size={22} />}
              {driftSeverity === 'MEDIUM' && <AlertTriangle size={22} />}
              {driftSeverity === 'LOW' && <AlertCircle size={22} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ 
                fontSize: '14px', 
                fontWeight: 700, 
                color: driftSeverity === 'HIGH' ? '#dc2626' 
                     : driftSeverity === 'MEDIUM' ? '#ea580c' 
                     : '#ca8a04',
                marginBottom: '4px'
              }}>
                {driftSeverity === 'HIGH' && 'Execution Plan Invalidated'}
                {driftSeverity === 'MEDIUM' && 'Context Shifted — Caution Advised'}
                {driftSeverity === 'LOW' && 'Minor Context Change'}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                {regimeDrift?.message || 'Market context has changed since plan was built'}
              </div>
              {regimeDrift?.changes?.length > 0 && (
                <div style={{ 
                  marginTop: '8px',
                  display: 'flex',
                  gap: '8px',
                  flexWrap: 'wrap'
                }}>
                  {regimeDrift.changes.map((c, i) => (
                    <span key={i} style={{
                      padding: '3px 8px',
                      background: 'rgba(0,0,0,0.05)',
                      borderRadius: '4px',
                      fontSize: '11px',
                      color: '#475569',
                    }}>
                      {c.field}: {c.from} → {c.to}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div style={{
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
              background: driftSeverity === 'HIGH' ? '#ef4444' 
                        : driftSeverity === 'MEDIUM' ? '#f97316' 
                        : '#eab308',
              color: 'white',
            }}>
              {driftSeverity}
            </div>
          </div>
          {driftSeverity === 'HIGH' && (
            <div style={{
              marginTop: '12px',
              padding: '10px',
              background: 'rgba(239, 68, 68, 0.1)',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#b91c1c',
              fontWeight: 500,
            }}>
              ⚠️ {regimeDrift?.recommendation || 'Re-evaluate setup before entering. Context changed significantly.'}
            </div>
          )}
        </Card>
      )}
      
      {/* EXECUTION PLAN - NEW! */}
      {hasPlan && (
        <Card style={{
          background: planQuality === 'EXCELLENT' || planQuality === 'HIGH' 
            ? 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'
            : planQuality === 'GOOD' || planQuality === 'MEDIUM'
            ? 'linear-gradient(135deg, #fefce8 0%, #fef3c7 100%)'
            : 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
          border: `2px solid ${planQuality === 'EXCELLENT' || planQuality === 'HIGH' ? '#22c55e' 
                              : planQuality === 'GOOD' || planQuality === 'MEDIUM' ? '#eab308' 
                              : '#ef4444'}`,
        }} data-testid="execution-plan">
          <SectionTitle>
            <Target />
            Execution Plan
            <span style={{
              marginLeft: 'auto',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '9px',
              fontWeight: 700,
              background: planQuality === 'EXCELLENT' || planQuality === 'HIGH' ? '#22c55e' 
                        : planQuality === 'GOOD' || planQuality === 'MEDIUM' ? '#eab308' 
                        : '#ef4444',
              color: 'white',
            }}>
              {planQuality}
            </span>
          </SectionTitle>
          
          {/* Entry / Stop / Target Grid */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(3, 1fr)', 
            gap: '12px',
            marginBottom: '16px',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                Entry
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                ${planEntry?.toLocaleString()}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#dc2626', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                Stop
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#dc2626' }}>
                ${planStop?.toLocaleString()}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#16a34a', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                Target
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#16a34a' }}>
                ${planTarget?.toLocaleString()}
              </div>
            </div>
          </div>
          
          {/* R/R and Time Row */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-around',
            padding: '12px',
            background: 'rgba(255,255,255,0.5)',
            borderRadius: '8px',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>R/R</div>
              <div style={{ fontSize: '16px', fontWeight: 700, color: planRR >= 2 ? '#16a34a' : planRR >= 1.2 ? '#eab308' : '#dc2626' }}>
                {planRR?.toFixed(1)}:1
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>Risk</div>
              <div style={{ fontSize: '16px', fontWeight: 700, color: '#475569' }}>
                {planRiskPct?.toFixed(1)}%
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>Time</div>
              <div style={{ fontSize: '16px', fontWeight: 700, color: '#475569' }}>
                {planTimeH < 24 ? `~${Math.round(planTimeH)}h` : `~${(planTimeH / 24).toFixed(1)}d`}
              </div>
            </div>
            {expectedMove && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>Expected</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: '#3b82f6' }}>
                  ~{expectedMove}%
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
      
      {/* Setup Card */}
      <Card>
        <SectionTitle>
          <Zap />
          Setup Quality
        </SectionTitle>
        <SetupCard data-testid="setup-card">
          <SetupItem>
            <div className="label">Pattern</div>
            <div className="value">{patternType}</div>
          </SetupItem>
          <SetupItem $highlight={bias}>
            <div className="label">Bias</div>
            <div className="value">{bias}</div>
          </SetupItem>
          <SetupItem $highlight={quality}>
            <div className="label">Quality</div>
            <div className="value">{quality.replace(/_/g, ' ')}</div>
          </SetupItem>
        </SetupCard>
      </Card>
      
      {/* Entry Card - Always show with status */}
      <EntryCard 
        setup={setupData?.entry_setup || setupData?.trade_setup || {
          available: false,
          lifecycle: primaryPattern?.lifecycle,
          reason: !primaryPattern ? 'No pattern detected' :
                  primaryPattern?.lifecycle === 'forming' ? 'Pattern still forming' :
                  primaryPattern?.lifecycle === 'developing' ? 'Pattern developing, awaiting confirmation' :
                  primaryPattern?.lifecycle === 'invalidated' ? 'Pattern has been invalidated' :
                  quality === 'low' ? 'Setup quality too low for entry' :
                  'Waiting for confirmation',
          advice: primaryPattern?.lifecycle === 'forming' ? 'Watch for structure completion' :
                  primaryPattern?.lifecycle === 'developing' ? 'Monitor for breakout above resistance' :
                  primaryPattern?.lifecycle === 'invalidated' ? 'Look for new pattern formation' :
                  quality === 'low' ? 'Wait for higher quality setup' :
                  'Wait for confirmed entry signal',
          pattern: patternType,
          bias: bias,
          confidence: decision?.confidence,
          confidence_low: decision?.confidence < 0.5,
          context_mismatch: fitLabel === 'LOW',
          range_bound: setupData?.structure_context?.market_state === 'range',
        }} 
        intelligence={setupData?.intelligence}
      />
      
      <BottomGrid>
        {/* Scenarios */}
        <Card>
          <SectionTitle>
            <TrendingUp />
            Scenarios
          </SectionTitle>
          <ScenariosBlock
            scenarios={scenarios}
            onScenarioClick={onScenarioClick}
          />
        </Card>
        
        {/* TA Composition */}
        <TACompositionPanel composition={taComposition} />
      </BottomGrid>
      
      {/* Risk Block */}
      <RiskBlock data-testid="risk-block">
        <div className="header">
          <Shield size={16} className="icon" />
          <span className="title">Risk Management</span>
        </div>
        <div className="content">{riskText}</div>
      </RiskBlock>
      
      {/* Final Action */}
      <ActionBlock $action={actionType} data-testid="final-action">
        <div className="icon">
          {actionType === 'enter' && <CheckCircle size={32} />}
          {actionType === 'exit' && <XCircle size={32} />}
          {actionType === 'wait' && <Clock size={32} />}
        </div>
        <div className="action">{actionText}</div>
        <div className="reason">{actionReason}</div>
      </ActionBlock>
      
      {/* Unified Setup + Execution Grid */}
      {(setupData?.unified_setup || setupData?.execution_plan) && (
        <BottomGrid>
          <UnifiedSetupPanel unifiedSetup={setupData.unified_setup} />
          <ExecutionPanel executionPlan={setupData.execution_plan} />
        </BottomGrid>
      )}
    </Container>
  );
};

export default ExecutionTab;
