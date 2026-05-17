/**
 * SentimentSignalBreakdown — BLOCK P2
 * =====================================
 * 
 * Shows RAW → FINAL transformation with explanation
 * - Confidence transformation
 * - URI/Calibration/SafeMode impact
 * - Risk size multiplier
 * 
 * Light theme, expandable details
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Info, ShieldAlert, AlertTriangle, Activity, Gauge, Scale } from 'lucide-react';

export default function SentimentSignalBreakdown({ explain }) {
  const [open, setOpen] = useState(false);

  if (!explain) return null;

  const { core, adjustments, safety } = explain;

  const pct = (x) => (x * 100).toFixed(1);
  const fmt = (x) => x.toFixed(2);

  const hasAdjustments = 
    adjustments.uriMultiplier !== 1 || 
    adjustments.calibrationMultiplier !== 1 ||
    safety.safeMode;

  return (
    <div 
      className="bg-white border border-gray-200 rounded-xl overflow-hidden"
      data-testid="sentiment-signal-breakdown"
    >
      {/* Header Strip - Always Visible */}
      <div className="px-4 py-3 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4 flex-wrap">
          {/* Confidence transformation */}
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">Confidence:</span>
            <span className="text-sm font-medium text-gray-800">
              {pct(core.rawConfidence)}%
            </span>
            {core.rawConfidence !== adjustments.finalConfidence && (
              <>
                <span className="text-gray-400">→</span>
                <span className={`text-sm font-semibold ${
                  adjustments.finalConfidence === 0 
                    ? 'text-amber-600' 
                    : adjustments.finalConfidence < core.rawConfidence 
                      ? 'text-orange-600' 
                      : 'text-emerald-600'
                }`}>
                  {pct(adjustments.finalConfidence)}%
                </span>
              </>
            )}
          </div>

          {/* Risk size */}
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">Risk Size:</span>
            <span className={`text-sm font-medium ${
              adjustments.sizeMultiplier < 1 ? 'text-amber-600' : 'text-gray-800'
            }`}>
              {fmt(adjustments.sizeMultiplier)}x
            </span>
          </div>

          {/* Flags */}
          <div className="flex items-center gap-2">
            {safety.safeMode && (
              <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
                <ShieldAlert className="w-3 h-3" />
                SAFE MODE
              </span>
            )}
            {adjustments.uriMultiplier !== 1 && !safety.safeMode && (
              <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-medium rounded-full">
                URI_ADJ
              </span>
            )}
            {adjustments.calibrationMultiplier !== 1 && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                CALIBRATED
              </span>
            )}
            {core.quality === 'LOW_VOLUME' && (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-full">
                LOW_DATA
              </span>
            )}
          </div>
        </div>

        {/* Expand button */}
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1 px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
        >
          <Info className="w-4 h-4" />
          {open ? 'Hide Details' : 'Explain Signal'}
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded Details */}
      {open && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Core Signal */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Core Signal
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Bias:</span>
                  <span className={`font-medium ${
                    core.bias > 0 ? 'text-emerald-600' : core.bias < 0 ? 'text-red-600' : 'text-gray-600'
                  }`}>
                    {core.bias >= 0 ? '+' : ''}{fmt(core.bias)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Score:</span>
                  <span className="font-medium text-gray-800">{pct(core.score)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Raw Confidence:</span>
                  <span className="font-medium text-gray-800">{pct(core.rawConfidence)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Events:</span>
                  <span className={`font-medium ${
                    core.quality === 'LOW_VOLUME' ? 'text-amber-600' : 'text-gray-800'
                  }`}>
                    {core.eventsCount} ({core.quality})
                  </span>
                </div>
              </div>
            </div>

            {/* Adjustments */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <Gauge className="w-4 h-4" />
                Adjustments
              </h4>
              
              {/* Formula */}
              <div className="bg-gray-50 rounded-lg p-3 mb-3 text-sm font-mono">
                <span className="text-gray-600">{fmt(core.rawConfidence)}</span>
                <span className="text-gray-400"> × </span>
                <span className={adjustments.uriMultiplier !== 1 ? 'text-indigo-600 font-semibold' : 'text-gray-600'}>
                  {fmt(adjustments.uriMultiplier)}
                </span>
                <span className="text-gray-400"> × </span>
                <span className={adjustments.calibrationMultiplier !== 1 ? 'text-blue-600 font-semibold' : 'text-gray-600'}>
                  {fmt(adjustments.calibrationMultiplier)}
                </span>
                <span className="text-gray-400"> = </span>
                <span className="text-gray-900 font-semibold">{fmt(adjustments.finalConfidence)}</span>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">URI Multiplier:</span>
                  <span className={`font-medium ${
                    adjustments.uriMultiplier !== 1 ? 'text-indigo-600' : 'text-gray-800'
                  }`}>
                    ×{fmt(adjustments.uriMultiplier)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Calibration:</span>
                  <span className={`font-medium ${
                    adjustments.calibrationMultiplier !== 1 ? 'text-blue-600' : 'text-gray-800'
                  }`}>
                    ×{fmt(adjustments.calibrationMultiplier)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Size Multiplier:</span>
                  <span className={`font-medium ${
                    adjustments.sizeMultiplier !== 1 ? 'text-amber-600' : 'text-gray-800'
                  }`}>
                    ×{fmt(adjustments.sizeMultiplier)}
                  </span>
                </div>
              </div>
            </div>

            {/* Safety */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                Safety Status
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">URI Level:</span>
                  <span className={`font-medium ${
                    safety.uriLevel === 'OK' ? 'text-emerald-600' :
                    safety.uriLevel === 'WARN' ? 'text-yellow-600' :
                    safety.uriLevel === 'DEGRADED' ? 'text-orange-600' :
                    'text-red-600'
                  }`}>
                    {safety.uriLevel}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Calibration:</span>
                  <span className={`font-medium ${
                    safety.calibrationStatus === 'OK' ? 'text-emerald-600' : 'text-blue-600'
                  }`}>
                    {safety.calibrationStatus}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Safe Mode:</span>
                  <span className={`font-medium ${
                    safety.safeMode ? 'text-amber-600' : 'text-emerald-600'
                  }`}>
                    {safety.safeMode ? 'ON' : 'OFF'}
                  </span>
                </div>
                {safety.safeModeReason && (
                  <div className="mt-2 p-2 bg-amber-50 rounded text-xs text-amber-700">
                    {safety.safeModeReason}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
