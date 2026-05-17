/**
 * Control Panel - System control status
 * Question: Можно ли торговать сейчас?
 * 
 * UPDATED: Now shows Decision Enforcement Block at the top
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import DecisionEnforcementBlock from './DecisionEnforcementBlock';

export default function ControlPanel({ data, fullData }) {
  if (!data && !fullData) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No control data available
      </div>
    );
  }

  // Extract enforcement data from fullData (if available)
  const showEnforcement = fullData && (fullData.decision_raw || fullData.decision_enforced);

  return (
    <div className="space-y-4">
      {/* Decision Enforcement Block (TOP - most important) */}
      {showEnforcement && (
        <DecisionEnforcementBlock
          decisionRaw={fullData.decision_raw}
          decisionEnforced={fullData.decision_enforced}
          reasonChain={fullData.reason_chain}
          blocked={fullData.blocked}
          blockReason={fullData.block_reason}
          finalAction={fullData.final_action}
          overrides={{
            ...fullData.orchestration?.control?.overrides,
            ...fullData.orchestration?.overrides?.entry_mode_overrides,
          }}
          executionControl={fullData.execution_control}
        />
      )}

      {/* Control Status */}
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
          Control Status
        </h3>
        <div className="space-y-3">
          <GridRow label="System State" value={data?.system_state} />
          <GridRow label="Alpha Mode" value={data?.alpha_mode} />
          <GridRow label="Can Trade" value={data?.can_trade ? 'YES' : 'NO'} />
          <GridRow label="Can Enter" value={data?.can_enter ? 'YES' : 'NO'} />
          <GridRow label="Soft Kill" value={data?.soft_kill ? 'ON' : 'OFF'} />
          <GridRow label="Hard Kill" value={data?.hard_kill ? 'ON' : 'OFF'} />
          <GridRow label="Pending Approvals" value={data?.pending_approvals ?? 0} />
        </div>
      </div>
    </div>
  );
}
