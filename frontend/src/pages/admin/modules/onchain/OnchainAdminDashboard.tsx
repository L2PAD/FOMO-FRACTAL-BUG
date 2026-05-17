import React, { useEffect, useState } from 'react';
import { useOnchainAdmin } from './hooks/useOnchainAdmin';
import { getActivePolicy, OnchainGovPolicy } from './lib/onchainGovernanceApi';
import { HeaderStrip } from './components/HeaderStrip';
import { PolicyPanel } from './components/PolicyPanel';
import { GuardrailsPanel } from './components/GuardrailsPanel';
import { GuardrailsPanelV2 } from './components/GuardrailsPanelV2';
import { RollingDriftPanel } from './components/RollingDriftPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { AuditPanel } from './components/AuditPanel';
import { RpcPoolPanel } from './components/RpcPoolPanel';
import { SnapshotBuilderPanel } from './components/SnapshotBuilderPanel';

export default function OnchainAdminDashboard() {
  const { runtime, govState, auditLog, loading, error, refetch, lastRefresh } = useOnchainAdmin(15000);
  const [activePolicy, setActivePolicy] = useState<OnchainGovPolicy | null>(null);

  useEffect(() => {
    async function fetchPolicy() {
      try {
        const res = await getActivePolicy();
        if (res.ok) {
          setActivePolicy(res.policy);
        }
      } catch {
        // Ignore
      }
    }
    fetchPolicy();
  }, [lastRefresh]);

  const handleRefresh = () => {
    refetch();
    getActivePolicy().then(res => {
      if (res.ok) setActivePolicy(res.policy);
    }).catch(() => {});
  };

  // Show skeleton if still loading initial data
  if (loading && !runtime && !govState) {
    return (
      <div className="p-6 flex items-center justify-center" data-testid="onchain-loading">
        <div className="text-slate-500">Loading OnChain Admin...</div>
      </div>
    );
  }

  if (error && !runtime && !govState) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
          <div className="font-semibold mb-2">Error Loading Dashboard</div>
          <div className="text-sm">{error}</div>
          <button 
            onClick={refetch}
            className="mt-4 px-4 py-2 bg-red-100 hover:bg-red-200 rounded-lg text-sm font-medium"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800">OnChain Module</h1>
          <p className="text-sm text-slate-500">Governance & Reliability Control</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">
            Last refresh: {new Date(lastRefresh).toLocaleTimeString()}
          </span>
          <button
            onClick={handleRefresh}
            className="px-3 py-1.5 text-sm bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Header Strip */}
      <HeaderStrip runtime={runtime} govState={govState} />

      {/* RPC Pool Configuration */}
      <RpcPoolPanel />

      {/* Snapshot Builder & Indexer */}
      <SnapshotBuilderPanel />

      {/* O9.5 Governance Panels */}
      <GuardrailsPanelV2 symbol="ETH" />
      <RollingDriftPanel symbol="ETH" />

      {/* Main Grid */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Left Column */}
        <div className="space-y-4">
          <PolicyPanel policy={activePolicy} />
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          <ActionsPanel onRefresh={handleRefresh} />
        </div>
      </div>

      {/* Audit Log */}
      <AuditPanel entries={auditLog} />
    </div>
  );
}
