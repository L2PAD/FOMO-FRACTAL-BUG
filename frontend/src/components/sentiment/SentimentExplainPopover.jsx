/**
 * SentimentExplainPopover — BLOCK P2.3
 * =====================================
 * 
 * Per-row explain popover for Top 20 table
 * Shows signal breakdown for individual symbols
 */

import React, { useState, useRef, useEffect } from 'react';
import { Info, X } from 'lucide-react';

export default function SentimentExplainPopover({ explain, symbol }) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [open]);

  if (!explain) return null;

  const pct = (x) => (x * 100).toFixed(1);
  const fmt = (x) => x.toFixed(2);

  return (
    <div className="relative" ref={popoverRef}>
      <button
        onClick={() => setOpen(!open)}
        className={`p-1 rounded transition-colors ${
          open 
            ? 'bg-indigo-100 text-indigo-600' 
            : 'text-gray-400 hover:text-indigo-600 hover:bg-gray-100'
        }`}
        data-testid={`explain-popover-trigger-${symbol}`}
      >
        <Info className="w-4 h-4" />
      </button>

      {open && (
        <div 
          className="absolute right-full mr-2 top-0 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-50"
          data-testid={`explain-popover-content-${symbol}`}
        >
          {/* Header */}
          <div className="px-3 py-2 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">
              {symbol} Signal
            </span>
            <button 
              onClick={() => setOpen(false)}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-3 space-y-3 text-xs">
            {/* Bias & Confidence */}
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-500">Bias:</span>
                <span className={`font-semibold ${
                  explain.bias > 0 ? 'text-emerald-600' : 
                  explain.bias < 0 ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {explain.bias >= 0 ? '+' : ''}{fmt(explain.bias)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Raw Confidence:</span>
                <span className="font-medium text-gray-700">{pct(explain.rawConfidence)}%</span>
              </div>
            </div>

            {/* Multipliers */}
            <div className="pt-2 border-t border-gray-100 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-500">URI ×:</span>
                <span className={`font-medium ${
                  explain.uriMultiplier !== 1 ? 'text-indigo-600' : 'text-gray-700'
                }`}>
                  {fmt(explain.uriMultiplier)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Calibration ×:</span>
                <span className={`font-medium ${
                  explain.calibrationMultiplier !== 1 ? 'text-blue-600' : 'text-gray-700'
                }`}>
                  {fmt(explain.calibrationMultiplier)}
                </span>
              </div>
            </div>

            {/* Final */}
            <div className="pt-2 border-t border-gray-100">
              <div className="flex justify-between">
                <span className="text-gray-500">Final Confidence:</span>
                <span className={`font-semibold ${
                  explain.finalConfidence === 0 ? 'text-amber-600' :
                  explain.finalConfidence < explain.rawConfidence ? 'text-orange-600' :
                  'text-emerald-600'
                }`}>
                  {pct(explain.finalConfidence)}%
                </span>
              </div>
            </div>

            {/* Flags */}
            {(explain.flags.safeMode || explain.flags.uriAdjustment || explain.flags.lowData) && (
              <div className="pt-2 border-t border-gray-100 flex flex-wrap gap-1">
                {explain.flags.safeMode && (
                  <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[10px] font-medium rounded">
                    SAFE MODE
                  </span>
                )}
                {explain.flags.uriAdjustment && (
                  <span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 text-[10px] font-medium rounded">
                    URI ADJ
                  </span>
                )}
                {explain.flags.lowData && (
                  <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-medium rounded">
                    LOW DATA
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Formula footer */}
          <div className="px-3 py-2 bg-gray-50 rounded-b-xl text-[10px] font-mono text-gray-500">
            {fmt(explain.rawConfidence)} × {fmt(explain.uriMultiplier)} × {fmt(explain.calibrationMultiplier)} = {fmt(explain.finalConfidence)}
          </div>
        </div>
      )}
    </div>
  );
}
