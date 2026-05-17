import IntelligencePanel from './panels/IntelligencePanel';
import { CexLockedPanel } from './panels/CexRoutePanel';

/**
 * MODE_REGISTRY — declarative mode configuration with lifecycle.
 *
 * Each mode defines:
 *   panel      — React component to render
 *   getData    — extracts props from context
 *   title      — display name
 *   hotkey     — keyboard shortcut (uppercase letter)
 *   bypassIntelligence — skip IntelligencePanel rendering
 *   onEnter(ctx)  — called when mode activates
 *   onExit(ctx)   — called when mode deactivates
 *
 * ctx shape: { intelligence, marketContext, expandedWalletSignal, setExpandedWalletSignal, cexFlow }
 *
 * Adding a new mode = 1 entry here + optional panel component.
 */
export const MODE_REGISTRY = {
  smart_money: {
    panel: IntelligencePanel,
    getData: (ctx) => ({
      activeIntelligence: ctx.intelligence.filter(s => s.category === 'smart_money'),
      marketContext: ctx.marketContext,
      expandedWalletSignal: ctx.expandedWalletSignal,
      setExpandedWalletSignal: ctx.setExpandedWalletSignal,
    }),
    title: 'Smart Money',
    hotkey: 'S',
    bypassIntelligence: false,
    onEnter: () => {},
    onExit: (ctx) => { ctx.setExpandedWalletSignal(null); },
  },
  entity: {
    panel: IntelligencePanel,
    getData: (ctx) => ({
      activeIntelligence: ctx.intelligence.filter(s => s.category === 'entity'),
      marketContext: ctx.marketContext,
      expandedWalletSignal: ctx.expandedWalletSignal,
      setExpandedWalletSignal: ctx.setExpandedWalletSignal,
    }),
    title: 'Entity',
    hotkey: 'E',
    bypassIntelligence: false,
    onEnter: () => {},
    onExit: (ctx) => { ctx.setExpandedWalletSignal(null); },
  },
  risk: {
    panel: IntelligencePanel,
    getData: (ctx) => ({
      activeIntelligence: ctx.intelligence.filter(s => s.category === 'risk'),
      marketContext: ctx.marketContext,
      expandedWalletSignal: ctx.expandedWalletSignal,
      setExpandedWalletSignal: ctx.setExpandedWalletSignal,
    }),
    title: 'Risk',
    hotkey: 'R',
    bypassIntelligence: false,
    onEnter: () => {},
    onExit: (ctx) => { ctx.setExpandedWalletSignal(null); },
  },
  token_rotation: {
    panel: IntelligencePanel,
    getData: (ctx) => ({
      activeIntelligence: ctx.intelligence.filter(s => s.category === 'token_flow'),
      marketContext: ctx.marketContext,
      expandedWalletSignal: ctx.expandedWalletSignal,
      setExpandedWalletSignal: ctx.setExpandedWalletSignal,
    }),
    title: 'Token Rotation',
    hotkey: 'T',
    bypassIntelligence: false,
    onEnter: () => {},
    onExit: (ctx) => { ctx.setExpandedWalletSignal(null); },
  },
  cex_flow: {
    panel: CexLockedPanel,
    getData: (ctx) => ctx.cexFlow,
    title: 'CEX Flow',
    hotkey: 'C',
    bypassIntelligence: true,
    onEnter: () => {},
    onExit: () => {},
  },
};

/**
 * Resolve active mode panel and data from registry.
 * Returns null if mode is not registered or has no data.
 */
export function resolveMode(graphMode, ctx) {
  if (!graphMode) return null;
  const config = MODE_REGISTRY[graphMode];
  if (!config) return null;
  const data = config.getData(ctx);
  return { config, data };
}
