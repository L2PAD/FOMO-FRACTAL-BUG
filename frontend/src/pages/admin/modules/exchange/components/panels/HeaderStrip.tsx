/**
 * Header Strip Panel
 * ===================
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface HeaderStripProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function HeaderStrip({ snapshot }: HeaderStripProps) {
  const { manifest, uri } = snapshot;

  return (
    <Card
      title="EXCHANGE MODULE CONTROL CENTER"
      right={
        <div className="flex items-center gap-2">
          <StatusBadge level={uri.uriLevel} />
          {manifest.frozen && (
            <span className="text-xs font-semibold text-indigo-600">
              FROZEN
            </span>
          )}
          {uri.actions.safeMode && (
            <span className="text-xs font-semibold text-amber-600">
              SAFE MODE
            </span>
          )}
        </div>
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 text-sm">
        <div>
          <div className="text-gray-500 text-xs">Version</div>
          <div className="font-semibold text-gray-900">{manifest.version}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Feature Mode</div>
          <div className="font-semibold text-gray-900">{manifest.featureMode || 'CORE_ONLY'}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">URI Score</div>
          <div className="font-semibold text-gray-900">{Math.round(uri.uriScore * 100)}%</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Confidence ×</div>
          <div className="font-semibold text-gray-900">{uri.actions.confidenceMultiplier.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Size ×</div>
          <div className="font-semibold text-gray-900">{uri.actions.sizeMultiplier.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Training</div>
          <div className={`font-semibold ${uri.actions.trainingBlocked ? 'text-red-600' : 'text-green-600'}`}>
            {uri.actions.trainingBlocked ? 'BLOCKED' : 'OK'}
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Promotion</div>
          <div className={`font-semibold ${uri.actions.promotionBlocked ? 'text-red-600' : 'text-green-600'}`}>
            {uri.actions.promotionBlocked ? 'BLOCKED' : 'OK'}
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Mode</div>
          <div className="font-semibold text-gray-900">{snapshot.lifecycle.mode}</div>
        </div>
      </div>
    </Card>
  );
}
