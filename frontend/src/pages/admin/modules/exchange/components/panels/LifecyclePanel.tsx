/**
 * Lifecycle Panel
 * ================
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface LifecyclePanelProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function LifecyclePanel({ snapshot }: LifecyclePanelProps) {
  const l = snapshot.lifecycle;

  return (
    <Card 
      title="Lifecycle & Shadow" 
      right={
        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
          l.mode === 'ML' ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'
        }`}>
          {l.mode}
        </span>
      }
    >
      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Active Mode</span>
          <span className="font-medium text-gray-900">{l.mode}</span>
        </div>
        
        {l.activeModelVersion && (
          <div className="flex justify-between">
            <span className="text-gray-500">Active Model</span>
            <span className="font-medium text-gray-900">{l.activeModelVersion}</span>
          </div>
        )}
        
        <div className="flex justify-between">
          <span className="text-gray-500">Shadow Status</span>
          <StatusBadge level={l.shadowStatus || 'UNKNOWN'} />
        </div>
        
        <div className="flex justify-between">
          <span className="text-gray-500">Edge Delta (ML − RULE)</span>
          <span className={`font-medium ${(l.edgeDelta ?? 0) > 0 ? 'text-green-600' : 'text-gray-600'}`}>
            {l.edgeDelta !== undefined ? `${(l.edgeDelta * 100).toFixed(2)}%` : '—'}
          </span>
        </div>
        
        <div className="flex justify-between">
          <span className="text-gray-500">Divergence</span>
          <span className="font-medium text-gray-900">
            {l.divergence !== undefined ? `${(l.divergence * 100).toFixed(2)}%` : '—'}
          </span>
        </div>
        
        <div className="flex justify-between">
          <span className="text-gray-500">Shadow Decisions</span>
          <span className="font-medium text-gray-900">{l.shadowDecisions ?? 0}</span>
        </div>

        {l.rollbackCooldown?.active && (
          <div className="pt-2">
            <div className="flex justify-between">
              <span className="text-amber-600">Rollback Cooldown</span>
              <span className="font-medium text-amber-600">
                {l.rollbackCooldown.remainingDays}d remaining
              </span>
            </div>
          </div>
        )}
      </div>
      
      <div className="mt-3 pt-3 text-xs text-gray-500">
        Promotion requires: &gt; 2% edge over 3 sustained windows
      </div>
    </Card>
  );
}
