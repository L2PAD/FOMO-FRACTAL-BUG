import { motion } from 'framer-motion';
import { useMiniApp } from '../../../context/MiniAppContext';
import { SearchBar } from './SearchBar';
import { AssetTabs } from './AssetTabs';
import { DecisionHeroCard } from './DecisionHeroCard';
import { ActionPlanCard } from './ActionPlanCard';
import { MarketStoryCard } from './MarketStoryCard';
import { StructureSnapshot } from './StructureSnapshot';
import { SignalPressureCard } from './SignalPressureCard';
import { WhyBlock } from './WhyBlock';
import { DecisionTimeline } from './DecisionTimeline';
import { QuickActionsRow } from './QuickActionsRow';

export function HomeScreen() {
  const { homeData, homeLoading } = useMiniApp();

  return (
    <div data-testid="home-screen" style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
      <SearchBar />
      <AssetTabs />

      {homeLoading && !homeData ? (
        <LoadingPulse />
      ) : homeData ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <DecisionHeroCard data={homeData} />
          <ActionPlanCard actionPlan={homeData.actionPlan} decision={homeData.decision} />
          <DecisionTimeline timeline={homeData.timeline} />
          <MarketStoryCard marketStory={homeData.marketStory} />
          <StructureSnapshot structure={homeData.structure} />
          <SignalPressureCard pressure={homeData.pressure} />
          <WhyBlock reasons={homeData.why} />
          <QuickActionsRow />
          {homeData.alertsPreview && homeData.alertsPreview.length > 0 && (
            <AlertsPreview alerts={homeData.alertsPreview} />
          )}
          <div style={{ height: '16px' }} />
        </motion.div>
      ) : null}
    </div>
  );
}


function AlertsPreview({ alerts }) {
  const IMPACT_COLORS = { HIGH: '#f87171', MED: '#facc15', LOW: '#a1a1aa' };
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.65 }}
      data-testid="alerts-preview"
      style={{
        margin: '10px 16px 0',
        padding: '14px 16px',
        background: 'var(--ma-surface, #18181b)',
        borderRadius: '16px',
        border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      <div style={{
        fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
        color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        marginBottom: '8px',
      }}>
        Latest Signals
      </div>
      {alerts.map((a, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '7px 0',
          borderBottom: i < alerts.length - 1 ? '1px solid var(--ma-divider, var(--ma-border))' : 'none',
        }}>
          <span style={{
            fontSize: '9px', fontWeight: 700,
            color: IMPACT_COLORS[a.impact] || '#a1a1aa',
            fontFamily: "'JetBrains Mono', monospace",
            background: `${IMPACT_COLORS[a.impact] || '#a1a1aa'}18`,
            padding: '2px 6px', borderRadius: '20px', flexShrink: 0,
          }}>
            {a.impact}
          </span>
          <span style={{
            flex: 1, fontSize: '12px', color: 'var(--ma-secondary)',
            fontFamily: "'Manrope', sans-serif",
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {a.text}
          </span>
        </div>
      ))}
    </motion.div>
  );
}


function LoadingPulse() {
  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {[160, 100, 120, 140, 80].map((_, i) => (
        <div key={i} style={{
          height: i === 0 ? '180px' : '80px',
          background: 'var(--ma-surface, #18181b)', borderRadius: '16px',
          animation: 'pulse 1.5s ease infinite',
        }} />
      ))}
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
