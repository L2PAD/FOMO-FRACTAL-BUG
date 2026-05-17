import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  LineChart,
  Brain,
  Play,
  Wallet,
  Shield,
  Server,
  Bell,
  Power,
  Activity,
  TrendingUp
} from 'lucide-react';
import {
  CockpitContainer,
  TopBar,
  TopBarLeft,
  TopBarCenter,
  TopBarRight,
  Logo,
  ModeBadge,
  HealthIndicator,
  MetricPill,
  KillSwitch,
  AlertsBadge,
  MainContent,
  LeftNavigation,
  NavSection,
  NavItem,
  Workspace,
  RightRail,
  RightRailSection,
  AlertItem,
  PositionRow
} from './styles';
import CockpitAPI from '../services/api';

// Pages
import OverviewPage from '../pages/Overview';
import ChartLabPage from '../pages/ChartLab';
import HypothesesPage from '../pages/Hypotheses';
import ExecutionPage from '../pages/Execution';
import PortfolioPage from '../pages/Portfolio';
import RiskPage from '../pages/Risk';
import SystemPage from '../pages/System';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'chart', label: 'Chart Lab', icon: LineChart },
  { id: 'hypotheses', label: 'Hypotheses', icon: Brain },
  { id: 'execution', label: 'Execution', icon: Play },
  { id: 'portfolio', label: 'Portfolio', icon: Wallet },
  { id: 'risk', label: 'Risk & Safety', icon: Shield },
  { id: 'system', label: 'System', icon: Server }
];

const CockpitLayout = () => {
  const [activePage, setActivePage] = useState('overview');
  const [systemStatus, setSystemStatus] = useState({
    executionMode: 'PAPER',
    capitalMode: 'PILOT',
    systemHealth: 'HEALTHY',
    killSwitchState: false,
    circuitBreakerState: false,
    connectedExchanges: ['Binance', 'Coinbase'],
    totalEquity: 125430.50,
    dailyPnL: 2340.20,
    alertsCount: 3,
    latency: { avg: 45, p95: 120, p99: 250 }
  });
  
  const [alerts, setAlerts] = useState([
    { id: '1', type: 'RISK', severity: 'WARNING', message: 'Position size approaching limit for BTC', timestamp: '2 min ago' },
    { id: '2', type: 'MARKET', severity: 'INFO', message: 'Regime transition detected: TRENDING → VOLATILE', timestamp: '5 min ago' },
    { id: '3', type: 'EXECUTION', severity: 'INFO', message: 'Order filled: BTC LONG 0.5', timestamp: '12 min ago' }
  ]);
  
  const [positions, setPositions] = useState([
    { symbol: 'BTC', direction: 'LONG', size: 0.5, pnl: 1250.30 },
    { symbol: 'ETH', direction: 'SHORT', size: 5.2, pnl: -320.50 },
    { symbol: 'SOL', direction: 'LONG', size: 100, pnl: 890.00 }
  ]);

  const [pendingApprovals, setPendingApprovals] = useState([
    { id: '1', symbol: 'BTC', side: 'BUY', size: 0.25, confidence: 0.82 },
    { id: '2', symbol: 'ETH', side: 'SELL', size: 2.5, confidence: 0.75 }
  ]);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Try to fetch from backend, use mock data if fails
        const [registry, patterns] = await Promise.all([
          CockpitAPI.getTARegistry().catch(() => null),
          CockpitAPI.getTAPatterns().catch(() => null)
        ]);
        
        if (registry?.status === 'ok') {
          console.log('[Cockpit] TA Registry loaded:', registry.registry);
        }
        if (patterns?.status === 'ok') {
          console.log('[Cockpit] Patterns loaded:', patterns.patterns);
        }
      } catch (err) {
        console.log('[Cockpit] Using mock data');
      }
    };
    
    fetchData();
  }, []);

  const renderPage = () => {
    switch (activePage) {
      case 'overview':
        return <OverviewPage />;
      case 'chart':
        return <ChartLabPage />;
      case 'hypotheses':
        return <HypothesesPage />;
      case 'execution':
        return <ExecutionPage />;
      case 'portfolio':
        return <PortfolioPage />;
      case 'risk':
        return <RiskPage />;
      case 'system':
        return <SystemPage />;
      default:
        return <OverviewPage />;
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value);
  };

  return (
    <CockpitContainer data-testid="cockpit-container">
      {/* Top Bar */}
      <TopBar data-testid="cockpit-topbar">
        <TopBarLeft>
          <Logo>
            <TrendingUp size={22} />
            FOMO Cockpit
          </Logo>
          <ModeBadge $mode={systemStatus.executionMode} data-testid="execution-mode">
            {systemStatus.executionMode}
          </ModeBadge>
          <ModeBadge $mode={systemStatus.capitalMode === 'PILOT' ? 'PAPER' : 'APPROVAL'}>
            {systemStatus.capitalMode}
          </ModeBadge>
        </TopBarLeft>
        
        <TopBarCenter>
          <HealthIndicator $status={systemStatus.systemHealth} data-testid="system-health">
            <span className="dot" />
            {systemStatus.systemHealth}
          </HealthIndicator>
          <MetricPill>
            <span className="label">Latency</span>
            <span className="value" style={{ color: '#a0aec0' }}>{systemStatus.latency.avg}ms</span>
          </MetricPill>
          <MetricPill>
            <span className="label">Exchanges</span>
            <span className="value" style={{ color: '#05A584' }}>{systemStatus.connectedExchanges.length}</span>
          </MetricPill>
        </TopBarCenter>
        
        <TopBarRight>
          <MetricPill $positive={systemStatus.totalEquity > 0}>
            <span className="label">Equity</span>
            <span className="value" style={{ color: '#e2e8f0' }}>{formatCurrency(systemStatus.totalEquity)}</span>
          </MetricPill>
          <MetricPill $positive={systemStatus.dailyPnL >= 0}>
            <span className="label">Daily P&L</span>
            <span className="value">{systemStatus.dailyPnL >= 0 ? '+' : ''}{formatCurrency(systemStatus.dailyPnL)}</span>
          </MetricPill>
          <KillSwitch 
            $active={systemStatus.killSwitchState}
            onClick={() => setSystemStatus(s => ({ ...s, killSwitchState: !s.killSwitchState }))}
            data-testid="kill-switch"
          >
            <Power size={14} />
            Kill Switch
          </KillSwitch>
          <AlertsBadge data-testid="alerts-badge">
            <Bell size={18} />
            {systemStatus.alertsCount > 0 && <span className="count">{systemStatus.alertsCount}</span>}
          </AlertsBadge>
        </TopBarRight>
      </TopBar>
      
      {/* Main Content */}
      <MainContent>
        {/* Left Navigation */}
        <LeftNavigation data-testid="cockpit-nav">
          <NavSection>
            <div className="section-title">Trading</div>
            {NAV_ITEMS.slice(0, 4).map(item => (
              <NavItem
                key={item.id}
                $active={activePage === item.id}
                onClick={() => setActivePage(item.id)}
                data-testid={`nav-${item.id}`}
              >
                <item.icon size={18} />
                {item.label}
              </NavItem>
            ))}
          </NavSection>
          <NavSection>
            <div className="section-title">Management</div>
            {NAV_ITEMS.slice(4).map(item => (
              <NavItem
                key={item.id}
                $active={activePage === item.id}
                onClick={() => setActivePage(item.id)}
                data-testid={`nav-${item.id}`}
              >
                <item.icon size={18} />
                {item.label}
              </NavItem>
            ))}
          </NavSection>
        </LeftNavigation>
        
        {/* Main Workspace */}
        <Workspace data-testid="cockpit-workspace">
          {renderPage()}
        </Workspace>
        
        {/* Right Rail */}
        <RightRail data-testid="cockpit-right-rail">
          <RightRailSection>
            <div className="section-title">Alerts</div>
            {alerts.map(alert => (
              <AlertItem key={alert.id} $severity={alert.severity}>
                <Activity size={14} />
                <div className="content">
                  <div className="message">{alert.message}</div>
                  <div className="time">{alert.timestamp}</div>
                </div>
              </AlertItem>
            ))}
          </RightRailSection>
          
          <RightRailSection>
            <div className="section-title">Pending Approvals</div>
            {pendingApprovals.map(item => (
              <AlertItem key={item.id} $severity="INFO">
                <div className="content">
                  <div className="message">{item.symbol} {item.side} {item.size}</div>
                  <div className="time">Confidence: {(item.confidence * 100).toFixed(0)}%</div>
                </div>
              </AlertItem>
            ))}
          </RightRailSection>
          
          <RightRailSection>
            <div className="section-title">Active Positions</div>
            {positions.map(pos => (
              <PositionRow key={pos.symbol} $direction={pos.direction} $positive={pos.pnl >= 0}>
                <div>
                  <span className="symbol">{pos.symbol}</span>
                  <span className="direction" style={{ marginLeft: 8 }}>{pos.direction}</span>
                </div>
                <span className="pnl">{pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}</span>
              </PositionRow>
            ))}
          </RightRailSection>
        </RightRail>
      </MainContent>
    </CockpitContainer>
  );
};

export default CockpitLayout;
