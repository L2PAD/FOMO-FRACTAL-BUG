import React, { useState } from 'react';
import { TrendingUp, TrendingDown, Wallet, PieChart, BarChart3 } from 'lucide-react';
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

const PortfolioPage = () => {
  const [portfolioState, setPortfolioState] = useState({
    equity: 125430.50,
    realizedPnL: 8520.30,
    unrealizedPnL: 4520.80,
    dailyPnL: 2340.20,
    weeklyPnL: 12450.60,
    longExposure: 65000,
    shortExposure: 25000,
    netExposure: 40000
  });

  const [positions, setPositions] = useState([
    { symbol: 'BTC', direction: 'LONG', size: 0.5, entry: 66500, currentPrice: 67420, pnl: 460, riskContribution: 35, targetWeight: 40, currentWeight: 38 },
    { symbol: 'ETH', direction: 'LONG', size: 5.2, entry: 3180, currentPrice: 3245, pnl: 338, riskContribution: 25, targetWeight: 25, currentWeight: 22 },
    { symbol: 'SOL', direction: 'LONG', size: 100, entry: 138, currentPrice: 142.5, pnl: 450, riskContribution: 20, targetWeight: 20, currentWeight: 18 },
    { symbol: 'BNB', direction: 'SHORT', size: 10, entry: 595, currentPrice: 598, pnl: -30, riskContribution: 10, targetWeight: 10, currentWeight: 12 },
    { symbol: 'AVAX', direction: 'LONG', size: 50, entry: 35.2, currentPrice: 36.8, pnl: 80, riskContribution: 10, targetWeight: 5, currentWeight: 10 }
  ]);

  const [riskBudget, setRiskBudget] = useState({
    momentum: { allocated: 40, used: 35, remaining: 5 },
    meanRevert: { allocated: 25, used: 18, remaining: 7 },
    breakout: { allocated: 20, used: 15, remaining: 5 },
    trend: { allocated: 15, used: 12, remaining: 3 }
  });

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  return (
    <div data-testid="portfolio-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Portfolio</h2>
        <p style={{ fontSize: 13, color: '#738094' }}>Positions, exposure, and risk allocation</p>
      </div>

      {/* Summary Cards */}
      <Grid $cols={5} style={{ marginBottom: 20 }}>
        <MetricCard $positive={portfolioState.equity > 0}>
          <div className="label">Total Equity</div>
          <div className="value">{formatCurrency(portfolioState.equity)}</div>
        </MetricCard>
        <MetricCard $positive={portfolioState.dailyPnL >= 0}>
          <div className="label">Daily P&L</div>
          <div className="value" style={{ color: portfolioState.dailyPnL >= 0 ? '#05A584' : '#ef4444' }}>
            {portfolioState.dailyPnL >= 0 ? '+' : ''}{formatCurrency(portfolioState.dailyPnL)}
          </div>
          <div className="change">{((portfolioState.dailyPnL / portfolioState.equity) * 100).toFixed(2)}%</div>
        </MetricCard>
        <MetricCard $positive={portfolioState.unrealizedPnL >= 0}>
          <div className="label">Unrealized P&L</div>
          <div className="value" style={{ color: portfolioState.unrealizedPnL >= 0 ? '#05A584' : '#ef4444' }}>
            {portfolioState.unrealizedPnL >= 0 ? '+' : ''}{formatCurrency(portfolioState.unrealizedPnL)}
          </div>
        </MetricCard>
        <MetricCard>
          <div className="label">Long Exposure</div>
          <div className="value" style={{ color: '#05A584' }}>{formatCurrency(portfolioState.longExposure)}</div>
        </MetricCard>
        <MetricCard>
          <div className="label">Short Exposure</div>
          <div className="value" style={{ color: '#ef4444' }}>{formatCurrency(portfolioState.shortExposure)}</div>
        </MetricCard>
      </Grid>

      <Grid $cols={3} $gap="20px">
        {/* Positions Table */}
        <div style={{ gridColumn: 'span 2' }}>
          <Panel>
            <PanelHeader>
              <div className="title">Active Positions</div>
              <Wallet size={16} style={{ color: '#05A584' }} />
            </PanelHeader>
            <PanelContent style={{ padding: 0 }}>
              <Table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Size</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>P&L</th>
                    <th>Risk %</th>
                    <th>Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map(pos => (
                    <tr key={pos.symbol}>
                      <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{pos.symbol}</td>
                      <td>
                        <StatusBadge $status={pos.direction}>{pos.direction}</StatusBadge>
                      </td>
                      <td>{pos.size}</td>
                      <td>${pos.entry.toLocaleString()}</td>
                      <td>${pos.currentPrice.toLocaleString()}</td>
                      <td style={{ 
                        fontWeight: 600,
                        color: pos.pnl >= 0 ? '#05A584' : '#ef4444' 
                      }}>
                        {pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}
                      </td>
                      <td>{pos.riskContribution}%</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ color: pos.currentWeight > pos.targetWeight ? '#f59e0b' : '#a0aec0' }}>
                            {pos.currentWeight}%
                          </span>
                          <span style={{ color: '#4a5568', fontSize: 11 }}>/ {pos.targetWeight}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </PanelContent>
          </Panel>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Exposure */}
          <Panel>
            <PanelHeader>
              <div className="title">Exposure</div>
              <PieChart size={16} style={{ color: '#738094' }} />
            </PanelHeader>
            <PanelContent>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: '#738094' }}>Net Exposure</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#05A584' }}>
                    {formatCurrency(portfolioState.netExposure)}
                  </span>
                </div>
                <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${(portfolioState.longExposure / (portfolioState.longExposure + portfolioState.shortExposure)) * 100}%`,
                    background: '#05A584'
                  }} />
                  <div style={{ 
                    flex: 1,
                    background: '#ef4444'
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: '#738094' }}>
                  <span>Long {((portfolioState.longExposure / (portfolioState.longExposure + portfolioState.shortExposure)) * 100).toFixed(0)}%</span>
                  <span>Short {((portfolioState.shortExposure / (portfolioState.longExposure + portfolioState.shortExposure)) * 100).toFixed(0)}%</span>
                </div>
              </div>
              
              <div style={{ 
                padding: 12, 
                background: 'rgba(5, 165, 132, 0.1)', 
                borderRadius: 8,
                fontSize: 12,
                color: '#05A584'
              }}>
                <strong>Long biased</strong> - Net exposure at {((portfolioState.netExposure / portfolioState.equity) * 100).toFixed(0)}% of equity
              </div>
            </PanelContent>
          </Panel>

          {/* Risk Budget */}
          <Panel>
            <PanelHeader>
              <div className="title">Risk Budget</div>
              <BarChart3 size={16} style={{ color: '#738094' }} />
            </PanelHeader>
            <PanelContent>
              {Object.entries(riskBudget).map(([strategy, budget]) => (
                <div key={strategy} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: '#e2e8f0', textTransform: 'capitalize' }}>{strategy}</span>
                    <span style={{ fontSize: 12, color: '#738094' }}>
                      {budget.used}% / {budget.allocated}%
                    </span>
                  </div>
                  <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: 'rgba(255, 255, 255, 0.1)' }}>
                    <div style={{ 
                      width: `${(budget.used / budget.allocated) * 100}%`,
                      background: budget.used > budget.allocated * 0.9 ? '#ef4444' : budget.used > budget.allocated * 0.7 ? '#f59e0b' : '#05A584'
                    }} />
                  </div>
                </div>
              ))}
            </PanelContent>
          </Panel>
        </div>
      </Grid>
    </div>
  );
};

export default PortfolioPage;
