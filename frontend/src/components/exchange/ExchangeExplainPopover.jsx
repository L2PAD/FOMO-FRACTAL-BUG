/**
 * Exchange Explain Popover
 * =========================
 * 
 * BLOCK E4/E5: Explain popover for performance and top-alts tables
 * Shows RAW → FINAL transformation details
 */

import { useState, useRef, useEffect } from "react";

export default function ExchangeExplainPopover({ row }) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const explain = row?.explain || {};
  const rawConf = explain.rawConfidence || row?.confidenceRaw || 0;
  const uriMul = explain.uriMultiplier || 1;
  const calibMul = explain.calibrationMultiplier || 1;
  const capitalMul = explain.capitalMultiplier || 1;
  const finalConf = explain.finalConfidence || row?.confidenceFinal || 0;
  const flags = explain.flags || {};

  return (
    <div className="relative" ref={popoverRef}>
      <button 
        onClick={() => setOpen(!open)}
        className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded transition-colors"
      >
        Explain
      </button>

      {open && (
        <div className="absolute right-0 top-8 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 w-56">
          {/* RAW Confidence */}
          <div className="text-xs text-gray-500 mb-3">
            <div className="font-medium text-gray-700 mb-2">Signal Breakdown</div>
            <div className="flex justify-between py-1">
              <span>RAW Confidence</span>
              <span className="font-medium text-gray-900">{Math.round(rawConf * 100)}%</span>
            </div>
          </div>

          {/* Multipliers */}
          <div className="text-xs border-t border-gray-100 pt-3 space-y-1.5">
            <div className="flex justify-between">
              <span className="text-gray-500">URI ×</span>
              <span className={uriMul !== 1 ? 'text-blue-600 font-medium' : 'text-gray-600'}>
                {uriMul.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Calibration ×</span>
              <span className={calibMul !== 1 ? 'text-purple-600 font-medium' : 'text-gray-600'}>
                {calibMul.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Capital ×</span>
              <span className={capitalMul !== 1 ? 'text-violet-600 font-medium' : 'text-gray-600'}>
                {capitalMul.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Final */}
          <div className="text-xs border-t border-gray-100 pt-3 mt-3">
            <div className="flex justify-between">
              <span className="font-medium text-gray-700">Final Confidence</span>
              <span className="font-semibold text-gray-900">{Math.round(finalConf * 100)}%</span>
            </div>
          </div>

          {/* Flags */}
          {(flags.safeMode || flags.uriAdjustment || flags.capitalGate) && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs font-medium text-gray-700 mb-2">Flags</div>
              <div className="flex flex-wrap gap-1">
                {flags.safeMode && (
                  <span className="text-amber-700 text-xs">
                    SAFE_MODE
                  </span>
                )}
                {flags.uriAdjustment && (
                  <span className="text-blue-700 text-xs">
                    URI_ADJ
                  </span>
                )}
                {flags.capitalGate && (
                  <span className="text-violet-700 text-xs">
                    CAPITAL_GATE
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Formula footer */}
          <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">
            {rawConf.toFixed(2)} × {uriMul.toFixed(2)} × {calibMul.toFixed(2)} × {capitalMul.toFixed(2)} = {finalConf.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}
