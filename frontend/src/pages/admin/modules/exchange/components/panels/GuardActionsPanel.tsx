/**
 * Guard Actions Panel
 * ====================
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface GuardActionsPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function GuardActionsPanel({ snapshot }: GuardActionsPanelProps) {
  const a = snapshot.uri.actions;
  const uri = snapshot.uri;

  return (
    <Card 
      title="Guard Actions" 
      right={
        a.safeMode ? (
          <span className="text-xs font-semibold text-amber-600">
            SAFE MODE ON
          </span>
        ) : (
          <span className="text-xs font-semibold text-emerald-600">
            NORMAL
          </span>
        )
      }
    >
      <div className="space-y-3">
        {/* Action Status */}
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
            <span className="text-gray-600">Training</span>
            <span className={`font-semibold ${a.trainingBlocked ? 'text-red-600' : 'text-green-600'}`}>
              {a.trainingBlocked ? 'BLOCKED' : 'OK'}
            </span>
          </div>
          <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
            <span className="text-gray-600">Promotion</span>
            <span className={`font-semibold ${a.promotionBlocked ? 'text-red-600' : 'text-green-600'}`}>
              {a.promotionBlocked ? 'BLOCKED' : 'OK'}
            </span>
          </div>
          <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
            <span className="text-gray-600">Workers</span>
            <span className={`font-semibold ${a.workersEnabled ? 'text-green-600' : 'text-red-600'}`}>
              {a.workersEnabled ? 'OK' : 'DISABLED'}
            </span>
          </div>
        </div>

        {/* Multipliers */}
        <div className="pt-3">
          <div className="text-xs text-gray-500 mb-2">MULTIPLIERS</div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Confidence ×</span>
              <span className={`font-semibold ${a.confidenceMultiplier < 1 ? 'text-amber-600' : 'text-gray-900'}`}>
                {a.confidenceMultiplier.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Size ×</span>
              <span className={`font-semibold ${a.sizeMultiplier < 1 ? 'text-amber-600' : 'text-gray-900'}`}>
                {a.sizeMultiplier.toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        {/* Safe Mode Reason */}
        {a.safeMode && a.safeModeReason && (
          <div className="pt-3">
            <div className="text-xs text-gray-500 mb-1">SAFE MODE REASON</div>
            <div className="p-2 bg-amber-50 rounded-lg text-sm text-amber-800">
              {a.safeModeReason}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
