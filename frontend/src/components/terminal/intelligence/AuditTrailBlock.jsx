import React, { useState, useEffect } from 'react';
import { FileText, TrendingUp, Zap, Brain } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const AuditTrailBlock = () => {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch audit summary
  const loadAudit = async () => {
    try {
      const [execRes, decRes, stratRes, learnRes] = await Promise.all([
        fetch(`${API_URL}/api/audit/execution?limit=1`),
        fetch(`${API_URL}/api/audit/decisions?limit=1`),
        fetch(`${API_URL}/api/audit/strategies?limit=1`),
        fetch(`${API_URL}/api/audit/learning?limit=1`)
      ]);

      const exec = await execRes.json();
      const dec = await decRes.json();
      const strat = await stratRes.json();
      const learn = await learnRes.json();

      setAudit({
        last_execution: exec.execution_events?.[0] || null,
        last_decision: dec.decisions?.[0] || null,
        last_strategy: strat.strategy_actions?.[0] || null,
        last_learning: learn.learning_cycles?.[0] || null
      });
      setLoading(false);
    } catch (error) {
      console.error('Audit trail error:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudit();
    const interval = setInterval(loadAudit, 5000);  // Refresh every 5 sec
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="audit-trail-block">
        <div className="text-sm text-gray-500">Loading audit trail...</div>
      </div>
    );
  }

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="audit-trail-block">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-medium text-gray-300">Audit Trail (P0.7)</span>
      </div>

      {/* Audit Items Grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Last Decision */}
        <div className="bg-[#0F141A] border border-gray-800 rounded p-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-xs text-gray-500">Last Decision</span>
          </div>
          {audit?.last_decision ? (
            <div className="space-y-1">
              <div className={`text-sm font-medium ${
                audit.last_decision.blocked ? 'text-red-400' : 'text-green-400'
              }`}>
                {audit.last_decision.final_action || 'ALLOW'}
              </div>
              <div className="text-xs text-gray-500">
                {audit.last_decision.symbol || '-'}
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-600">No decisions yet</div>
          )}
        </div>

        {/* Last Strategy Action */}
        <div className="bg-[#0F141A] border border-gray-800 rounded p-3">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-xs text-gray-500">Last Strategy</span>
          </div>
          {audit?.last_strategy ? (
            <div className="space-y-1">
              <div className="text-sm font-medium text-amber-400">
                {audit.last_strategy.action_type?.replace(/_/g, ' ') || '-'}
              </div>
              <div className="text-xs text-gray-500">
                {audit.last_strategy.strategy_id || '-'}
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-600">No strategy actions yet</div>
          )}
        </div>

        {/* Last Execution Event */}
        <div className="bg-[#0F141A] border border-gray-800 rounded p-3">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-xs text-gray-500">Last Execution</span>
          </div>
          {audit?.last_execution ? (
            <div className="space-y-1">
              <div className={`text-sm font-medium ${
                audit.last_execution.event_type === 'ORDER_REJECTED' ? 'text-red-400' :
                audit.last_execution.event_type === 'ORDER_FILL_RECORDED' ? 'text-green-400' :
                'text-blue-400'
              }`}>
                {audit.last_execution.event_type?.replace(/_/g, ' ') || '-'}
              </div>
              <div className="text-xs text-gray-500">
                {audit.last_execution.symbol || '-'}
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-600">No execution events yet</div>
          )}
        </div>

        {/* Last Learning Action */}
        <div className="bg-[#0F141A] border border-gray-800 rounded p-3">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-3.5 h-3.5 text-green-400" />
            <span className="text-xs text-gray-500">Last Learning</span>
          </div>
          {audit?.last_learning ? (
            <div className="space-y-1">
              <div className="text-sm font-medium text-green-400">
                {audit.last_learning.actions_applied?.length || 0} actions
              </div>
              <div className="text-xs text-gray-500">
                {audit.last_learning.actions_applied?.[0] || '-'}
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-600">No learning cycles yet</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuditTrailBlock;
