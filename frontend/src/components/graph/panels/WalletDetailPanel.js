import React from 'react';
import { X } from 'lucide-react';
import { fmtUsd } from '../utils';
import { toast } from 'sonner';

const WalletDetailPanel = React.memo(({ expandedWalletSignal, onClose }) => {
  if (!expandedWalletSignal) return null;
  const { wallets, title, flowKey } = expandedWalletSignal;
  const shortAddr = (id) => {
    const parts = (id || '').split(':');
    const addr = parts.length >= 2 ? parts[1] : id;
    if (!addr || addr.length < 10) return addr;
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };
  const fullAddr = (id) => {
    const parts = (id || '').split(':');
    return parts.length >= 2 ? parts[1] : id;
  };
  const copyAddr = (id) => {
    const addr = fullAddr(id);
    navigator.clipboard.writeText(addr);
    toast.success('Address copied');
  };

  return (
    <div data-testid="wallet-detail-panel" style={{
      position: 'absolute', top: '56px', right: '340px', zIndex: 31,
      backgroundColor: 'rgba(15, 23, 42, 0.97)', border: '1px solid rgba(96,165,250,0.2)',
      borderRadius: '12px', padding: '12px', color: '#e2e8f0', backdropFilter: 'blur(12px)',
      width: '260px', fontSize: '11px', boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      maxHeight: 'calc(100% - 72px)', overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontWeight: 600, fontSize: '11px', color: '#60a5fa' }}>{title}</span>
        <button data-testid="wallet-panel-close" onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}>
          <X size={13} />
        </button>
      </div>
      <div style={{ fontSize: '9px', color: '#64748b', marginBottom: '6px' }}>
        {wallets.length} wallet{wallets.length !== 1 ? 's' : ''} &middot; click address to copy
      </div>
      {/* Wallet list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        {expandedWalletSignal.tokenFrom && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#64748b', padding: '0 7px', marginBottom: '2px' }}>
            <span>Address</span>
            <div style={{ display: 'flex', gap: '12px' }}>
              <span style={{ color: '#E5484D' }}>{expandedWalletSignal.tokenFrom}</span>
              <span style={{ color: '#30A46C' }}>{expandedWalletSignal.tokenTo}</span>
            </div>
          </div>
        )}
        {wallets.map((w, wi) => (
          <div key={wi} data-testid={`wallet-row-${wi}`} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '5px 7px', borderRadius: '6px', backgroundColor: 'rgba(100,116,139,0.08)',
            border: '1px solid rgba(100,116,139,0.1)',
          }}>
            <span data-testid={`wallet-addr-${wi}`}
              onClick={() => copyAddr(w.id)}
              title={fullAddr(w.id)}
              style={{
                fontFamily: 'monospace', fontSize: '11px', color: '#60a5fa',
                cursor: 'pointer', fontWeight: 500,
              }}>
              {shortAddr(w.id)}
            </span>
            {expandedWalletSignal.tokenFrom ? (
              <div style={{ display: 'flex', gap: '12px' }}>
                <span style={{ fontSize: '10px', color: '#E5484D', fontWeight: 500 }}>{fmtUsd(w.sell_exposure || w.outflow || 0)}</span>
                <span style={{ fontSize: '10px', color: '#30A46C', fontWeight: 500 }}>{fmtUsd(w.buy_exposure || w.inflow || 0)}</span>
              </div>
            ) : (
              <span style={{ fontSize: '10px', color: '#e2e8f0', fontWeight: 500 }}>
                {fmtUsd(w[flowKey] || w.inflow || w.outflow || 0)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
});

WalletDetailPanel.displayName = 'WalletDetailPanel';

export default WalletDetailPanel;
