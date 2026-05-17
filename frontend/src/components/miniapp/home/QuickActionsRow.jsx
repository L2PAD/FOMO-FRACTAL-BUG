import { motion } from 'framer-motion';
import { HelpCircle, Activity, TrendingUp, Bell } from 'lucide-react';
import { useMiniApp } from '../../../context/MiniAppContext';

export function QuickActionsRow() {
  const { setActiveTab, trackEvent } = useMiniApp();

  const scrollToWhy = () => {
    const el = document.querySelector('[data-testid="why-block"]');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const btn = el.querySelector('[data-testid="why-toggle"]');
      if (btn) setTimeout(() => btn.click(), 400);
    }
  };

  const actions = [
    { id: 'why', label: 'Why', Icon: HelpCircle, onClick: scrollToWhy },
    { id: 'feed', label: 'Feed', Icon: Activity, onClick: () => setActiveTab('feed') },
    { id: 'edge', label: 'Edge', Icon: TrendingUp, onClick: () => { trackEvent('edge_viewed', { source: 'quick_action' }); setActiveTab('polymarket'); } },
    { id: 'alerts', label: 'Alerts', Icon: Bell, onClick: () => setActiveTab('feed') },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.55 }}
      data-testid="quick-actions"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr 1fr',
        gap: '8px',
        margin: '12px 16px 0',
      }}
    >
      {actions.map(({ id, label, Icon, onClick }) => (
        <motion.button
          key={id}
          data-testid={`action-${id}`}
          whileTap={{ scale: 0.94 }}
          onClick={onClick}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '6px',
            padding: '14px 8px',
            background: 'var(--ma-surface)',
            border: '1px solid var(--ma-border)',
            borderRadius: '14px',
            cursor: 'pointer',
          }}
        >
          <Icon size={18} color="var(--ma-secondary)" strokeWidth={1.5} />
          <span style={{
            fontSize: '11px',
            fontWeight: 600,
            color: 'var(--ma-secondary)',
            fontFamily: "'Manrope', sans-serif",
            letterSpacing: '0.05em',
          }}>
            {label}
          </span>
        </motion.button>
      ))}
    </motion.div>
  );
}
