import React, { useState } from 'react';
import { Shield, AlertTriangle, Power, Zap, Ban, Activity } from 'lucide-react';
import {
  Grid,
  Panel,
  PanelHeader,
  PanelContent,
  MetricCard,
  StatusBadge,
  ProgressBar,
  Button,
  Table
} from '../components/styles';

const RiskPage = () => {
  const [riskState, setRiskState] = useState({
    killSwitchState: false,
    circuitBreakerState: false,
    throttleState: false,
    drawdown: 2.5,
    maxDrawdown: 10,
    blockedTrades: 2,
    var95: 3200,
    var99: 4800
  });

  const [safetyViolations, setSafetyViolations] = useState([
    { id: '1', type: 'Position Limit', message: 'BTC position approaching 80% of limit', severity: 'WARNING', time: '5 min ago' },
    { id: '2', type: 'Throttle', message: 'Order rate reduced due to high volatility', severity: 'INFO', time: '12 min ago' }
  ]);

  const [blockedTrades, setBlockedTrades] = useState([
    { id: '1', symbol: 'SOL', side: 'BUY', size: 200, reason: 'Position limit exceeded', time: '8 min ago' },
    { id: '2', symbol: 'AVAX', side: 'SELL', size: 100, reason: 'Circuit breaker active', time: '15 min ago' }
  ]);

  const toggleKillSwitch = () => {
    setRiskState(prev => ({ ...prev, killSwitchState: !prev.killSwitchState }));
  };

  const toggleCircuitBreaker = () => {
    setRiskState(prev => ({ ...prev, circuitBreakerState: !prev.circuitBreakerState }));
  };

  return (
    <div data-testid="risk-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Risk & Safety</h2>
        <p style={{ fontSize: 13, color: '#738094' }}>System safety controls and risk monitoring</p>
      </div>

      {/* Emergency Controls */}
      <Panel style={{ marginBottom: 20, border: riskState.killSwitchState ? '1px solid #ef4444' : '1px solid #1e2530' }}>
        <PanelHeader>
          <div className="title">Emergency Controls</div>
          <Shield size={16} style={{ color: riskState.killSwitchState ? '#ef4444' : '#05A584' }} />
        </PanelHeader>
        <PanelContent>
          <Grid $cols={3} $gap="20px">
            <div style={{ 
              padding: 20, 
              background: riskState.killSwitchState ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.02)',
              borderRadius: 12,
              border: `1px solid ${riskState.killSwitchState ? 'rgba(239, 68, 68, 0.3)' : '#1e2530'}`,
              textAlign: 'center'
            }}>
              <Power size={32} style={{ color: riskState.killSwitchState ? '#ef4444' : '#4a5568', marginBottom: 12 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Kill Switch</div>
              <div style={{ fontSize: 12, color: '#738094', marginBottom: 16 }}>
                {riskState.killSwitchState ? 'All trading halted' : 'Trading active'}
              </div>
              <Button 
                $variant={riskState.killSwitchState ? 'primary' : 'danger'}
                onClick={toggleKillSwitch}
                style={{ width: '100%' }}
                data-testid="kill-switch-btn"
              >
                {riskState.killSwitchState ? 'Resume Trading' : 'Activate Kill Switch'}
              </Button>
            </div>
            
            <div style={{ 
              padding: 20, 
              background: riskState.circuitBreakerState ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.02)',
              borderRadius: 12,
              border: `1px solid ${riskState.circuitBreakerState ? 'rgba(245, 158, 11, 0.3)' : '#1e2530'}`,
              textAlign: 'center'
            }}>
              <Zap size={32} style={{ color: riskState.circuitBreakerState ? '#f59e0b' : '#4a5568', marginBottom: 12 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Circuit Breaker</div>
              <div style={{ fontSize: 12, color: '#738094', marginBottom: 16 }}>
                {riskState.circuitBreakerState ? 'Auto-triggered' : 'Not triggered'}
              </div>
              <Button 
                $variant={riskState.circuitBreakerState ? 'primary' : 'warning'}
                onClick={toggleCircuitBreaker}
                style={{ width: '100%' }}
              >
                {riskState.circuitBreakerState ? 'Reset Breaker' : 'Trigger Breaker'}
              </Button>
            </div>
            
            <div style={{ 
              padding: 20, 
              background: riskState.throttleState ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.02)',
              borderRadius: 12,
              border: `1px solid ${riskState.throttleState ? 'rgba(245, 158, 11, 0.3)' : '#1e2530'}`,
              textAlign: 'center'
            }}>
              <Activity size={32} style={{ color: riskState.throttleState ? '#f59e0b' : '#4a5568', marginBottom: 12 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Trade Throttle</div>
              <div style={{ fontSize: 12, color: '#738094', marginBottom: 16 }}>
                {riskState.throttleState ? 'Rate limited' : 'Normal rate'}
              </div>
              <StatusBadge $status={riskState.throttleState ? 'NEUTRAL' : 'HEALTHY'} style={{ width: '100%', justifyContent: 'center' }}>
                {riskState.throttleState ? 'THROTTLED' : 'NORMAL'}
              </StatusBadge>
            </div>
          </Grid>
        </PanelContent>
      </Panel>

      <Grid $cols={2} $gap="20px">
        {/* Risk Metrics */}
        <Panel>
          <PanelHeader>
            <div className="title">Risk Metrics</div>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#738094' }}>Current Drawdown</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: riskState.drawdown > 5 ? '#ef4444' : '#f59e0b' }}>
                  {riskState.drawdown}%
                </span>
              </div>
              <ProgressBar $value={(riskState.drawdown / riskState.maxDrawdown) * 100} $color={riskState.drawdown > 5 ? '#ef4444' : '#f59e0b'}>
                <div className="fill" />
              </ProgressBar>
              <div style={{ fontSize: 11, color: '#4a5568', marginTop: 4 }}>
                Max allowed: {riskState.maxDrawdown}%
              </div>
            </div>
            
            <Grid $cols={2} $gap="12px">
              <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>VaR (95%)</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: '#f59e0b' }}>${riskState.var95.toLocaleString()}</div>
              </div>
              <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>VaR (99%)</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: '#ef4444' }}>${riskState.var99.toLocaleString()}</div>
              </div>
            </Grid>
          </PanelContent>
        </Panel>

        {/* Safety Violations */}
        <Panel>
          <PanelHeader>
            <div className="title">Safety Violations</div>
            <AlertTriangle size={16} style={{ color: '#f59e0b' }} />
          </PanelHeader>
          <PanelContent>
            {safetyViolations.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: '#05A584' }}>
                No active violations
              </div>
            ) : (
              safetyViolations.map(violation => (
                <div 
                  key={violation.id}
                  style={{
                    padding: 12,
                    background: violation.severity === 'WARNING' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                    borderRadius: 8,
                    marginBottom: 8,
                    borderLeft: `3px solid ${violation.severity === 'WARNING' ? '#f59e0b' : '#05A584'}`
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>{violation.type}</span>
                    <StatusBadge $status={violation.severity === 'WARNING' ? 'NEUTRAL' : 'HEALTHY'}>
                      {violation.severity}
                    </StatusBadge>
                  </div>
                  <div style={{ fontSize: 12, color: '#a0aec0', marginBottom: 4 }}>{violation.message}</div>
                  <div style={{ fontSize: 10, color: '#4a5568' }}>{violation.time}</div>
                </div>
              ))
            )}
          </PanelContent>
        </Panel>
      </Grid>

      {/* Blocked Trades */}
      <Panel style={{ marginTop: 20 }}>
        <PanelHeader>
          <div className="title">Blocked Trades</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Ban size={16} style={{ color: '#ef4444' }} />
            <span style={{ fontSize: 13, color: '#ef4444' }}>{blockedTrades.length} blocked</span>
          </div>
        </PanelHeader>
        <PanelContent style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Reason</th>
                <th>Time</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {blockedTrades.map(trade => (
                <tr key={trade.id}>
                  <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{trade.symbol}</td>
                  <td>
                    <StatusBadge $status={trade.side}>{trade.side}</StatusBadge>
                  </td>
                  <td>{trade.size}</td>
                  <td style={{ color: '#ef4444' }}>{trade.reason}</td>
                  <td style={{ color: '#738094' }}>{trade.time}</td>
                  <td>
                    <Button $variant="ghost" style={{ padding: '4px 8px', fontSize: 11 }}>
                      Override
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </PanelContent>
      </Panel>
    </div>
  );
};

export default RiskPage;
