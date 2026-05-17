/**
 * P5.2 — Health Tab (Light Theme)
 * 
 * Model health monitoring for BTC/SPX/DXY/CROSS_ASSET.
 * Shows grade badges, metrics, and action buttons.
 * 
 * v2.0: Added Rollback UI with CRITICAL guard
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const SCOPES = ['BTC', 'SPX', 'DXY', 'CROSS_ASSET'];

/**
 * Rollback Confirmation Modal
 */
function RollbackModal({ scope, currentVersion, previousVersion, onConfirm, onCancel, loading }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4" data-testid="rollback-modal">
        <div className="px-4 py-3 bg-red-600 rounded-t-lg">
          <h3 className="font-bold text-white flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Rollback {scope} Model
          </h3>
        </div>
        
        <div className="p-4">
          <p className="text-gray-600 mb-4">
            You are about to rollback the <strong>{scope}</strong> model to a previous stable version.
          </p>
          
          <div className="bg-gray-50 rounded-lg p-3 mb-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Current Version:</span>
              <span className="font-mono text-red-600">{currentVersion || 'Unknown'}</span>
            </div>
            <div className="flex items-center justify-center">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Previous Version:</span>
              <span className="font-mono text-green-600">{previousVersion || 'Unknown'}</span>
            </div>
          </div>
          
          <div className="bg-amber-50 rounded-lg p-3 mb-4 text-sm text-amber-700">
            <strong>This action will:</strong>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>Change active model version</li>
              <li>Restore previous runtime config</li>
              <li>Affect new forecasts immediately</li>
            </ul>
            <p className="mt-2 text-xs">Existing snapshots and outcomes will NOT be deleted.</p>
          </div>
        </div>
        
        <div className="px-4 py-3 bg-gray-50 rounded-b-lg flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors disabled:opacity-50"
            data-testid="rollback-cancel-btn"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50"
            data-testid="rollback-confirm-btn"
          >
            {loading ? (
              <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" />
              </svg>
            )}
            Confirm Rollback
          </button>
        </div>
      </div>
    </div>
  );
}

function GradeBadge({ grade }) {
  const colors = {
    HEALTHY: 'bg-green-100 text-green-700',
    DEGRADED: 'bg-amber-100 text-amber-700',
    CRITICAL: 'bg-red-100 text-red-700',
  };
  
  const icons = {
    HEALTHY: '✓',
    DEGRADED: '⚠',
    CRITICAL: '✗',
  };
  
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1.5 ${colors[grade] || colors.HEALTHY}`}>
      <span>{icons[grade] || '○'}</span>
      {grade || 'UNKNOWN'}
    </span>
  );
}

function MetricBox({ label, value, suffix = '', warning = false }) {
  return (
    <div className={`bg-gray-50 rounded-lg p-3 ${warning ? 'ring-1 ring-amber-200' : ''}`}>
      <div className="text-xs text-gray-500 uppercase mb-1">{label}</div>
      <div className={`text-lg font-semibold ${warning ? 'text-amber-600' : 'text-gray-900'}`}>
        {typeof value === 'number' ? value.toFixed(2) : (value ?? '—')}{suffix}
      </div>
    </div>
  );
}

function ScopeCard({ scope, health, onRecompute, onResolve, onRollback, rollbackInfo, loading }) {
  const [expanded, setExpanded] = useState(false);
  const metrics = health?.metrics || {};
  
  if (!health) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-gray-900">{scope}</h3>
          <span className="text-sm text-gray-400">Нет данных</span>
        </div>
        <p className="text-sm text-gray-500">Запустите проверку для расчёта метрик</p>
      </div>
    );
  }
  
  const canRollback = rollbackInfo?.canRollback && rollbackInfo?.rollbackAllowed;
  const hasRollbackOption = rollbackInfo?.canRollback;
  
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden" data-testid={`health-card-${scope}`}>
      {/* Header */}
      <div 
        className="px-4 py-3 bg-slate-900 flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <h3 className="font-bold text-white">{scope}</h3>
          <GradeBadge grade={health.grade} />
        </div>
        <svg 
          className={`w-5 h-5 text-white transition-transform ${expanded ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
      
      {/* Quick metrics */}
      <div className="p-4 grid grid-cols-3 gap-3">
        <MetricBox 
          label="Hit Rate" 
          value={(metrics.hitRate * 100)} 
          suffix="%" 
          warning={metrics.hitRate < 0.45}
        />
        <MetricBox 
          label="Avg Abs Error" 
          value={metrics.avgAbsError} 
          suffix="%" 
          warning={metrics.avgAbsError > 5}
        />
        <MetricBox 
          label="Samples" 
          value={metrics.sampleCount || 0} 
        />
      </div>
      
      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-200 p-4 bg-gray-50">
          {/* Active Version */}
          <div className="mb-4">
            <div className="text-xs text-gray-500 uppercase mb-1">Active Version</div>
            <div className="text-sm font-mono text-gray-700">{health.activeVersionId || 'N/A'}</div>
          </div>
          
          {/* Additional metrics */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <MetricBox label="Avg Error" value={metrics.avgError} suffix="%" />
            <MetricBox label="P50 Error" value={metrics.p50AbsError} suffix="%" />
            <MetricBox label="P90 Error" value={metrics.p90AbsError} suffix="%" />
            <MetricBox label="Consec. Degraded" value={health.consecutiveDegradedWindows || 0} />
          </div>
          
          {/* Reasons */}
          {health.reasons?.length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-gray-500 uppercase mb-2">Reasons</div>
              <ul className="space-y-1">
                {health.reasons.map((reason, i) => (
                  <li key={i} className="text-sm text-gray-600 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Computed At */}
          <div className="mb-4 flex items-center gap-2 text-xs text-gray-400">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Last computed: {health.computedAt ? new Date(health.computedAt).toLocaleString() : 'N/A'}
          </div>
          
          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); onResolve(); }}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
              data-testid={`resolve-btn-${scope}`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              Resolve Now
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onRecompute(scope); }}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300 transition-colors disabled:opacity-50"
              data-testid={`recompute-btn-${scope}`}
            >
              <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Recompute
            </button>
            
            {/* Rollback Button - only shown when CRITICAL and has previous version */}
            {canRollback && (
              <button
                onClick={(e) => { e.stopPropagation(); onRollback(scope); }}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition-colors disabled:opacity-50 animate-pulse"
                data-testid={`rollback-btn-${scope}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" />
                </svg>
                Rollback to Stable
              </button>
            )}
            
            {/* Info if rollback available but not allowed (not CRITICAL) */}
            {hasRollbackOption && !canRollback && health.grade !== 'CRITICAL' && (
              <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-500 rounded text-sm" title="Rollback only available when grade is CRITICAL">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Rollback (CRITICAL only)
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function HealthTab() {
  const [healthStates, setHealthStates] = useState({});
  const [rollbackInfoMap, setRollbackInfoMap] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [toast, setToast] = useState(null);
  
  // Rollback modal state
  const [rollbackModal, setRollbackModal] = useState(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  
  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);
  
  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/health/status`);
      const data = await res.json();
      
      if (data.ok) {
        const statesMap = {};
        (data.states || []).forEach(s => {
          statesMap[s.scope] = s;
        });
        setHealthStates(statesMap);
        setLastUpdate(new Date());
      } else {
        setError(data.error || 'Failed to fetch health');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  // Fetch rollback info for all scopes
  const fetchRollbackInfo = useCallback(async () => {
    const infoMap = {};
    for (const scope of SCOPES) {
      try {
        const asset = scope === 'CROSS_ASSET' ? 'CROSS_ASSET' : scope;
        const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/lifecycle/rollback-info?asset=${asset}`);
        const data = await res.json();
        if (data.ok) {
          infoMap[scope] = data;
        }
      } catch (err) {
        console.error(`Failed to fetch rollback info for ${scope}:`, err);
      }
    }
    setRollbackInfoMap(infoMap);
  }, []);
  
  const recomputeHealth = useCallback(async (scope) => {
    setLoading(true);
    try {
      const url = scope 
        ? `${API_BASE}/api/admin/health/recompute?scope=${scope}`
        : `${API_BASE}/api/admin/health/recompute`;
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      
      if (data.ok) {
        await fetchHealth();
        await fetchRollbackInfo();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchHealth, fetchRollbackInfo]);
  
  const runResolveJob = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/jobs/run?job=resolve_matured`, { method: 'POST' });
      const data = await res.json();
      
      if (data.ok) {
        await fetchHealth();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchHealth]);
  
  const runFullJob = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/jobs/run?job=full`, { method: 'POST' });
      const data = await res.json();
      
      if (data.ok) {
        await fetchHealth();
        await fetchRollbackInfo();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchHealth, fetchRollbackInfo]);
  
  // Open rollback modal
  const handleRollbackClick = useCallback((scope) => {
    const info = rollbackInfoMap[scope];
    if (!info?.canRollback) return;
    
    setRollbackModal({
      scope,
      currentVersion: info.currentVersion,
      previousVersion: info.previousVersion,
    });
  }, [rollbackInfoMap]);
  
  // Execute rollback
  const executeRollback = useCallback(async () => {
    if (!rollbackModal) return;
    
    setRollbackLoading(true);
    try {
      const asset = rollbackModal.scope === 'CROSS_ASSET' ? 'CROSS_ASSET' : rollbackModal.scope;
      const res = await fetch(`${API_BASE}/api/fractal/v2.1/admin/lifecycle/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset,
          user: 'admin-ui',
        }),
      });
      
      const data = await res.json();
      
      if (data.ok) {
        showToast(`Rollback successful! Active version: ${data.toVersion}`, 'success');
        setRollbackModal(null);
        await fetchHealth();
        await fetchRollbackInfo();
      } else {
        showToast(`Rollback failed: ${data.error}`, 'error');
      }
    } catch (err) {
      showToast(`Rollback error: ${err.message}`, 'error');
    } finally {
      setRollbackLoading(false);
    }
  }, [rollbackModal, fetchHealth, fetchRollbackInfo, showToast]);
  
  useEffect(() => {
    fetchHealth();
    fetchRollbackInfo();
  }, [fetchHealth, fetchRollbackInfo]);
  
  const summary = {
    total: Object.keys(healthStates).length,
    healthy: Object.values(healthStates).filter(s => s.grade === 'HEALTHY').length,
    degraded: Object.values(healthStates).filter(s => s.grade === 'DEGRADED').length,
    critical: Object.values(healthStates).filter(s => s.grade === 'CRITICAL').length,
  };
  
  return (
    <div className="space-y-6" data-testid="health-tab">
      {/* Toast notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg ${
          toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
        } text-white flex items-center gap-2`} data-testid="toast">
          {toast.type === 'success' ? (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          {toast.message}
        </div>
      )}
      
      {/* Rollback Modal */}
      {rollbackModal && (
        <RollbackModal
          scope={rollbackModal.scope}
          currentVersion={rollbackModal.currentVersion}
          previousVersion={rollbackModal.previousVersion}
          onConfirm={executeRollback}
          onCancel={() => setRollbackModal(null)}
          loading={rollbackLoading}
        />
      )}
      
      {/* Header Card */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-900 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white">Мониторинг здоровья модели</h3>
            <p className="text-xs text-slate-400">Статус и метрики всех моделей</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={runFullJob}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
              data-testid="run-full-job-btn"
            >
              {loading ? (
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              Run Full Job
            </button>
            <button
              onClick={fetchHealth}
              disabled={loading}
              className="p-2 text-white hover:bg-slate-700 rounded transition-colors disabled:opacity-50"
              title="Refresh"
              data-testid="refresh-health-btn"
            >
              <svg className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
        
        {error && (
          <div className="px-4 py-2 bg-red-50 text-red-600 text-sm">{error}</div>
        )}
        
        {/* Summary */}
        <div className="p-4 grid grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">{summary.total}</div>
            <div className="text-xs text-gray-500 uppercase">Всего Scope</div>
          </div>
          <div className="text-center bg-green-50 rounded-lg p-2">
            <div className="text-2xl font-bold text-green-600">{summary.healthy}</div>
            <div className="text-xs text-green-600 uppercase">Healthy</div>
          </div>
          <div className="text-center bg-amber-50 rounded-lg p-2">
            <div className="text-2xl font-bold text-amber-600">{summary.degraded}</div>
            <div className="text-xs text-amber-600 uppercase">Degraded</div>
          </div>
          <div className="text-center bg-red-50 rounded-lg p-2">
            <div className="text-2xl font-bold text-red-600">{summary.critical}</div>
            <div className="text-xs text-red-600 uppercase">Critical</div>
          </div>
        </div>
        
        {/* Last Update */}
        {lastUpdate && (
          <div className="px-4 pb-3 text-xs text-gray-400 flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Обновлено: {lastUpdate.toLocaleString('ru-RU')}
          </div>
        )}
      </div>
      
      {/* Scope Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SCOPES.map(scope => (
          <ScopeCard
            key={scope}
            scope={scope}
            health={healthStates[scope]}
            onRecompute={recomputeHealth}
            onResolve={runResolveJob}
            onRollback={handleRollbackClick}
            rollbackInfo={rollbackInfoMap[scope]}
            loading={loading}
          />
        ))}
      </div>
    </div>
  );
}

export default HealthTab;
