import React, { useState } from 'react';
import { TrendingUp, TrendingDown, AlertTriangle, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import {
  Grid,
  Panel,
  PanelHeader,
  PanelContent,
  StatusBadge,
  ProgressBar,
  HypothesisCard,
  Button
} from '../components/styles';

const HypothesesPage = () => {
  const [expandedId, setExpandedId] = useState('1');
  
  const [hypotheses, setHypotheses] = useState([
    {
      id: '1',
      type: 'BREAKOUT_CONTINUATION',
      direction: 'LONG',
      confidence: 0.82,
      reliability: 0.78,
      alphaFamily: 'Momentum',
      decayStage: 'FRESH',
      scenarioAlignment: 0.85,
      capitalFlowAlignment: 0.72,
      fractalAlignment: 0.88,
      explanation: 'Strong momentum breakout above key resistance with volume confirmation. Historical pattern match suggests continuation to next major level.',
      conflicts: ['Overbought RSI on 4H timeframe', 'Approaching weekly resistance'],
      executionEligibility: true
    },
    {
      id: '2',
      type: 'MEAN_REVERSION',
      direction: 'SHORT',
      confidence: 0.68,
      reliability: 0.72,
      alphaFamily: 'Statistical',
      decayStage: 'MATURE',
      scenarioAlignment: 0.62,
      capitalFlowAlignment: 0.45,
      fractalAlignment: 0.58,
      explanation: 'Price extended beyond 2 standard deviations. Statistical reversion expected within 24-48 hours.',
      conflicts: ['Strong trend momentum', 'Capital flow bullish'],
      executionEligibility: true
    },
    {
      id: '3',
      type: 'RANGE_BREAKOUT',
      direction: 'LONG',
      confidence: 0.58,
      reliability: 0.65,
      alphaFamily: 'Pattern',
      decayStage: 'MATURE',
      scenarioAlignment: 0.55,
      capitalFlowAlignment: 0.68,
      fractalAlignment: 0.52,
      explanation: 'Consolidation pattern nearing completion. Breakout expected on volume expansion.',
      conflicts: ['Low volatility environment', 'Weak momentum confirmation'],
      executionEligibility: false
    },
    {
      id: '4',
      type: 'TREND_CONTINUATION',
      direction: 'LONG',
      confidence: 0.52,
      reliability: 0.58,
      alphaFamily: 'Trend',
      decayStage: 'DECAYING',
      scenarioAlignment: 0.48,
      capitalFlowAlignment: 0.55,
      fractalAlignment: 0.45,
      explanation: 'Pullback to support in established uptrend. Entry on confirmation of support hold.',
      conflicts: ['Weakening trend strength', 'Diverging indicators'],
      executionEligibility: false
    }
  ]);

  const getDecayColor = (stage) => {
    switch (stage) {
      case 'FRESH': return '#05A584';
      case 'MATURE': return '#f59e0b';
      case 'DECAYING': return '#ef4444';
      case 'EXPIRED': return '#4a5568';
      default: return '#738094';
    }
  };

  return (
    <div data-testid="hypotheses-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#0f172a', marginBottom: 8 }}>Active Hypotheses</h2>
        <p style={{ fontSize: 14, color: '#738094' }}>Competing market scenarios ranked by confidence and reliability</p>
      </div>

      {/* Top Hypothesis - Expanded */}
      <Panel style={{ marginBottom: 20, border: '2px solid #05A584' }}>
        <PanelHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ 
              padding: '5px 10px', 
              background: '#e8f9f1', 
              borderRadius: 6, 
              fontSize: 11, 
              fontWeight: 600, 
              color: '#05A584' 
            }}>
              TOP HYPOTHESIS
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#0f172a' }}>
              {hypotheses[0].type.replace(/_/g, ' ')}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <StatusBadge $status={hypotheses[0].direction}>{hypotheses[0].direction}</StatusBadge>
            {hypotheses[0].direction === 'LONG' ? 
              <TrendingUp size={20} style={{ color: '#05A584' }} /> : 
              <TrendingDown size={20} style={{ color: '#ef4444' }} />
            }
          </div>
        </PanelHeader>
        <PanelContent>
          <Grid $cols={4} style={{ marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Confidence</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#05A584' }}>{(hypotheses[0].confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Reliability</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#0f172a' }}>{(hypotheses[0].reliability * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Alpha Family</div>
              <div style={{ fontSize: 18, fontWeight: 600, color: '#0f172a' }}>{hypotheses[0].alphaFamily}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Decay Stage</div>
              <div style={{ fontSize: 18, fontWeight: 600, color: getDecayColor(hypotheses[0].decayStage) }}>
                {hypotheses[0].decayStage}
              </div>
            </div>
          </Grid>
          
          {/* Alignment Bars */}
          <Grid $cols={3} style={{ marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: '#738094' }}>Scenario Alignment</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{(hypotheses[0].scenarioAlignment * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar $value={hypotheses[0].scenarioAlignment * 100} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: '#738094' }}>Capital Flow</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{(hypotheses[0].capitalFlowAlignment * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar $value={hypotheses[0].capitalFlowAlignment * 100} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: '#738094' }}>Fractal Match</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{(hypotheses[0].fractalAlignment * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar $value={hypotheses[0].fractalAlignment * 100} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
          </Grid>
          
          {/* Explanation */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: '#05A584', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
              <Zap size={14} /> Explanation
            </div>
            <div style={{ fontSize: 14, color: '#0f172a', lineHeight: 1.6 }}>
              {hypotheses[0].explanation}
            </div>
          </div>
          
          {/* Conflicts */}
          {hypotheses[0].conflicts.length > 0 && (
            <div style={{ 
              padding: 14, 
              background: 'rgba(245, 158, 11, 0.08)', 
              borderRadius: 10,
              border: '1px solid rgba(245, 158, 11, 0.15)'
            }}>
              <div style={{ fontSize: 13, color: '#f59e0b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                <AlertTriangle size={14} /> Conflicts
              </div>
              {hypotheses[0].conflicts.map((conflict, i) => (
                <div key={i} style={{ fontSize: 14, color: '#738094', marginBottom: 4 }}>
                  • {conflict}
                </div>
              ))}
            </div>
          )}
          
          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button $variant="ghost">View Details</Button>
            <Button $variant="primary" disabled={!hypotheses[0].executionEligibility}>
              Send to Execution
            </Button>
          </div>
        </PanelContent>
      </Panel>

      {/* Competing Hypotheses */}
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#9CA3AF', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Competing Hypotheses</h3>
      </div>
      
      <Grid $cols={1} $gap="12px">
        {hypotheses.slice(1).map((hyp, index) => (
          <HypothesisCard 
            key={hyp.id}
            $isTop={false}
            onClick={() => setExpandedId(expandedId === hyp.id ? null : hyp.id)}
            data-testid={`hypothesis-${hyp.id}`}
          >
            <div className="header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className="type">{hyp.type.replace(/_/g, ' ')}</span>
                <StatusBadge $status={hyp.direction}>{hyp.direction}</StatusBadge>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 11, color: getDecayColor(hyp.decayStage) }}>{hyp.decayStage}</span>
                {expandedId === hyp.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>
            
            <div className="metrics">
              <div className="metric">
                <div className="label">Confidence</div>
                <div className="value" style={{ color: '#05A584' }}>{(hyp.confidence * 100).toFixed(0)}%</div>
              </div>
              <div className="metric">
                <div className="label">Reliability</div>
                <div className="value">{(hyp.reliability * 100).toFixed(0)}%</div>
              </div>
              <div className="metric">
                <div className="label">Alpha</div>
                <div className="value">{hyp.alphaFamily}</div>
              </div>
            </div>
            
            {expandedId === hyp.id && (
              <>
                <div className="explanation" style={{ marginBottom: 12 }}>
                  {hyp.explanation}
                </div>
                
                {hyp.conflicts.length > 0 && (
                  <div style={{ fontSize: 12, color: '#f59e0b' }}>
                    Conflicts: {hyp.conflicts.join(', ')}
                  </div>
                )}
                
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                  <Button $variant="ghost" style={{ fontSize: 12, padding: '6px 12px' }}>Details</Button>
                  <Button 
                    $variant="primary" 
                    style={{ fontSize: 12, padding: '6px 12px' }}
                    disabled={!hyp.executionEligibility}
                  >
                    Execute
                  </Button>
                </div>
              </>
            )}
          </HypothesisCard>
        ))}
      </Grid>
    </div>
  );
};

export default HypothesesPage;
