import React from 'react';
import { OnchainRuntimeResponse, OnchainGovStateResponse } from '../lib/onchainGovernanceApi';
import { StatusBadge } from './StatusBadge';
import { MiniCard } from './Card';

interface HeaderStripProps {
  runtime: OnchainRuntimeResponse | null;
  govState: OnchainGovStateResponse | null;
}

export function HeaderStrip({ runtime, govState }: HeaderStripProps) {
  const enabled = runtime?.enabled ?? false;
  const provider = runtime?.provider ?? 'unknown';
  const guardrailsPass = govState?.guardrails?.allPassed ?? false;
  const policyVersion = govState?.activePolicy?.version ?? 'N/A';
  const mainReason = govState?.guardrails?.reasons?.[0] ?? null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-800">OnChain V2 Module</h2>
        <div className="flex items-center gap-2">
          <StatusBadge status={enabled ? 'OK' : 'CRITICAL'} />
          <span className="text-sm text-slate-600">{enabled ? 'ENABLED' : 'DISABLED'}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MiniCard 
          label="Provider" 
          value={provider.toUpperCase()} 
          badge={
            <span className={`text-xs px-2 py-0.5 rounded ${
              provider === 'rpc' && runtime?.rpcConfigured 
                ? 'bg-blue-100 text-blue-700' 
                : 'bg-slate-100 text-slate-600'
            }`}>
              {provider === 'mock' ? 'MOCK' : runtime?.rpcConfigured ? 'RPC_OK' : 'RPC_NOT_CONFIGURED'}
            </span>
          }
        />
        
        <MiniCard 
          label="Policy Version" 
          value={policyVersion}
        />
        
        <MiniCard 
          label="Guardrails" 
          value={guardrailsPass ? 'PASS' : 'BLOCK'}
          badge={<StatusBadge status={guardrailsPass ? 'PASS' : 'BLOCK'} />}
        />
        
        <MiniCard 
          label="Latest Block" 
          value={runtime?.latestBlock?.toLocaleString() ?? 'N/A'}
        />
      </div>
      
      {mainReason && (
        <div className="mt-4 p-3 bg-amber-50 border border-amber-100 rounded-lg">
          <div className="text-xs text-amber-600 font-medium">Guardrails Issue:</div>
          <div className="text-sm text-amber-800">{mainReason}</div>
        </div>
      )}
    </div>
  );
}
