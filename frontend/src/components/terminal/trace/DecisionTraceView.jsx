/**
 * Decision Trace View — Sprint 2
 * 
 * Shows the full journey of each decision through the pipeline:
 * Signal → Risk → Mode → R1 → R2 → Safety → Execution → Position
 * 
 * This is the NARRATIVE LAYER — operator sees HOW the system thinks.
 */

import { useState, useEffect, useCallback } from 'react';
import { Activity, CheckCircle, XCircle, Clock, AlertTriangle, TrendingUp, TrendingDown, RefreshCw, Zap, Shield } from 'lucide-react';
// Phase A.3 Step 3 — trace reads on canonical /api/ta/runtime/trace/*.
// Phase A.3 Step 4.1 — daemon/status (read-only) routed through taRuntime.
// Phase A.3 Step 4.2A — daemon/start|stop now via taRuntime.daemon.*.
// Phase A.3 Step 4.3 (approve+reject) — decisions.approve/reject via taRuntime.
import { taRuntime, taTrace } from '../../../modules/ta/services';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STEP_CONFIG = {
  SIGNAL:          { icon: Zap,          color: '#3b82f6', label: 'Signal' },
  RISK_APPROVED:   { icon: CheckCircle,  color: '#22c55e', label: 'Risk OK' },
  RISK_REJECTED:   { icon: XCircle,      color: '#ef4444', label: 'Risk Rejected' },
  MODE_GATE:       { icon: Shield,       color: '#a855f7', label: 'Mode Gate' },
  R1_SIZING:       { icon: TrendingUp,   color: '#06b6d4', label: 'R1 Sizing' },
  R2_ADAPTIVE:     { icon: TrendingDown, color: '#f59e0b', label: 'R2 Adaptive' },
  SAFETY:          { icon: Shield,       color: '#22c55e', label: 'Safety' },
  EXECUTION:       { icon: Activity,     color: '#10b981', label: 'Execution' },
  PENDING_CREATED: { icon: Clock,        color: '#eab308', label: 'Pending' },
  OPERATOR_CREATED:{ icon: Zap,          color: '#f59e0b', label: 'Operator Created' },
};

const STATUS_COLORS = {
  EXECUTED: '#22c55e',
  PENDING:  '#eab308',
  REJECTED: '#ef4444',
  BLOCKED:  '#f97316',
  IN_PROGRESS: '#6b7280',
};

function TraceStep({ step, isLast }) {
  const config = STEP_CONFIG[step.step] || { icon: Activity, color: '#6b7280', label: step.step };
  const Icon = config.icon;
  const data = step.data || {};

  return (
    <div className="flex items-start gap-3" data-testid={`trace-step-${step.step.toLowerCase()}`}>
      <div className="flex flex-col items-center">
        <div 
          className="w-8 h-8 rounded-full flex items-center justify-center"
          style={{ backgroundColor: `${config.color}20`, color: config.color }}
        >
          <Icon size={16} />
        </div>
        {!isLast && <div className="w-px h-6 bg-gray-700 mt-1" />}
      </div>
      <div className="flex-1 pb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">{config.label}</span>
          <span className="text-xs text-gray-500">{new Date(step.timestamp).toLocaleTimeString()}</span>
        </div>
        <div className="text-xs text-gray-400 mt-1 space-y-0.5">
          {data.confidence && <div>Confidence: <span className="text-gray-300">{(data.confidence * 100).toFixed(1)}%</span></div>}
          {data.strategy && <div>Strategy: <span className="text-gray-300">{data.strategy}</span></div>}
          {data.entry_price && <div>Entry: <span className="text-green-400">${data.entry_price.toLocaleString()}</span></div>}
          {data.stop_price && <div>Stop: <span className="text-red-400">${data.stop_price.toLocaleString()}</span></div>}
          {data.target_price && <div>Target: <span className="text-blue-400">${data.target_price.toLocaleString()}</span></div>}
          {data.qty && <div>Qty: <span className="text-gray-300">{data.qty}</span></div>}
          {data.r2_multiplier && <div>R2: <span className="text-yellow-400">×{data.r2_multiplier.toFixed(2)}</span></div>}
          {data.reason && <div>Reason: <span className="text-red-400">{data.reason}</span></div>}
          {data.mode && <div>Mode: <span className="text-gray-300">{data.mode}</span> → {data.action}</div>}
          {data.decision_id && <div>Decision: <span className="text-gray-300 font-mono text-xs">{data.decision_id}</span></div>}
        </div>
      </div>
    </div>
  );
}

function TraceCard({ trace, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const statusColor = STATUS_COLORS[trace.final_status] || '#6b7280';
  const isPending = trace.final_status === 'PENDING';
  
  // Extract decision_id from PENDING_CREATED or OPERATOR_CREATED step
  const pendingStep = trace.steps?.find(s => 
    s.step === 'PENDING_CREATED' || s.step === 'OPERATOR_CREATED'
  );
  const decisionId = pendingStep?.data?.decision_id;
  
  const handleApprove = async (e) => {
    e.stopPropagation();
    if (!decisionId) return;
    setActionLoading(true);
    try {
      await onApprove(decisionId, trace.trace_id);
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleReject = async (e) => {
    e.stopPropagation();
    if (!decisionId) return;
    setActionLoading(true);
    try {
      await onReject(decisionId, trace.trace_id);
    } finally {
      setActionLoading(false);
    }
  };
  
  return (
    <div 
      className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden cursor-pointer hover:border-gray-600 transition-colors"
      onClick={() => setExpanded(!expanded)}
      data-testid={`trace-card-${trace.trace_id}`}
    >
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className={`px-2 py-1 rounded text-xs font-bold ${trace.side === 'BUY' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
            {trace.side}
          </div>
          <span className="text-gray-200 font-medium">{trace.symbol}</span>
          <span className="text-gray-500 text-xs">{trace.steps_count} steps</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{trace.duration_ms}ms</span>
          <span 
            className="px-2 py-0.5 rounded text-xs font-bold"
            style={{ backgroundColor: `${statusColor}20`, color: statusColor }}
          >
            {trace.final_status}
          </span>
        </div>
      </div>
      
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-700/50 pt-3">
          {trace.steps.map((step, i) => (
            <TraceStep key={i} step={step} isLast={i === trace.steps.length - 1 && !isPending} />
          ))}
          {trace.final_reason && (
            <div className="text-xs text-gray-500 mt-2 italic">
              Final: {trace.final_reason}
            </div>
          )}
          
          {/* Sprint 3: Operator Approval buttons for PENDING decisions */}
          {isPending && decisionId && (
            <div className="mt-3 pt-3 border-t border-gray-700/50 flex items-center gap-3" data-testid="operator-approval-panel">
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-green-600/20 border border-green-600/40 text-green-400 hover:bg-green-600/30 transition-colors font-medium text-sm disabled:opacity-50"
                data-testid="approve-decision-btn"
              >
                <CheckCircle size={16} />
                {actionLoading ? 'Executing...' : 'APPROVE & EXECUTE'}
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-600/20 border border-red-600/40 text-red-400 hover:bg-red-600/30 transition-colors font-medium text-sm disabled:opacity-50"
                data-testid="reject-decision-btn"
              >
                <XCircle size={16} />
                {actionLoading ? 'Rejecting...' : 'REJECT'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TraceStats({ stats }) {
  if (!stats) return null;
  
  return (
    <div className="grid grid-cols-5 gap-3 mb-4" data-testid="trace-stats">
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-center">
        <div className="text-lg font-bold text-gray-200">{stats.total_traces}</div>
        <div className="text-xs text-gray-500">Total</div>
      </div>
      <div className="bg-gray-800/50 border border-green-900/50 rounded-lg p-3 text-center">
        <div className="text-lg font-bold text-green-400">{stats.executed}</div>
        <div className="text-xs text-gray-500">Executed</div>
      </div>
      <div className="bg-gray-800/50 border border-yellow-900/50 rounded-lg p-3 text-center">
        <div className="text-lg font-bold text-yellow-400">{stats.pending}</div>
        <div className="text-xs text-gray-500">Pending</div>
      </div>
      <div className="bg-gray-800/50 border border-red-900/50 rounded-lg p-3 text-center">
        <div className="text-lg font-bold text-red-400">{stats.rejected}</div>
        <div className="text-xs text-gray-500">Rejected</div>
      </div>
      <div className="bg-gray-800/50 border border-blue-900/50 rounded-lg p-3 text-center">
        <div className="text-lg font-bold text-blue-400">{stats.pass_rate}%</div>
        <div className="text-xs text-gray-500">Pass Rate</div>
      </div>
    </div>
  );
}

export default function DecisionTraceView() {
  const [traces, setTraces] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daemonStatus, setDaemonStatus] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [tracesRes, statsRes, daemonRes] = await Promise.all([
        // trace/* migrated to canonical /api/ta/runtime/trace/*
        taTrace.getLatest({ limit: 20 }),
        taTrace.getStats(),
        // daemon/status (read-only) → canonical /api/ta/runtime/daemon/status.
        taRuntime.daemon.getStatus(),
      ]);
      setTraces(tracesRes.traces || []);
      setStats(statsRes);
      setDaemonStatus(daemonRes);
    } catch (err) {
      console.error('Failed to load traces:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleDaemon = async () => {
    // Step 4.2A: canonical /api/ta/runtime/daemon/{start|stop} via taRuntime.
    // No fall-through to legacy — backend alias proxies byte-identically.
    if (daemonStatus?.is_running) {
      await taRuntime.daemon.stop();
    } else {
      await taRuntime.daemon.start();
    }
    fetchData();
  };

  // Sprint 3: Operator Approval
  // Step 4.3 (approve): canonical /api/ta/runtime/decisions/{id}/approve.
  // Reject still on legacy until next sub-step. DO NOT migrate it here.
  const handleApprove = async (decisionId) => {
    try {
      const data = await taRuntime.decisions.approve(decisionId);
      if (data.ok) {
        fetchData(); // Refresh traces
      }
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  const handleReject = async (decisionId) => {
    try {
      // Step 4.3 (reject): canonical /api/ta/runtime/decisions/{id}/reject.
      // Payload preserved byte-identically: { reason: 'OPERATOR_REJECTED' }.
      const data = await taRuntime.decisions.reject(decisionId, 'OPERATOR_REJECTED');
      if (data.ok) {
        fetchData(); // Refresh traces
      }
    } catch (err) {
      console.error('Reject failed:', err);
    }
  };

  return (
    <div className="space-y-4" data-testid="decision-trace-view">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-blue-400" />
          <h3 className="text-lg font-semibold text-gray-200">Decision Trace</h3>
          <span className="text-xs text-gray-500">Live decision narrative</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleDaemon}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              daemonStatus?.is_running 
                ? 'bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-800' 
                : 'bg-green-900/30 text-green-400 hover:bg-green-900/50 border border-green-800'
            }`}
            data-testid="daemon-toggle-btn"
          >
            {daemonStatus?.is_running ? '■ Stop Daemon' : '▶ Start Daemon'}
          </button>
          <button onClick={fetchData} className="p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-400" data-testid="refresh-traces-btn">
            <RefreshCw size={14} />
          </button>
          {daemonStatus?.is_running && (
            <span className="text-xs text-green-400 animate-pulse">● LIVE ({daemonStatus.cycles_count} cycles)</span>
          )}
        </div>
      </div>

      <TraceStats stats={stats} />

      {loading ? (
        <div className="text-gray-500 text-center py-8">Loading traces...</div>
      ) : traces.length === 0 ? (
        <div className="text-gray-500 text-center py-8 bg-gray-800/30 rounded-lg border border-gray-700">
          No decision traces yet. Start the daemon or run a manual cycle.
        </div>
      ) : (
        <div className="space-y-2">
          {traces.map(trace => (
            <TraceCard key={trace.trace_id} trace={trace} onApprove={handleApprove} onReject={handleReject} />
          ))}
        </div>
      )}
    </div>
  );
}
