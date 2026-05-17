import React, { useState, useEffect } from 'react';
import { Server, Activity, CheckCircle, AlertTriangle, Wifi, Database, Clock, Zap } from 'lucide-react';
import {
  Grid,
  Panel,
  PanelHeader,
  PanelContent,
  MetricCard,
  StatusBadge,
  ProgressBar,
  Table
} from '../components/styles';
import CockpitAPI from '../services/api';

const SystemPage = () => {
  const [systemStatus, setSystemStatus] = useState({
    validationScore: 98,
    coefficientAudit: 'PASSED',
    integrationAudit: 'PASSED',
    stressStatus: 'IDLE',
    chaosStatus: 'IDLE'
  });

  const [latencyMetrics, setLatencyMetrics] = useState({
    avg: 45,
    p95: 120,
    p99: 250,
    throughput: 1250,
    errorRate: 0.02
  });

  const [exchanges, setExchanges] = useState([
    { name: 'Binance', status: 'CONNECTED', latency: 42, lastSync: '2s ago', wsStatus: 'OPEN' },
    { name: 'Coinbase', status: 'CONNECTED', latency: 58, lastSync: '3s ago', wsStatus: 'OPEN' },
    { name: 'Kraken', status: 'DEGRADED', latency: 180, lastSync: '15s ago', wsStatus: 'RECONNECTING' }
  ]);

  const [healthChecks, setHealthChecks] = useState([
    { service: 'API Gateway', status: 'HEALTHY', uptime: 99.99, lastCheck: '5s ago' },
    { service: 'TA Engine', status: 'HEALTHY', uptime: 99.95, lastCheck: '5s ago' },
    { service: 'Data Pipeline', status: 'HEALTHY', uptime: 99.90, lastCheck: '5s ago' },
    { service: 'Execution Engine', status: 'HEALTHY', uptime: 99.98, lastCheck: '5s ago' },
    { service: 'Risk Engine', status: 'HEALTHY', uptime: 99.99, lastCheck: '5s ago' },
    { service: 'MongoDB', status: 'HEALTHY', uptime: 99.99, lastCheck: '5s ago' }
  ]);

  useEffect(() => {
    const fetchSystemData = async () => {
      try {
        const [registry, dbHealth] = await Promise.all([
          CockpitAPI.getTARegistry().catch(() => null),
          fetch(`${process.env.REACT_APP_BACKEND_URL || ''}/api/system/db-health`).then(r => r.json()).catch(() => null)
        ]);
        
        if (dbHealth?.status === 'healthy') {
          setHealthChecks(prev => prev.map(check => 
            check.service === 'MongoDB' ? { ...check, status: 'HEALTHY' } : check
          ));
        }
        
        if (registry?.status === 'ok') {
          console.log('[System] TA Registry:', registry.registry);
        }
      } catch (err) {
        console.log('[System] Using mock data');
      }
    };
    
    fetchSystemData();
    const interval = setInterval(fetchSystemData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div data-testid="system-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>System Status</h2>
        <p style={{ fontSize: 13, color: '#738094' }}>Infrastructure health, validation, and performance metrics</p>
      </div>

      {/* Top Metrics */}
      <Grid $cols={5} style={{ marginBottom: 20 }}>
        <MetricCard>
          <div className="label">Validation Score</div>
          <div className="value" style={{ color: systemStatus.validationScore >= 95 ? '#05A584' : '#f59e0b' }}>
            {systemStatus.validationScore}%
          </div>
        </MetricCard>
        <MetricCard>
          <div className="label">Avg Latency</div>
          <div className="value">{latencyMetrics.avg}ms</div>
        </MetricCard>
        <MetricCard>
          <div className="label">P95 Latency</div>
          <div className="value" style={{ color: latencyMetrics.p95 > 100 ? '#f59e0b' : '#05A584' }}>
            {latencyMetrics.p95}ms
          </div>
        </MetricCard>
        <MetricCard>
          <div className="label">Throughput</div>
          <div className="value">{latencyMetrics.throughput}/s</div>
        </MetricCard>
        <MetricCard>
          <div className="label">Error Rate</div>
          <div className="value" style={{ color: latencyMetrics.errorRate > 0.01 ? '#ef4444' : '#05A584' }}>
            {(latencyMetrics.errorRate * 100).toFixed(2)}%
          </div>
        </MetricCard>
      </Grid>

      <Grid $cols={2} $gap="20px">
        {/* Service Health */}
        <Panel>
          <PanelHeader>
            <div className="title">Service Health</div>
            <CheckCircle size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <PanelContent style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Status</th>
                  <th>Uptime</th>
                  <th>Last Check</th>
                </tr>
              </thead>
              <tbody>
                {healthChecks.map(check => (
                  <tr key={check.service}>
                    <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{check.service}</td>
                    <td>
                      <StatusBadge $status={check.status}>{check.status}</StatusBadge>
                    </td>
                    <td style={{ color: check.uptime >= 99.9 ? '#05A584' : '#f59e0b' }}>
                      {check.uptime}%
                    </td>
                    <td style={{ color: '#738094' }}>{check.lastCheck}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>

        {/* Exchange Connectivity */}
        <Panel>
          <PanelHeader>
            <div className="title">Exchange Connectivity</div>
            <Wifi size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <PanelContent style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr>
                  <th>Exchange</th>
                  <th>Status</th>
                  <th>Latency</th>
                  <th>WebSocket</th>
                  <th>Last Sync</th>
                </tr>
              </thead>
              <tbody>
                {exchanges.map(exchange => (
                  <tr key={exchange.name}>
                    <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{exchange.name}</td>
                    <td>
                      <StatusBadge $status={exchange.status === 'CONNECTED' ? 'HEALTHY' : 'DEGRADED'}>
                        {exchange.status}
                      </StatusBadge>
                    </td>
                    <td style={{ color: exchange.latency > 100 ? '#f59e0b' : '#05A584' }}>
                      {exchange.latency}ms
                    </td>
                    <td>
                      <StatusBadge $status={exchange.wsStatus === 'OPEN' ? 'HEALTHY' : 'NEUTRAL'}>
                        {exchange.wsStatus}
                      </StatusBadge>
                    </td>
                    <td style={{ color: '#738094' }}>{exchange.lastSync}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>
      </Grid>

      {/* Validation & Testing */}
      <Grid $cols={3} $gap="20px" style={{ marginTop: 20 }}>
        <Panel>
          <PanelHeader>
            <div className="title">Validation Status</div>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#738094' }}>Overall Score</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#05A584' }}>{systemStatus.validationScore}%</span>
              </div>
              <ProgressBar $value={systemStatus.validationScore} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#a0aec0' }}>Coefficient Audit</span>
                <StatusBadge $status="HEALTHY">{systemStatus.coefficientAudit}</StatusBadge>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#a0aec0' }}>Integration Audit</span>
                <StatusBadge $status="HEALTHY">{systemStatus.integrationAudit}</StatusBadge>
              </div>
            </div>
          </PanelContent>
        </Panel>

        <Panel>
          <PanelHeader>
            <div className="title">Stress Testing</div>
          </PanelHeader>
          <PanelContent>
            <div style={{ 
              padding: 20, 
              background: 'rgba(255, 255, 255, 0.02)', 
              borderRadius: 8,
              textAlign: 'center',
              marginBottom: 16
            }}>
              <Server size={32} style={{ color: '#4a5568', marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                {systemStatus.stressStatus}
              </div>
              <div style={{ fontSize: 12, color: '#738094' }}>
                Last run: 2 hours ago
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <StatusBadge $status="HEALTHY" style={{ flex: 1, justifyContent: 'center' }}>
                Load: PASSED
              </StatusBadge>
              <StatusBadge $status="HEALTHY" style={{ flex: 1, justifyContent: 'center' }}>
                Peak: PASSED
              </StatusBadge>
            </div>
          </PanelContent>
        </Panel>

        <Panel>
          <PanelHeader>
            <div className="title">Chaos Testing</div>
          </PanelHeader>
          <PanelContent>
            <div style={{ 
              padding: 20, 
              background: 'rgba(255, 255, 255, 0.02)', 
              borderRadius: 8,
              textAlign: 'center',
              marginBottom: 16
            }}>
              <Zap size={32} style={{ color: '#4a5568', marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                {systemStatus.chaosStatus}
              </div>
              <div style={{ fontSize: 12, color: '#738094' }}>
                Last run: 6 hours ago
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <StatusBadge $status="HEALTHY" style={{ flex: 1, justifyContent: 'center' }}>
                Failover: OK
              </StatusBadge>
              <StatusBadge $status="HEALTHY" style={{ flex: 1, justifyContent: 'center' }}>
                Recovery: OK
              </StatusBadge>
            </div>
          </PanelContent>
        </Panel>
      </Grid>
    </div>
  );
};

export default SystemPage;
