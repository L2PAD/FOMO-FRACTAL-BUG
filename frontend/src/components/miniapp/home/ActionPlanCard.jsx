import { motion } from 'framer-motion';
import { Target } from 'lucide-react';

export function ActionPlanCard({ actionPlan, decision }) {
  if (!actionPlan) return null;

  const isBuy = decision?.action === 'BUY';
  const isSell = decision?.action === 'SELL';
  const accentColor = isBuy ? '#34d399' : isSell ? '#f87171' : '#facc15';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.15 }}
      data-testid="action-plan-card"
      style={{
        margin: '10px 16px 0',
        padding: '14px 16px',
        background: 'var(--ma-surface)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Target size={14} color={accentColor} strokeWidth={2} />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Action Plan
        </span>
      </div>

      <div data-testid="plan-summary" style={{
        fontSize: '15px', fontWeight: 700, color: accentColor,
        fontFamily: "'Manrope', sans-serif", marginBottom: '10px',
      }}>
        {actionPlan.summary}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {actionPlan.entryZone && (
          <PlanRow label="Entry Zone" value={actionPlan.entryZone} />
        )}
        {actionPlan.invalidation && (
          <PlanRow label="Invalidation" value={actionPlan.invalidation} color="#f87171" />
        )}
        {actionPlan.nextTrigger && (
          <PlanRow label="Next Trigger" value={actionPlan.nextTrigger} testId="plan-trigger" />
        )}
      </div>

      {actionPlan.comment && (
        <div style={{
          marginTop: '10px', paddingTop: '10px',
          borderTop: '1px solid var(--ma-divider, var(--ma-border))',
          fontSize: '12px', color: 'var(--ma-muted)',
          fontFamily: "'Manrope', sans-serif", fontStyle: 'italic',
        }}>
          {actionPlan.comment}
        </div>
      )}
    </motion.div>
  );
}

function PlanRow({ label, value, color, testId }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }} data-testid={testId}>
      <span style={{
        fontSize: '11px', fontWeight: 600, color: 'var(--ma-muted)',
        fontFamily: "'Manrope', sans-serif", letterSpacing: '0.05em',
      }}>
        {label}
      </span>
      <span style={{
        fontSize: '12px', fontWeight: 700, color: color || 'var(--ma-text)',
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        {value}
      </span>
    </div>
  );
}
