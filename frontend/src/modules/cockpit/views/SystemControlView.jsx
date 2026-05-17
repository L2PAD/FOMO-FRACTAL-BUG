import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { Server, CheckCircle, AlertTriangle, Wifi, Power, Zap, Activity, Shield } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const ControlsPanel = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 20px 24px;
`;

const ControlsTitle = styled.div`
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 20px;
`;

const ControlsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
`;

const ControlCard = styled.div`
  padding: 20px;
  border-radius: 12px;
  text-align: center;
  border: 1px solid ${({ $active, $type }) => $active && $type === 'danger' ? 'rgba(239, 68, 68, 0.3)' : '#eef1f5'};
  background: ${({ $active, $type }) => $active && $type === 'danger' ? 'rgba(239, 68, 68, 0.05)' : '#f9fafb'};
`;

const ControlIcon = styled.div`
  margin-bottom: 12px;
  color: ${({ $active, $type }) => $active && $type === 'danger' ? '#ef4444' : '#9CA3AF'};
`;

const ControlTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
`;

const ControlStatus = styled.div`
  font-size: 12px;
  color: #738094;
  margin-bottom: 16px;
`;

const ControlButton = styled.button`
  width: 100%;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  
  ${({ $active, $type }) => {
    if ($active && $type === 'danger') {
      return 'background: #05A584; color: white; &:hover { background: #048a6e; }';
    }
    if ($type === 'danger') {
      return 'background: rgba(239, 68, 68, 0.1); color: #ef4444; &:hover { background: rgba(239, 68, 68, 0.15); }';
    }
    return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b; &:hover { background: rgba(245, 158, 11, 0.15); }';
  }}
`;

const MetricsRow = styled.div`
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
`;

const MetricCard = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 16px;
  
  .label {
    font-size: 11px;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }
  
  .value {
    font-size: 20px;
    font-weight: 700;
    color: ${({ $color }) => $color || '#0f172a'};
  }
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
`;

const Panel = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  overflow: hidden;
`;

const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #eef1f5;
  
  .title {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
  }
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  
  th {
    text-align: left;
    padding: 12px 16px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9CA3AF;
    background: #f9fafb;
    border-bottom: 1px solid #eef1f5;
  }
  
  td {
    padding: 12px 16px;
    font-size: 14px;
    color: #0f172a;
    border-bottom: 1px solid #eef1f5;
  }
  
  tr:last-child td {
    border-bottom: none;
  }
`;

const Badge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: ${({ $type }) => $type === 'healthy' ? '#e8f9f1' : $type === 'degraded' ? 'rgba(245, 158, 11, 0.1)' : '#f5f7fa'};
  color: ${({ $type }) => $type === 'healthy' ? '#05A584' : $type === 'degraded' ? '#f59e0b' : '#738094'};
`;

const ProgressBar = styled.div`
  height: 6px;
  background: #eef1f5;
  border-radius: 3px;
  overflow: hidden;
  
  .fill {
    height: 100%;
    background: ${({ $color }) => $color || '#05A584'};
    width: ${({ $value }) => $value}%;
    border-radius: 3px;
  }
`;

// ============================================
// MOCK DATA
// ============================================

const services = [
  { name: 'API Gateway', status: 'HEALTHY', uptime: 99.99, latency: 42 },
  { name: 'TA Engine', status: 'HEALTHY', uptime: 99.95, latency: 58 },
  { name: 'Data Pipeline', status: 'HEALTHY', uptime: 99.90, latency: 35 },
  { name: 'Execution Engine', status: 'HEALTHY', uptime: 99.98, latency: 28 },
  { name: 'MongoDB', status: 'HEALTHY', uptime: 99.99, latency: 12 }
];

const exchanges = [
  { name: 'Binance', status: 'CONNECTED', latency: 42, ws: 'OPEN' },
  { name: 'Coinbase', status: 'CONNECTED', latency: 58, ws: 'OPEN' },
  { name: 'Kraken', status: 'DEGRADED', latency: 180, ws: 'RECONNECTING' }
];

// ============================================
// COMPONENT
// ============================================

const SystemControlView = () => {
  const [killSwitch, setKillSwitch] = useState(false);
  const [circuitBreaker, setCircuitBreaker] = useState(false);
  const [throttle, setThrottle] = useState(false);
  const [validationScore, setValidationScore] = useState(98);

  return (
    <Container data-testid="system-control-view">
      {/* Emergency Controls */}
      <ControlsPanel>
        <ControlsTitle>Emergency Controls</ControlsTitle>
        <ControlsGrid>
          <ControlCard $active={killSwitch} $type="danger">
            <ControlIcon $active={killSwitch} $type="danger">
              <Power size={32} />
            </ControlIcon>
            <ControlTitle>Kill Switch</ControlTitle>
            <ControlStatus>{killSwitch ? 'All trading halted' : 'Trading active'}</ControlStatus>
            <ControlButton $active={killSwitch} $type="danger" onClick={() => setKillSwitch(!killSwitch)}>
              {killSwitch ? 'Resume Trading' : 'Activate Kill Switch'}
            </ControlButton>
          </ControlCard>
          
          <ControlCard $active={circuitBreaker} $type="warning">
            <ControlIcon $active={circuitBreaker}>
              <Zap size={32} />
            </ControlIcon>
            <ControlTitle>Circuit Breaker</ControlTitle>
            <ControlStatus>{circuitBreaker ? 'Auto-triggered' : 'Not triggered'}</ControlStatus>
            <ControlButton $active={circuitBreaker} onClick={() => setCircuitBreaker(!circuitBreaker)}>
              {circuitBreaker ? 'Reset Breaker' : 'Trigger Breaker'}
            </ControlButton>
          </ControlCard>
          
          <ControlCard $active={throttle}>
            <ControlIcon $active={throttle}>
              <Activity size={32} />
            </ControlIcon>
            <ControlTitle>Trade Throttle</ControlTitle>
            <ControlStatus>{throttle ? 'Rate limited' : 'Normal rate'}</ControlStatus>
            <Badge $type={throttle ? 'degraded' : 'healthy'} style={{ width: '100%', justifyContent: 'center' }}>
              {throttle ? 'THROTTLED' : 'NORMAL'}
            </Badge>
          </ControlCard>
        </ControlsGrid>
      </ControlsPanel>
      
      {/* System Metrics */}
      <MetricsRow>
        <MetricCard $color={validationScore >= 95 ? '#05A584' : '#f59e0b'}>
          <div className="label">Validation Score</div>
          <div className="value">{validationScore}%</div>
        </MetricCard>
        <MetricCard>
          <div className="label">Avg Latency</div>
          <div className="value">45ms</div>
        </MetricCard>
        <MetricCard>
          <div className="label">P95 Latency</div>
          <div className="value">120ms</div>
        </MetricCard>
        <MetricCard $color="#05A584">
          <div className="label">Throughput</div>
          <div className="value">1,250/s</div>
        </MetricCard>
        <MetricCard $color="#05A584">
          <div className="label">Error Rate</div>
          <div className="value">0.02%</div>
        </MetricCard>
      </MetricsRow>
      
      <Grid>
        {/* Service Health */}
        <Panel>
          <PanelHeader>
            <span className="title">Service Health</span>
            <CheckCircle size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <Table>
            <thead>
              <tr>
                <th>Service</th>
                <th>Status</th>
                <th>Uptime</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {services.map(svc => (
                <tr key={svc.name}>
                  <td style={{ fontWeight: 500 }}>{svc.name}</td>
                  <td><Badge $type="healthy">{svc.status}</Badge></td>
                  <td style={{ color: svc.uptime >= 99.9 ? '#05A584' : '#f59e0b' }}>{svc.uptime}%</td>
                  <td>{svc.latency}ms</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>
        
        {/* Exchange Connectivity */}
        <Panel>
          <PanelHeader>
            <span className="title">Exchange Connectivity</span>
            <Wifi size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <Table>
            <thead>
              <tr>
                <th>Exchange</th>
                <th>Status</th>
                <th>Latency</th>
                <th>WebSocket</th>
              </tr>
            </thead>
            <tbody>
              {exchanges.map(ex => (
                <tr key={ex.name}>
                  <td style={{ fontWeight: 500 }}>{ex.name}</td>
                  <td><Badge $type={ex.status === 'CONNECTED' ? 'healthy' : 'degraded'}>{ex.status}</Badge></td>
                  <td style={{ color: ex.latency > 100 ? '#f59e0b' : '#05A584' }}>{ex.latency}ms</td>
                  <td><Badge $type={ex.ws === 'OPEN' ? 'healthy' : 'degraded'}>{ex.ws}</Badge></td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>
      </Grid>
      
      {/* Validation Progress */}
      <Panel>
        <PanelHeader>
          <span className="title">Validation Status</span>
          <Shield size={16} style={{ color: '#738094' }} />
        </PanelHeader>
        <div style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 13, color: '#738094' }}>Overall Validation</span>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#05A584' }}>{validationScore}%</span>
          </div>
          <ProgressBar $value={validationScore}>
            <div className="fill" />
          </ProgressBar>
          <div style={{ display: 'flex', gap: 24, marginTop: 16 }}>
            <Badge $type="healthy">Coefficient Audit: PASSED</Badge>
            <Badge $type="healthy">Integration Audit: PASSED</Badge>
            <Badge $type="healthy">Stress Test: PASSED</Badge>
          </div>
        </div>
      </Panel>
    </Container>
  );
};

export default SystemControlView;
