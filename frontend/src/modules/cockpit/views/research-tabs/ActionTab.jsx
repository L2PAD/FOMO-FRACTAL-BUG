/**
 * ActionTab — "What to do" (renamed Execution)
 * =============================================
 *
 * Reads unified state (decision.bias / tradeability) as ground truth.
 * If decision says LOW tradeability → big honest "WAIT" banner instead
 * of a fake trade plan.
 *
 * Otherwise wraps the existing ExecutionTab (which already consumes the
 * same setupData fields).
 */

import React from 'react';
import styled from 'styled-components';
import { AlertOctagon, Clock, Target } from 'lucide-react';

import ExecutionTab from './ExecutionTab';

const Banner = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: ${(p) => p.$tone === 'wait' ? '#fff7ed'
                    : p.$tone === 'go' ? '#f0fdf4'
                    : '#f8fafc'};
  border: 1px solid ${(p) => p.$tone === 'wait' ? '#fed7aa'
                          : p.$tone === 'go' ? '#bbf7d0'
                          : '#e2e8f0'};
  border-radius: 12px;
  margin-bottom: 12px;

  .icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    background: ${(p) => p.$tone === 'wait' ? '#fff1d6'
                      : p.$tone === 'go' ? '#dcfce7'
                      : '#f1f5f9'};
    color: ${(p) => p.$tone === 'wait' ? '#d97706'
                  : p.$tone === 'go' ? '#16a34a'
                  : '#64748b'};
  }
  .title { font-size: 14px; font-weight: 700; color: #0f172a; }
  .desc  { font-size: 12px; color: #475569; margin-top: 2px; }
`;

const ActionTab = ({ unified, ...executionProps }) => {
  if (!unified) return null;

  const { tradeability, bias, confidence } = unified;

  // Honest "WAIT" banner when ground truth says low.
  const showWait = tradeability === 'low' || (bias === 'neutral' && confidence < 0.4);

  return (
    <div data-testid="action-tab">
      {showWait ? (
        <Banner $tone="wait" data-testid="wait-banner">
          <div className="icon"><Clock size={18} /></div>
          <div>
            <div className="title">
              No actionable setup right now —{' '}
              <span style={{ color: '#d97706' }}>recommended: WAIT</span>
            </div>
            <div className="desc">
              Decision: <strong>{(bias || 'neutral').toUpperCase()}</strong>{' '}
              · Confidence: {Math.round((confidence || 0) * 100)}%{' '}
              · Tradeability: {(tradeability || 'low').toUpperCase()}.
              The system will not fabricate a trade plan when truth is unclear.
            </div>
          </div>
        </Banner>
      ) : (
        <Banner $tone="go" data-testid="go-banner">
          <div className="icon"><Target size={18} /></div>
          <div>
            <div className="title">
              Active setup detected — <span style={{ color: '#16a34a' }}>{(bias || '').toUpperCase()}</span>
            </div>
            <div className="desc">
              Confidence: {Math.round((confidence || 0) * 100)}% · Tradeability: {(tradeability || '—').toUpperCase()}
            </div>
          </div>
        </Banner>
      )}

      <ExecutionTab {...executionProps} />
    </div>
  );
};

export default ActionTab;
