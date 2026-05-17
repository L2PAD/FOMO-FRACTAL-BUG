/**
 * Feature Lock Panel
 * ===================
 * 

 */

import React from 'react';
import Card from '../Card';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface FeatureLockPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function FeatureLockPanel({ snapshot }: FeatureLockPanelProps) {
  const lock = snapshot.featureLock;
  const uri = snapshot.uri;

  return (
    <Card 
      title="Feature Lock (TTL)" 
      right={
        <span className={`text-xs font-semibold ${
          lock.locked 
            ? 'text-amber-600' 
            : 'text-emerald-600'
        }`}>
          {lock.locked ? 'LOCKED' : 'UNLOCKED'}
        </span>
      }
    >
      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <span className={`w-3 h-3 rounded-full ${lock.locked ? 'bg-amber-500' : 'bg-emerald-500'}`} />
          <span className="text-gray-600">{lock.locked ? 'Module can be modified' : 'Module can be modified'}</span>
        </div>
        
        {lock.locked && (
          <>
            <div className="text-gray-500">
              Locked until: <span className="font-medium text-gray-900">
                {lock.lockedUntil ? new Date(lock.lockedUntil).toLocaleString() : '—'}
              </span>
            </div>
            {lock.lockedBy && (
              <div className="text-gray-500">
                Locked by: <span className="font-medium text-gray-900">{lock.lockedBy}</span>
              </div>
            )}
            {lock.remainingMinutes !== undefined && (
              <div className="text-gray-500">
                Remaining: <span className="font-medium text-amber-600">{lock.remainingMinutes} min</span>
              </div>
            )}
          </>
        )}
      </div>
      
      <div className="mt-3 pt-3">
        <div className="text-xs text-gray-500">Blocked Operations when Locked:</div>
        <div className="flex flex-wrap gap-1 mt-1">
          {['retrain', 'promote', 'rollback', 'config_update', 'baseline_create'].map(op => (
            <span key={op} className="text-xs text-gray-600">
              {op}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
