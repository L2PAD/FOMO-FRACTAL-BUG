/**
 * Decision Timeline — Sprint 4
 * 
 * Full history of ONE decision as a vertical timeline.
 * Operator opens a decision and understands:
 *   1. How it appeared
 *   2. How it passed through every layer
 *   3. What the operator did
 *   4. What happened after
 * 
 * Design: Trading Terminal style (white, Gilroy, black/white)
 */

import { useState, useEffect } from 'react';
import { ArrowLeft, Clock, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─── Timeline step config ────────────────────────────────────
const STEP_THEME = {
  SIGNAL:           { label: 'Signal Created',         color: '#3b82f6', desc: 'TA Engine generated trading signal' },
  RISK_APPROVED:    { label: 'Risk Approved',          color: '#16a34a', desc: 'RiskManager passed all checks' },
  RISK_REJECTED:    { label: 'Risk Rejected',          color: '#dc2626', desc: 'RiskManager blocked the signal' },
  MODE_GATE:        { label: 'Mode Gate',              color: '#7c3aed', desc: 'Runtime mode routing' },
  R1_SIZING:        { label: 'R1 — Dynamic Sizing',    color: '#0891b2', desc: 'Dynamic Risk Engine applied position sizing' },
  R2_ADAPTIVE:      { label: 'R2 — Adaptive Risk',     color: '#d97706', desc: 'Adaptive dampening based on drawdown/streak' },
  SAFETY:           { label: 'Safety Passed',           color: '#16a34a', desc: 'AutoSafety allowed execution' },
  EXECUTION:        { label: 'Execution Queued',        color: '#059669', desc: 'Order submitted to execution bridge' },
  PENDING_CREATED:  { label: 'Pending — Awaiting Operator', color: '#ca8a04', desc: 'Decision requires operator approval' },
  OPERATOR_CREATED: { label: 'Created by Operator',    color: '#d97706', desc: 'Operator manually created this decision' },
};

const STATUS_BADGE = {
  EXECUTED:    { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0', label: 'EXECUTED' },
  PENDING:     { bg: '#fefce8', text: '#a16207', border: '#fde68a', label: 'PENDING APPROVAL' },
  REJECTED:    { bg: '#fef2f2', text: '#dc2626', border: '#fecaca', label: 'REJECTED' },
  BLOCKED:     { bg: '#fff7ed', text: '#ea580c', border: '#fed7aa', label: 'BLOCKED' },
};

// ─── Price display ───────────────────────────────────────────
function PriceRow({ label, value, color }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[11px] text-neutral-400 uppercase tracking-wide">{label}</span>
      <span className="text-[13px] font-semibold" style={{ color }}>${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
    </div>
  );
}

// ─── Single timeline node ────────────────────────────────────
function TimelineNode({ step, isLast }) {
  const theme = STEP_THEME[step.step] || { label: step.step, color: '#64748b', desc: '' };
  const d = step.data || {};
  const time = new Date(step.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  return (
    <div className="flex gap-4" data-testid={`timeline-node-${step.step.toLowerCase()}`}>
      {/* Left: time + connector */}
      <div className="flex flex-col items-center w-16 flex-shrink-0">
        <span className="text-[11px] font-mono text-neutral-400">{time}</span>
        <div className="w-3 h-3 rounded-full mt-1.5 border-2 bg-white" style={{ borderColor: theme.color }} />
        {!isLast && <div className="w-px flex-1 bg-neutral-200 mt-1" />}
      </div>

      {/* Right: content */}
      <div className={`flex-1 ${isLast ? 'pb-0' : 'pb-6'}`}>
        <div className="bg-white border border-neutral-200 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: theme.color }} />
            <span className="text-[13px] font-semibold text-neutral-900">{theme.label}</span>
          </div>
          <div className="text-[11px] text-neutral-400 mb-2">{theme.desc}</div>

          {/* SIGNAL step: show full price + strategy info */}
          {step.step === 'SIGNAL' && (
            <div className="bg-neutral-50 rounded-md p-2.5 space-y-0.5">
              {d.strategy && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">Strategy</span>
                  <span className="font-semibold text-neutral-700">{d.strategy}</span>
                </div>
              )}
              {d.regime && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">Regime</span>
                  <span className="font-semibold text-neutral-700">{d.regime}</span>
                </div>
              )}
              {d.confidence != null && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">Confidence</span>
                  <span className="font-bold text-neutral-900">{(d.confidence * 100).toFixed(1)}%</span>
                </div>
              )}
              {d.timeframe && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">Timeframe</span>
                  <span className="font-semibold text-neutral-700">{d.timeframe}</span>
                </div>
              )}
              <div className="border-t border-neutral-200 mt-1.5 pt-1.5">
                <PriceRow label="Entry" value={d.entry_price} color="#0f172a" />
                <PriceRow label="Stop" value={d.stop_price} color="#dc2626" />
                <PriceRow label="Target" value={d.target_price} color="#16a34a" />
              </div>
              {d.drivers && Object.keys(d.drivers).length > 0 && (
                <div className="border-t border-neutral-200 mt-1.5 pt-1.5">
                  <div className="text-[10px] text-neutral-400 uppercase tracking-wider mb-1">Drivers</div>
                  <div className="flex gap-2 flex-wrap">
                    {Object.entries(d.drivers).map(([k, v]) => (
                      <span key={k} className="text-[10px] px-1.5 py-0.5 bg-white border border-neutral-200 rounded text-neutral-600">
                        {k}: {typeof v === 'number' ? v.toFixed(1) : v}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* R1 sizing */}
          {step.step === 'R1_SIZING' && (
            <div className="bg-neutral-50 rounded-md p-2.5 space-y-0.5 text-[11px]">
              {d.qty && <div className="flex justify-between"><span className="text-neutral-400">Quantity</span><span className="font-semibold">{d.qty}</span></div>}
              {d.notional_usd && <div className="flex justify-between"><span className="text-neutral-400">Notional</span><span className="font-semibold">${d.notional_usd.toFixed(2)}</span></div>}
              {d.size_multiplier && <div className="flex justify-between"><span className="text-neutral-400">Multiplier</span><span className="font-semibold">{d.size_multiplier.toFixed(2)}x</span></div>}
            </div>
          )}

          {/* R2 adaptive */}
          {step.step === 'R2_ADAPTIVE' && (
            <div className="bg-neutral-50 rounded-md p-2.5 space-y-0.5 text-[11px]">
              {d.r2_multiplier != null && <div className="flex justify-between"><span className="text-neutral-400">R2 Multiplier</span><span className="font-semibold text-amber-600">{d.r2_multiplier.toFixed(2)}x</span></div>}
              {d.final_multiplier != null && <div className="flex justify-between"><span className="text-neutral-400">Final Multiplier</span><span className="font-semibold">{d.final_multiplier.toFixed(2)}x</span></div>}
              {d.final_qty != null && <div className="flex justify-between"><span className="text-neutral-400">Final Qty</span><span className="font-semibold">{d.final_qty.toFixed(4)}</span></div>}
              {d.components && (
                <div className="flex gap-2 mt-1">
                  {Object.entries(d.components).map(([k, v]) => (
                    <span key={k} className="text-[10px] px-1.5 py-0.5 bg-white border border-neutral-200 rounded text-neutral-600">
                      {k}: {typeof v === 'number' ? v.toFixed(2) : v}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Mode gate */}
          {step.step === 'MODE_GATE' && d.mode && (
            <div className="text-[12px] text-neutral-600">
              Mode: <span className="font-semibold">{d.mode}</span> → <span className="font-semibold">{d.action}</span>
            </div>
          )}

          {/* Risk rejected */}
          {step.step === 'RISK_REJECTED' && d.reason && (
            <div className="bg-red-50 rounded-md p-2.5 text-[12px] text-red-700 font-medium">
              {d.reason}
            </div>
          )}

          {/* Execution */}
          {step.step === 'EXECUTION' && (
            <div className="bg-neutral-50 rounded-md p-2.5 text-[11px] text-neutral-600">
              {d.job_id && <div>Job: <span className="font-mono">{d.job_id}</span></div>}
              {d.ok != null && <div>Status: <span className={d.ok ? 'text-green-600 font-semibold' : 'text-red-600'}>{d.ok ? 'QUEUED' : 'FAILED'}</span></div>}
            </div>
          )}

          {/* Pending / Operator created: show decision_id */}
          {(step.step === 'PENDING_CREATED' || step.step === 'OPERATOR_CREATED') && d.decision_id && (
            <div className="text-[11px] text-neutral-500">
              Decision: <span className="font-mono text-neutral-700">{d.decision_id}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Full Timeline View ──────────────────────────────────────
export default function DecisionTimeline({ trace, onBack }) {
  if (!trace) return null;

  const sb = STATUS_BADGE[trace.final_status] || STATUS_BADGE.PENDING;

  return (
    <div className="h-full bg-white overflow-y-auto" style={{ fontFamily: 'Gilroy, sans-serif' }} data-testid="decision-timeline">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white border-b border-neutral-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button 
              onClick={onBack}
              className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-400 transition-colors"
              data-testid="timeline-back-btn"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${trace.side === 'BUY' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {trace.side}
                </span>
                <span className="text-[16px] font-bold text-neutral-900">{trace.symbol}</span>
                <span
                  className="text-[11px] font-bold px-2.5 py-0.5 rounded"
                  style={{ background: sb.bg, color: sb.text, border: `1px solid ${sb.border}` }}
                >
                  {sb.label}
                </span>
              </div>
              <div className="text-[11px] text-neutral-400 mt-0.5">
                {trace.trace_id} · {trace.source} · {trace.duration_ms}ms
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-neutral-400">
            <Clock size={13} />
            {new Date(trace.started_at).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Timeline body */}
      <div className="p-6 max-w-2xl mx-auto">
        {trace.steps.map((step, i) => (
          <TimelineNode key={i} step={step} isLast={i === trace.steps.length - 1} />
        ))}

        {/* Final outcome */}
        {trace.final_reason && (
          <div className="mt-4 p-3 rounded-lg text-[12px] text-neutral-500 italic" style={{ background: sb.bg, border: `1px solid ${sb.border}` }}>
            {trace.final_reason}
          </div>
        )}
      </div>
    </div>
  );
}
