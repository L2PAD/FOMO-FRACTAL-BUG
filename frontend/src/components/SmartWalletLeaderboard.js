import React, { useState, useEffect, useCallback } from 'react';
import { Trophy, Users, Route, ChevronDown, ChevronUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const TAB_CONFIG = [
  { id: 'wallets', label: 'Smart Wallets', icon: Trophy },
  { id: 'clusters', label: 'Clusters', icon: Users },
  { id: 'routes', label: 'Capital Routes', icon: Route },
];

const ScoreBar = ({ value, color = '#10b981', max = 1 }) => (
  <div style={{ width: '100%', height: '4px', backgroundColor: 'rgba(148,163,184,0.15)', borderRadius: '2px' }}>
    <div style={{
      width: `${Math.min((value / max) * 100, 100)}%`,
      height: '100%', backgroundColor: color, borderRadius: '2px',
      transition: 'width 0.3s ease',
    }} />
  </div>
);

const formatUsd = (v) => {
  if (!v) return '$0';
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
};

const truncAddr = (a) => {
  if (!a) return '';
  if (a.length <= 14) return a;
  return `${a.slice(0, 6)}...${a.slice(-4)}`;
};

export default function SmartWalletLeaderboard({ onNavigate }) {
  const [activeTab, setActiveTab] = useState('wallets');
  const [wallets, setWallets] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedRow, setExpandedRow] = useState(null);

  const loadData = useCallback(async (tab) => {
    setLoading(true);
    try {
      const endpoints = {
        wallets: '/api/graph-core/smart-wallets?limit=30',
        clusters: '/api/graph-core/top-clusters?limit=20',
        routes: '/api/graph-core/top-routes?limit=20',
      };
      const res = await fetch(`${API_URL}${endpoints[tab]}`);
      const data = res.ok ? await res.json() : {};
      if (tab === 'wallets') setWallets(data.wallets || []);
      if (tab === 'clusters') setClusters(data.clusters || []);
      if (tab === 'routes') setRoutes(data.routes || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(activeTab); }, [activeTab, loadData]);

  const renderWallets = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      {wallets.map((w, i) => (
        <div
          key={w.wallet}
          data-testid={`smart-wallet-row-${i}`}
          style={{
            display: 'grid', gridTemplateColumns: '28px 1fr 70px 60px',
            alignItems: 'center', gap: '8px', padding: '6px 8px',
            borderRadius: '6px', cursor: 'pointer',
            backgroundColor: expandedRow === i ? 'rgba(30,41,59,0.5)' : 'transparent',
            transition: 'background-color 0.15s',
          }}
          onClick={() => setExpandedRow(expandedRow === i ? null : i)}
        >
          <span style={{
            fontSize: '10px', fontWeight: 700,
            color: i < 3 ? '#f59e0b' : '#64748b',
            textAlign: 'center',
          }}>#{i + 1}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {w.label || truncAddr(w.wallet)}
            </div>
            {w.cluster_id && (
              <div style={{ fontSize: '9px', color: '#64748b' }}>{w.cluster_id}</div>
            )}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#10b981' }}>
              {(w.smart_wallet_score * 100).toFixed(1)}
            </div>
            <ScoreBar value={w.smart_wallet_score} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            {expandedRow === i ? <ChevronUp size={12} color="#64748b" /> : <ChevronDown size={12} color="#64748b" />}
          </div>
          {expandedRow === i && (
            <div style={{
              gridColumn: '1 / -1', padding: '6px 0',
              display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px',
            }}>
              <MetricCell label="Profitability" value={`${(w.profitability * 100).toFixed(0)}%`} color="#10b981" />
              <MetricCell label="Early Entry" value={`${(w.early_entry_score * 100).toFixed(0)}%`} color="#3b82f6" />
              <MetricCell label="Alpha" value={`${(w.alpha_score * 100).toFixed(0)}%`} color="#f59e0b" />
              <MetricCell label="Capital" value={`${(w.capital_size * 100).toFixed(0)}%`} color="#8b5cf6" />
              <MetricCell label="Influence" value={`${(w.capital_influence_score * 100).toFixed(0)}%`} color="#ec4899" />
              <MetricCell label="Connections" value={w.degree || 0} color="#64748b" />
            </div>
          )}
        </div>
      ))}
      {wallets.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '20px', color: '#475569', fontSize: '12px' }}>
          No smart wallets found. Run Context Build first.
        </div>
      )}
    </div>
  );

  const renderClusters = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      {clusters.map((c, i) => (
        <div
          key={c.cluster_id}
          data-testid={`cluster-row-${i}`}
          style={{
            display: 'grid', gridTemplateColumns: '28px 1fr 60px 60px',
            alignItems: 'center', gap: '8px', padding: '6px 8px',
            borderRadius: '6px',
          }}
        >
          <span style={{ fontSize: '10px', fontWeight: 700, color: i < 3 ? '#3b82f6' : '#64748b', textAlign: 'center' }}>#{i + 1}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.label || c.cluster_id}
            </div>
            <div style={{ fontSize: '9px', color: '#64748b' }}>
              {c.wallet_count} wallets | {c.total_value_eth?.toFixed(1)} ETH
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, color: '#3b82f6' }}>
            {(c.cluster_score * 100).toFixed(0)}
          </div>
          <div style={{ textAlign: 'right', fontSize: '10px', color: '#64748b' }}>
            {c.total_tx_count} tx
          </div>
        </div>
      ))}
    </div>
  );

  const renderRoutes = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {routes.map((r, i) => (
        <div
          key={r.route_id || i}
          data-testid={`route-row-${i}`}
          style={{
            padding: '6px 8px', borderRadius: '6px',
            backgroundColor: 'rgba(30,41,59,0.3)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
            <span style={{ fontSize: '10px', fontWeight: 700, color: i < 3 ? '#f59e0b' : '#64748b' }}>#{i + 1}</span>
            <span style={{ fontSize: '10px', color: '#8b5cf6', fontWeight: 600 }}>
              {(r.importance * 100).toFixed(0)}% importance
            </span>
          </div>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', alignItems: 'center' }}>
            {(r.path || []).map((node, j) => (
              <React.Fragment key={j}>
                {j > 0 && <span style={{ fontSize: '10px', color: '#475569' }}>→</span>}
                <span style={{
                  fontSize: '9px', color: '#94a3b8', backgroundColor: 'rgba(148,163,184,0.1)',
                  padding: '1px 5px', borderRadius: '3px', maxWidth: '120px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {node.split(':').slice(0, 2).join(':')}
                </span>
              </React.Fragment>
            ))}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div data-testid="smart-wallet-leaderboard" style={{
      position: 'absolute', top: 8, right: 8, bottom: 8,
      width: '320px', zIndex: 30,
      backgroundColor: 'rgba(10, 14, 26, 0.95)',
      border: '1px solid rgba(100, 116, 139, 0.2)',
      borderRadius: '12px', backdropFilter: 'blur(14px)',
      display: 'flex', flexDirection: 'column',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: '2px', padding: '8px 8px 0',
        borderBottom: '1px solid rgba(100,116,139,0.15)',
      }}>
        {TAB_CONFIG.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              data-testid={`leaderboard-tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
                padding: '7px 4px', border: 'none', cursor: 'pointer',
                fontSize: '10px', fontWeight: 600, borderRadius: '6px 6px 0 0',
                backgroundColor: isActive ? 'rgba(30,41,59,0.6)' : 'transparent',
                color: isActive ? '#f1f5f9' : '#64748b',
                borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                transition: 'all 0.15s',
              }}
            >
              <Icon size={12} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#475569', fontSize: '11px' }}>
            Loading...
          </div>
        ) : (
          <>
            {activeTab === 'wallets' && renderWallets()}
            {activeTab === 'clusters' && renderClusters()}
            {activeTab === 'routes' && renderRoutes()}
          </>
        )}
      </div>
    </div>
  );
}

function MetricCell({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '9px', color: '#64748b', marginBottom: '1px' }}>{label}</div>
      <div style={{ fontSize: '11px', fontWeight: 600, color }}>{value}</div>
    </div>
  );
}
