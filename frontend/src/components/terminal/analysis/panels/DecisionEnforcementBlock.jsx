/**
 * Decision Enforcement Block
 * ==========================
 * 
 * Shows RAW vs ENFORCED decision with full transparency:
 * - What system wanted (raw)
 * - What system did (enforced)
 * - Why it changed (reason_chain)
 * - What was applied (overrides)
 * - ORCH-4: Execution routing (route type, status, order ID)
 * 
 * This is the debug console for the trading brain.
 */

import React from 'react';

export default function DecisionEnforcementBlock({
  decisionRaw,
  decisionEnforced,
  reasonChain = [],
  blocked,
  blockReason,
  finalAction,
  overrides = {},
  executionControl,  // ORCH-4: New prop
}) {
  // Determine status
  const status = blocked
    ? 'BLOCKED'
    : decisionRaw?.action !== decisionEnforced?.action
    ? 'MODIFIED'
    : 'ALLOWED';

  // Status color
  const statusColor =
    status === 'BLOCKED'
      ? 'text-red-400 bg-red-500/10 border-red-500/30'
      : status === 'MODIFIED'
      ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
      : 'text-green-400 bg-green-500/10 border-green-500/30';

  const statusIcon =
    status === 'BLOCKED'
      ? '✖'
      : status === 'MODIFIED'
      ? '⚠'
      : '✔';

  // ORCH-4: Extract routing info
  const routing = executionControl?.routing;
  const routeType = routing?.route_type || 'none';
  const routeStatus = routing?.status || '—';
  const orderId = routing?.order_id || '—';
  const routed = routing?.routed || false;

  // Route status color
  const routeStatusColor =
    routeStatus === 'FILLED'
      ? 'text-green-400'
      : routeStatus === 'PLACED'
      ? 'text-blue-400'
      : routeStatus === 'REJECTED' || routeStatus === 'BLOCKED'
      ? 'text-red-400'
      : routeStatus === 'FAILED'
      ? 'text-orange-400'
      : 'text-gray-400';

  return (
    <div className="bg-[#0B0F14] border border-white/10 rounded-lg p-4 space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="text-xs text-gray-400 uppercase tracking-wider font-semibold">
          Decision Enforcement
        </div>
        <div
          className={`text-xs font-bold px-2 py-1 rounded border ${statusColor}`}
        >
          {statusIcon} {status}
        </div>
      </div>

      {/* RAW vs FINAL */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#111827] rounded p-2">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Raw</div>
          <div className="text-white font-medium text-sm">
            {decisionRaw?.action || decisionRaw?.mode || '—'}
          </div>
          {decisionRaw?.confidence != null && (
            <div className="text-xs text-gray-400 mt-1">
              {Math.round(decisionRaw.confidence * 100)}% conf
            </div>
          )}
        </div>

        <div className="bg-[#111827] rounded p-2">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Final</div>
          <div className="text-white font-medium text-sm">
            {finalAction || decisionEnforced?.action || decisionEnforced?.mode || '—'}
          </div>
          {decisionEnforced?.size_multiplier != null && (
            <div className="text-xs text-cyan-400 mt-1">
              {Math.round(decisionEnforced.size_multiplier * 100)}% size
            </div>
          )}
        </div>
      </div>

      {/* Block Reason (if blocked) */}
      {blocked && blockReason && (
        <div className="bg-red-500/10 border border-red-500/30 rounded p-2">
          <div className="text-xs text-red-400 font-semibold">
            🚫 BLOCKED: {blockReason.replace(/_/g, ' ').toUpperCase()}
          </div>
        </div>
      )}

      {/* ORCH-4: Execution Routing */}
      {routing && (
        <div className="bg-[#111827] border border-white/10 rounded p-3 space-y-2">
          <div className="text-[10px] text-gray-500 uppercase">
            Execution Routing
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-gray-500 text-[10px] mb-0.5">Route</div>
              <div className="text-cyan-400 font-semibold uppercase">
                {routeType}
              </div>
            </div>
            <div>
              <div className="text-gray-500 text-[10px] mb-0.5">Status</div>
              <div className={`font-semibold ${routeStatusColor}`}>
                {routeStatus}
              </div>
            </div>
            <div>
              <div className="text-gray-500 text-[10px] mb-0.5">Routed</div>
              <div className={routed ? 'text-green-400' : 'text-gray-400'}>
                {routed ? '✓' : '✗'}
              </div>
            </div>
          </div>
          {orderId !== '—' && (
            <div className="pt-2 border-t border-white/5">
              <div className="text-gray-500 text-[10px] mb-1">Order ID</div>
              <div className="text-gray-300 font-mono text-[10px] bg-[#0B0F14] px-2 py-1 rounded">
                {orderId}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Reason Chain */}
      {reasonChain && reasonChain.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] text-gray-500 uppercase">
            Enforcement Reasons
          </div>
          <div className="flex flex-wrap gap-1.5">
            {reasonChain.map((reason, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-1 bg-[#1F2937] text-cyan-300 rounded font-mono"
              >
                {reason}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Overrides Applied */}
      {overrides && Object.keys(overrides).length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] text-gray-500 uppercase">
            Active Overrides
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(overrides).map(([key, value]) => (
              <span
                key={key}
                className="text-[10px] px-2 py-1 bg-amber-500/10 text-amber-300 rounded border border-amber-500/20"
              >
                {key}: {value}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
