/**
 * Data Status Banner — Phase 5, Block 5.2
 * =========================================
 *
 * Unified banner for DATA_OK / DATA_DEGRADED / DATA_MISSING.
 * No version strings, no item counts, no technical debug info.
 */

import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';

export type DataStatus = 'OK' | 'DEGRADED' | 'MISSING';

interface DataStatusBannerProps {
  status: DataStatus;
  context?: string;
}

export function DataStatusBanner({ status, context }: DataStatusBannerProps) {
  if (status === 'OK') return null;

  if (status === 'MISSING') {
    return (
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-50"
        data-testid="data-status-banner-missing"
      >
        <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
        <p className="text-sm text-red-700">
          On-chain data currently unavailable.
          {context && <span className="text-red-500 ml-1">{context}</span>}
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50"
      data-testid="data-status-banner-degraded"
    >
      <Info className="w-4 h-4 text-amber-600 flex-shrink-0" />
      <p className="text-sm text-amber-700">
        Limited coverage. Signals confidence reduced.
        {context && <span className="text-amber-500 ml-1">{context}</span>}
      </p>
    </div>
  );
}

// ── Status computation helpers ──

export function computeOverviewStatus(lare: any): DataStatus {
  if (!lare) return 'MISSING';
  const d = lare.data || lare;
  if (d.score == null || d.regime == null) return 'MISSING';
  if ((d.confidence ?? 0) < 0.35) return 'DEGRADED';
  return 'OK';
}

export function computeSignalsStatus(
  items: any[],
  meta?: { confidence?: number; tokenCount?: number }
): DataStatus {
  if (!items || items.length === 0) return 'MISSING';
  if (meta) {
    if ((meta.confidence ?? 0) < 0.35) return 'DEGRADED';
    if ((meta.tokenCount ?? 0) === 0) return 'MISSING';
  }
  return 'OK';
}

export function computeAssetsStatus(profile: any): DataStatus {
  if (!profile) return 'MISSING';
  const snap = profile.snapshot || {};
  if (snap.priceUsd == null && snap.reliability === 0) return 'MISSING';
  if ((snap.reliability ?? 0) < 0.4) return 'DEGRADED';
  return 'OK';
}

export function computeActorsStatus(items: any[]): DataStatus {
  if (!items || items.length === 0) return 'MISSING';
  const avgConf =
    items.reduce((s: number, i: any) => s + (i.attributionConfidence ?? 0), 0) / items.length;
  if (avgConf < 0.4) return 'DEGRADED';
  return 'OK';
}
