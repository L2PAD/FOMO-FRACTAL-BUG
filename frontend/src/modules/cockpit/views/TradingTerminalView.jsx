import React, { useState } from 'react';
import styled from 'styled-components';
import { Check, X, Minus, Clock, Zap, Wallet, Shield, TrendingUp, TrendingDown } from 'lucide-react';

// ============================================
// STYLED COMPONENTS  
// ============================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 20px;
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
    font-size: 12px;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }
  
  .value {
    font-size: 22px;
    font-weight: 700;
    color: ${({ $color }) => $color || '#0f172a'};
  }
  
  .sub {
    font-size: 13px;
    color: #738094;
    margin-top: 4px;
  }
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  
  @media (max-width: 1200px) {
    grid-template-columns: 1fr;
  }
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

const PanelContent = styled.div`
  padding: 0;
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
    padding: 14px 16px;
    font-size: 14px;
    color: #0f172a;
    border-bottom: 1px solid #eef1f5;
  }
  
  tr:hover td {
    background: #f9fafb;
  }
`;

const Badge = styled.span`
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: ${({ $type }) => {
    switch ($type) {
      case 'BUY': case 'LONG': return '#e8f9f1';
      case 'SELL': case 'SHORT': return 'rgba(239, 68, 68, 0.1)';
      case 'LOW': return '#e8f9f1';
      case 'MEDIUM': return 'rgba(245, 158, 11, 0.1)';
      case 'HIGH': return 'rgba(239, 68, 68, 0.1)';
      default: return '#f5f7fa';
    }
  }};
  color: ${({ $type }) => {
    switch ($type) {
      case 'BUY': case 'LONG': case 'LOW': return '#05A584';
      case 'SELL': case 'SHORT': case 'HIGH': return '#ef4444';
      case 'MEDIUM': return '#f59e0b';
      default: return '#738094';
    }
  }};
`;

const ActionBtn = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  
  ${({ $type }) => {
    switch ($type) {
      case 'approve': return 'background: #e8f9f1; color: #05A584; &:hover { background: #d0f4e8; }';
      case 'reject': return 'background: rgba(239, 68, 68, 0.1); color: #ef4444; &:hover { background: rgba(239, 68, 68, 0.15); }';
      case 'reduce': return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b; &:hover { background: rgba(245, 158, 11, 0.15); }';
      default: return 'background: #f5f7fa; color: #738094;';
    }
  }}
`;

const ActionGroup = styled.div`
  display: flex;
  gap: 4px;
`;

const PositionRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #eef1f5;
  
  &:last-child {
    border-bottom: none;
  }
`;

const PositionInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  
  .symbol {
    font-weight: 600;
    color: #0f172a;
  }
`;

const PositionPnL = styled.span`
  font-weight: 600;
  color: ${({ $positive }) => $positive ? '#05A584' : '#ef4444'};
`;

const RiskItem = styled.div`
  padding: 16px;
  border-bottom: 1px solid #eef1f5;
  
  &:last-child {
    border-bottom: none;
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  
  .label {
    font-size: 13px;
    color: #738094;
  }
  
  .value {
    font-size: 14px;
    font-weight: 600;
    color: #0f172a;
  }
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

const pendingOrders = [
  { id: '1', symbol: 'BTC', side: 'BUY', size: 0.25, strategy: 'Momentum', confidence: 82, risk: 'MEDIUM' },
  { id: '2', symbol: 'ETH', side: 'SELL', size: 2.5, strategy: 'MeanRevert', confidence: 75, risk: 'LOW' },
  { id: '3', symbol: 'SOL', side: 'BUY', size: 50, strategy: 'Breakout', confidence: 68, risk: 'HIGH' }
];

const positions = [
  { symbol: 'BTC', direction: 'LONG', size: 0.5, pnl: 1250.30 },
  { symbol: 'ETH', direction: 'SHORT', size: 5.2, pnl: -320.50 },
  { symbol: 'SOL', direction: 'LONG', size: 100, pnl: 890.00 }
];

const riskBudget = [
  { strategy: 'Momentum', used: 35, allocated: 40 },
  { strategy: 'MeanRevert', used: 18, allocated: 25 },
  { strategy: 'Breakout', used: 15, allocated: 20 }
];

// ============================================
// COMPONENT
// ============================================

const TradingTerminalView = () => {
  const [orders, setOrders] = useState(pendingOrders);

  const handleApprove = (id) => setOrders(prev => prev.filter(o => o.id !== id));
  const handleReject = (id) => setOrders(prev => prev.filter(o => o.id !== id));

  const formatCurrency = (v) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);

  return (
    <Container data-testid="trading-terminal-view">
      {/* Portfolio Metrics */}
      <MetricsRow>
        <MetricCard>
          <div className="label">Total Equity</div>
          <div className="value">$125,430</div>
        </MetricCard>
        <MetricCard $color="#05A584">
          <div className="label">Daily P&L</div>
          <div className="value">+$2,340</div>
          <div className="sub">+1.87%</div>
        </MetricCard>
        <MetricCard>
          <div className="label">Net Exposure</div>
          <div className="value">$40,000</div>
          <div className="sub">Long biased</div>
        </MetricCard>
        <MetricCard $color="#f59e0b">
          <div className="label">VaR (95%)</div>
          <div className="value">$3,200</div>
        </MetricCard>
        <MetricCard>
          <div className="label">Pending</div>
          <div className="value">{orders.length}</div>
          <div className="sub">orders waiting</div>
        </MetricCard>
      </MetricsRow>
      
      <Grid>
        {/* Execution Queue */}
        <Panel>
          <PanelHeader>
            <span className="title">Execution Queue</span>
            <Clock size={16} style={{ color: '#f59e0b' }} />
          </PanelHeader>
          <PanelContent>
            <Table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Size</th>
                  <th>Strategy</th>
                  <th>Conf.</th>
                  <th>Risk</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(order => (
                  <tr key={order.id}>
                    <td style={{ fontWeight: 600 }}>{order.symbol}</td>
                    <td><Badge $type={order.side}>{order.side}</Badge></td>
                    <td>{order.size}</td>
                    <td>{order.strategy}</td>
                    <td style={{ color: '#05A584' }}>{order.confidence}%</td>
                    <td><Badge $type={order.risk}>{order.risk}</Badge></td>
                    <td>
                      <ActionGroup>
                        <ActionBtn $type="approve" onClick={() => handleApprove(order.id)}><Check size={14} /></ActionBtn>
                        <ActionBtn $type="reject" onClick={() => handleReject(order.id)}><X size={14} /></ActionBtn>
                        <ActionBtn $type="reduce"><Minus size={14} /></ActionBtn>
                      </ActionGroup>
                    </td>
                  </tr>
                ))}
                {orders.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9CA3AF', padding: 32 }}>No pending orders</td></tr>
                )}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>
        
        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Active Positions */}
          <Panel>
            <PanelHeader>
              <span className="title">Active Positions</span>
              <Wallet size={16} style={{ color: '#05A584' }} />
            </PanelHeader>
            <PanelContent>
              {positions.map(pos => (
                <PositionRow key={pos.symbol}>
                  <PositionInfo>
                    <span className="symbol">{pos.symbol}</span>
                    <Badge $type={pos.direction}>{pos.direction}</Badge>
                  </PositionInfo>
                  <PositionPnL $positive={pos.pnl >= 0}>
                    {pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}
                  </PositionPnL>
                </PositionRow>
              ))}
            </PanelContent>
          </Panel>
          
          {/* Risk Budget */}
          <Panel>
            <PanelHeader>
              <span className="title">Risk Budget</span>
              <Shield size={16} style={{ color: '#738094' }} />
            </PanelHeader>
            <PanelContent>
              {riskBudget.map(item => (
                <RiskItem key={item.strategy}>
                  <div className="header">
                    <span className="label">{item.strategy}</span>
                    <span className="value">{item.used}% / {item.allocated}%</span>
                  </div>
                  <ProgressBar 
                    $value={(item.used / item.allocated) * 100}
                    $color={item.used > item.allocated * 0.9 ? '#ef4444' : item.used > item.allocated * 0.7 ? '#f59e0b' : '#05A584'}
                  >
                    <div className="fill" />
                  </ProgressBar>
                </RiskItem>
              ))}
            </PanelContent>
          </Panel>
        </div>
      </Grid>
    </Container>
  );
};

export default TradingTerminalView;
