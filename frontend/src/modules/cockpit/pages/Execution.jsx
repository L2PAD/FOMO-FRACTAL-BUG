import React, { useState } from 'react';
import { Check, X, Minus, AlertTriangle, Clock, Zap, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import {
  Grid,
  Panel,
  PanelHeader,
  PanelContent,
  StatusBadge,
  Table,
  Button,
  TabsContainer,
  TabButton
} from '../components/styles';

const ExecutionPage = () => {
  const [activeTab, setActiveTab] = useState('pending');
  const [selectedOrder, setSelectedOrder] = useState(null);
  
  const [pendingOrders, setPendingOrders] = useState([
    { id: '1', symbol: 'BTC', side: 'BUY', size: 0.25, strategy: 'Momentum', confidence: 82, riskLevel: 'MEDIUM', impactState: 'LOW', exchange: 'Binance', createdAt: '2 min ago' },
    { id: '2', symbol: 'ETH', side: 'SELL', size: 2.5, strategy: 'MeanRevert', confidence: 75, riskLevel: 'LOW', impactState: 'LOW', exchange: 'Coinbase', createdAt: '5 min ago' },
    { id: '3', symbol: 'SOL', side: 'BUY', size: 50, strategy: 'Breakout', confidence: 68, riskLevel: 'HIGH', impactState: 'MEDIUM', exchange: 'Binance', createdAt: '8 min ago' }
  ]);

  const [activeOrders, setActiveOrders] = useState([
    { id: '4', symbol: 'BTC', side: 'BUY', size: 0.15, filled: 0.1, avgPrice: 67420, status: 'PARTIAL', exchange: 'Binance' },
    { id: '5', symbol: 'ETH', side: 'SELL', size: 1.5, filled: 1.5, avgPrice: 3245, status: 'FILLED', exchange: 'Coinbase' }
  ]);

  const [recentFills, setRecentFills] = useState([
    { id: '6', symbol: 'BTC', side: 'BUY', size: 0.5, price: 67380, slippage: 0.02, latency: 45, time: '12 min ago' },
    { id: '7', symbol: 'ETH', side: 'SELL', size: 3.0, price: 3248, slippage: -0.01, latency: 38, time: '25 min ago' },
    { id: '8', symbol: 'SOL', side: 'BUY', size: 100, price: 142.5, slippage: 0.05, latency: 52, time: '1 hour ago' }
  ]);

  const handleApprove = (orderId) => {
    setPendingOrders(prev => prev.filter(o => o.id !== orderId));
    console.log('[Execution] Approved:', orderId);
  };

  const handleReject = (orderId) => {
    setPendingOrders(prev => prev.filter(o => o.id !== orderId));
    console.log('[Execution] Rejected:', orderId);
  };

  const handleReduce = (orderId) => {
    setPendingOrders(prev => prev.map(o => 
      o.id === orderId ? { ...o, size: o.size * 0.5 } : o
    ));
    console.log('[Execution] Reduced:', orderId);
  };

  return (
    <div data-testid="execution-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Execution Control</h2>
        <p style={{ fontSize: 13, color: '#738094' }}>Manage pending approvals, active orders, and fills</p>
      </div>

      <TabsContainer>
        <TabButton $active={activeTab === 'pending'} onClick={() => setActiveTab('pending')}>
          Pending Approvals ({pendingOrders.length})
        </TabButton>
        <TabButton $active={activeTab === 'active'} onClick={() => setActiveTab('active')}>
          Active Orders ({activeOrders.length})
        </TabButton>
        <TabButton $active={activeTab === 'fills'} onClick={() => setActiveTab('fills')}>
          Recent Fills
        </TabButton>
      </TabsContainer>

      {activeTab === 'pending' && (
        <Grid $cols={selectedOrder ? 2 : 1} $gap="20px">
          {/* Approval Queue */}
          <Panel>
            <PanelHeader>
              <div className="title">Approval Queue</div>
              <Clock size={16} style={{ color: '#f59e0b' }} />
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
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingOrders.map(order => (
                    <tr 
                      key={order.id} 
                      onClick={() => setSelectedOrder(order)}
                      style={{ cursor: 'pointer', background: selectedOrder?.id === order.id ? 'rgba(5, 165, 132, 0.1)' : 'transparent' }}
                    >
                      <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{order.symbol}</td>
                      <td>
                        <StatusBadge $status={order.side}>{order.side}</StatusBadge>
                      </td>
                      <td>{order.size}</td>
                      <td>{order.strategy}</td>
                      <td style={{ color: '#05A584' }}>{order.confidence}%</td>
                      <td>
                        <StatusBadge $status={order.riskLevel === 'HIGH' ? 'CRITICAL' : order.riskLevel === 'MEDIUM' ? 'NEUTRAL' : 'HEALTHY'}>
                          {order.riskLevel}
                        </StatusBadge>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                          <Button $variant="primary" style={{ padding: '4px 8px' }} onClick={() => handleApprove(order.id)}>
                            <Check size={14} />
                          </Button>
                          <Button $variant="danger" style={{ padding: '4px 8px' }} onClick={() => handleReject(order.id)}>
                            <X size={14} />
                          </Button>
                          <Button $variant="warning" style={{ padding: '4px 8px' }} onClick={() => handleReduce(order.id)}>
                            <Minus size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              {pendingOrders.length === 0 && (
                <div style={{ padding: 40, textAlign: 'center', color: '#4a5568' }}>
                  No pending approvals
                </div>
              )}
            </PanelContent>
          </Panel>
          
          {/* Order Detail */}
          {selectedOrder && (
            <Panel>
              <PanelHeader>
                <div className="title">Order Detail</div>
                <StatusBadge $status={selectedOrder.side}>{selectedOrder.side}</StatusBadge>
              </PanelHeader>
              <PanelContent>
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>
                    {selectedOrder.symbol}
                  </div>
                  <div style={{ fontSize: 13, color: '#738094' }}>
                    {selectedOrder.exchange} • {selectedOrder.createdAt}
                  </div>
                </div>
                
                <Grid $cols={2} $gap="16px" style={{ marginBottom: 20 }}>
                  <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>Size</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#e2e8f0' }}>{selectedOrder.size}</div>
                  </div>
                  <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>Strategy</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#e2e8f0' }}>{selectedOrder.strategy}</div>
                  </div>
                  <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>Confidence</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#05A584' }}>{selectedOrder.confidence}%</div>
                  </div>
                  <div style={{ padding: 12, background: 'rgba(255, 255, 255, 0.02)', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#4a5568', marginBottom: 4 }}>Impact</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#e2e8f0' }}>{selectedOrder.impactState}</div>
                  </div>
                </Grid>
                
                <div style={{ display: 'flex', gap: 12 }}>
                  <Button $variant="primary" style={{ flex: 1 }} onClick={() => handleApprove(selectedOrder.id)}>
                    <Check size={16} /> Approve
                  </Button>
                  <Button $variant="danger" style={{ flex: 1 }} onClick={() => handleReject(selectedOrder.id)}>
                    <X size={16} /> Reject
                  </Button>
                </div>
              </PanelContent>
            </Panel>
          )}
        </Grid>
      )}

      {activeTab === 'active' && (
        <Panel>
          <PanelHeader>
            <div className="title">Active Orders</div>
            <Zap size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <PanelContent style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Size</th>
                  <th>Filled</th>
                  <th>Avg Price</th>
                  <th>Status</th>
                  <th>Exchange</th>
                </tr>
              </thead>
              <tbody>
                {activeOrders.map(order => (
                  <tr key={order.id}>
                    <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{order.symbol}</td>
                    <td>
                      <StatusBadge $status={order.side}>{order.side}</StatusBadge>
                    </td>
                    <td>{order.size}</td>
                    <td style={{ color: order.filled === order.size ? '#05A584' : '#f59e0b' }}>
                      {order.filled} / {order.size}
                    </td>
                    <td>${order.avgPrice.toLocaleString()}</td>
                    <td>
                      <StatusBadge $status={order.status === 'FILLED' ? 'HEALTHY' : 'NEUTRAL'}>
                        {order.status}
                      </StatusBadge>
                    </td>
                    <td>{order.exchange}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>
      )}

      {activeTab === 'fills' && (
        <Panel>
          <PanelHeader>
            <div className="title">Recent Fills</div>
          </PanelHeader>
          <PanelContent style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Size</th>
                  <th>Price</th>
                  <th>Slippage</th>
                  <th>Latency</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentFills.map(fill => (
                  <tr key={fill.id}>
                    <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{fill.symbol}</td>
                    <td>
                      <StatusBadge $status={fill.side}>{fill.side}</StatusBadge>
                    </td>
                    <td>{fill.size}</td>
                    <td>${fill.price.toLocaleString()}</td>
                    <td style={{ color: fill.slippage > 0 ? '#ef4444' : '#05A584' }}>
                      {fill.slippage > 0 ? '+' : ''}{(fill.slippage * 100).toFixed(2)}%
                    </td>
                    <td>{fill.latency}ms</td>
                    <td style={{ color: '#738094' }}>{fill.time}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </PanelContent>
        </Panel>
      )}
    </div>
  );
};

export default ExecutionPage;
