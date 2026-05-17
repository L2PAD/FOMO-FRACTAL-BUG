import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';
import {
  Grid,
  Panel,
  PanelHeader,
  PanelContent,
  MetricCard,
  StatusBadge,
  ProgressBar,
  Table,
  HypothesisCard
} from '../components/styles';
import CockpitAPI from '../services/api';

const OverviewPage = () => {
  const [dashboardData, setDashboardData] = useState({
    marketRegime: { regime: 'TRENDING_UP', confidence: 0.78, transitionProbability: 0.15 },
    capitalFlow: { flowBias: 'BULLISH', dominantRotation: 'Risk-On', flowStrength: 0.72 },
    topHypothesis: {
      type: 'BREAKOUT_CONTINUATION',
      direction: 'LONG',
      confidence: 0.82,
      alphaFamily: 'Momentum',
      explanation: 'Strong momentum continuation with volume confirmation above key resistance'
    },
    portfolio: {
      equity: 125430.50,
      dailyPnL: 2340.20,
      unrealizedPnL: 4520.80,
      longExposure: 65000,
      shortExposure: 25000
    },
    risk: {
      var95: 3200,
      drawdown: 2.5,
      riskBudgetUsed: 45
    },
    systemHealth: {
      validation: 98,
      latency: 45,
      uptime: 99.9
    }
  });

  const [pendingApprovals, setPendingApprovals] = useState([
    { id: '1', symbol: 'BTC', side: 'BUY', size: 0.25, strategy: 'Momentum', confidence: 82, riskLevel: 'MEDIUM' },
    { id: '2', symbol: 'ETH', side: 'SELL', size: 2.5, strategy: 'MeanRevert', confidence: 75, riskLevel: 'LOW' }
  ]);

  const [recentAlerts, setRecentAlerts] = useState([
    { id: '1', type: 'MARKET', message: 'Regime transition: TRENDING → VOLATILE', time: '2m ago', severity: 'WARNING' },
    { id: '2', type: 'RISK', message: 'Position limit 80% reached for BTC', time: '5m ago', severity: 'WARNING' },
    { id: '3', type: 'EXECUTION', message: 'Order filled: BTC LONG 0.5 @ 67,420', time: '12m ago', severity: 'INFO' }
  ]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [registry, patterns] = await Promise.all([
          CockpitAPI.getTARegistry().catch(() => null),
          CockpitAPI.getTAPatterns().catch(() => null)
        ]);
        
        if (registry?.status === 'ok') {
          setDashboardData(prev => ({
            ...prev,
            systemHealth: {
              ...prev.systemHealth,
              strategies: registry.registry?.strategies_count || 0,
              calibrationEnabled: registry.registry?.calibration_enabled || false
            }
          }));
        }
      } catch (err) {
        console.log('[Overview] Using mock data');
      }
    };
    
    fetchData();
  }, []);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  return (
    <div data-testid="overview-page">
      {/* Top Metrics Row */}
      <Grid $cols={4} style={{ marginBottom: 20 }}>
        <MetricCard $positive={dashboardData.portfolio.dailyPnL >= 0}>
          <div className="label">Daily P&L</div>
          <div className="value" style={{ color: dashboardData.portfolio.dailyPnL >= 0 ? '#05A584' : '#ef4444' }}>
            {dashboardData.portfolio.dailyPnL >= 0 ? '+' : ''}{formatCurrency(dashboardData.portfolio.dailyPnL)}
          </div>
          <div className="change">+2.1% today</div>
        </MetricCard>
        
        <MetricCard>
          <div className="label">Total Equity</div>
          <div className="value">{formatCurrency(dashboardData.portfolio.equity)}</div>
          <div className="change" style={{ color: '#05A584' }}>+18.5% MTD</div>
        </MetricCard>
        
        <MetricCard>
          <div className="label">Net Exposure</div>
          <div className="value">{formatCurrency(dashboardData.portfolio.longExposure - dashboardData.portfolio.shortExposure)}</div>
          <div className="change" style={{ color: '#a0aec0' }}>Long biased</div>
        </MetricCard>
        
        <MetricCard>
          <div className="label">VaR (95%)</div>
          <div className="value" style={{ color: '#f59e0b' }}>{formatCurrency(dashboardData.risk.var95)}</div>
          <div className="change">2.5% of equity</div>
        </MetricCard>
      </Grid>

      {/* Main Content */}
      <Grid $cols={3} $gap="20px">
        {/* Market State */}
        <Panel>
          <PanelHeader>
            <div>
              <div className="title">Market State</div>
              <div className="subtitle">Current regime & bias</div>
            </div>
            <StatusBadge $status={dashboardData.marketRegime.regime.includes('UP') ? 'BULLISH' : 'BEARISH'}>
              {dashboardData.marketRegime.regime.replace('_', ' ')}
            </StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: '#738094' }}>Regime Confidence</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{(dashboardData.marketRegime.confidence * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar $value={dashboardData.marketRegime.confidence * 100} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#738094' }}>Capital Flow</span>
                <StatusBadge $status={dashboardData.capitalFlow.flowBias}>{dashboardData.capitalFlow.flowBias}</StatusBadge>
              </div>
              <div style={{ fontSize: 12, color: '#a0aec0' }}>
                {dashboardData.capitalFlow.dominantRotation} • Strength: {(dashboardData.capitalFlow.flowStrength * 100).toFixed(0)}%
              </div>
            </div>
            
            <div style={{ padding: 12, background: 'rgba(245, 158, 11, 0.08)', borderRadius: 10, fontSize: 13, border: '1px solid rgba(245, 158, 11, 0.15)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f59e0b', marginBottom: 4 }}>
                <AlertTriangle size={14} />
                Transition Risk
              </div>
              <div style={{ color: '#738094' }}>
                {(dashboardData.marketRegime.transitionProbability * 100).toFixed(0)}% probability of regime change
              </div>
            </div>
          </PanelContent>
        </Panel>
        
        {/* Top Hypothesis */}
        <Panel>
          <PanelHeader>
            <div>
              <div className="title">Top Hypothesis</div>
              <div className="subtitle">Highest confidence signal</div>
            </div>
            <StatusBadge $status={dashboardData.topHypothesis.direction}>
              {dashboardData.topHypothesis.direction}
            </StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                {dashboardData.topHypothesis.type.replace(/_/g, ' ')}
              </div>
              <div style={{ fontSize: 12, color: '#738094' }}>
                Alpha Family: {dashboardData.topHypothesis.alphaFamily}
              </div>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', marginBottom: 4 }}>Confidence</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#05A584' }}>{(dashboardData.topHypothesis.confidence * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', marginBottom: 4 }}>Direction</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: dashboardData.topHypothesis.direction === 'LONG' ? '#05A584' : '#ef4444' }}>
                  {dashboardData.topHypothesis.direction === 'LONG' ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
                </div>
              </div>
            </div>
            
            <div style={{ fontSize: 13, color: '#738094', lineHeight: 1.6 }}>
              {dashboardData.topHypothesis.explanation}
            </div>
          </PanelContent>
        </Panel>
        
        {/* System Health */}
        <Panel>
          <PanelHeader>
            <div>
              <div className="title">System Health</div>
              <div className="subtitle">Performance metrics</div>
            </div>
            <StatusBadge $status="HEALTHY">
              <CheckCircle size={12} /> Healthy
            </StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#738094' }}>Validation Score</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#05A584' }}>{dashboardData.systemHealth.validation}%</span>
              </div>
              <ProgressBar $value={dashboardData.systemHealth.validation} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ padding: 14, background: '#f5f7fa', borderRadius: 10 }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Avg Latency</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: '#0f172a' }}>{dashboardData.systemHealth.latency}ms</div>
              </div>
              <div style={{ padding: 14, background: '#f5f7fa', borderRadius: 10 }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>Uptime</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: '#05A584' }}>{dashboardData.systemHealth.uptime}%</div>
              </div>
            </div>
          </PanelContent>
        </Panel>
      </Grid>

      {/* Bottom Section */}
      <Grid $cols={2} $gap="20px" style={{ marginTop: 20 }}>
        {/* Pending Approvals */}
        <Panel>
          <PanelHeader>
            <div>
              <div className="title">Pending Approvals</div>
              <div className="subtitle">{pendingApprovals.length} orders waiting</div>
            </div>
            <Clock size={18} style={{ color: '#f59e0b' }} />
          </PanelHeader>
          <PanelContent style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Size</th>
                  <th>Strategy</th>
                  <th>Confidence</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {pendingApprovals.map(item => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{item.symbol}</td>
                    <td>
                      <StatusBadge $status={item.side}>{item.side}</StatusBadge>
                    </td>
                    <td>{item.size}</td>
                    <td>{item.strategy}</td>
                    <td style={{ color: '#05A584' }}>{item.confidence}%</td>
                    <td>
                      <StatusBadge $status={item.riskLevel === 'HIGH' ? 'CRITICAL' : item.riskLevel === 'MEDIUM' ? 'NEUTRAL' : 'HEALTHY'}>
                        {item.riskLevel}
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>
        
        {/* Recent Alerts */}
        <Panel>
          <PanelHeader>
            <div>
              <div className="title">Recent Alerts</div>
              <div className="subtitle">Last 24 hours</div>
            </div>
            <Zap size={18} style={{ color: '#f59e0b' }} />
          </PanelHeader>
          <PanelContent>
            {recentAlerts.map(alert => (
              <div 
                key={alert.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: 14,
                  background: alert.severity === 'WARNING' ? 'rgba(245, 158, 11, 0.08)' : '#f9fafb',
                  borderRadius: 10,
                  marginBottom: 10,
                  borderLeft: `3px solid ${alert.severity === 'WARNING' ? '#f59e0b' : alert.severity === 'CRITICAL' ? '#ef4444' : '#05A584'}`
                }}
              >
                <Activity size={16} style={{ color: alert.severity === 'WARNING' ? '#f59e0b' : alert.severity === 'CRITICAL' ? '#ef4444' : '#05A584', marginTop: 2 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: '#0f172a', marginBottom: 4 }}>{alert.message}</div>
                  <div style={{ fontSize: 12, color: '#9CA3AF' }}>{alert.type} • {alert.time}</div>
                </div>
              </div>
            ))}
          </PanelContent>
        </Panel>
      </Grid>
    </div>
  );
};

export default OverviewPage;
