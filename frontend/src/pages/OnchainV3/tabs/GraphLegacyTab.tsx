/**
 * Graph Explorer Tab
 * ==================
 * 
 * Full-screen Graph Explorer extracted from FOMO-API repository.
 * Replaces the old Graph Intelligence legacy tab.
 * 
 * Components extracted without modification:
 * - ForceGraphViewer.js (graph engine - DO NOT MODIFY)
 * - GraphExplorer.js (explorer UI)
 * - EntityTrendChart.js (momentum trends)
 */

// @ts-ignore
import GraphExplorer from '../../../components/GraphExplorer';

// Colors matching the dark-themed graph panels
const GRAPH_COLORS = {
  background: '#0f172a',
  surface: '#1e293b',
  border: '#334155',
  text: '#e2e8f0',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  accent: '#6366f1',
  accentSoft: '#312e81',
  accentHover: '#4f46e5',
  success: '#10b981',
  successSoft: '#064e3b',
  warning: '#f59e0b',
  warningSoft: '#78350f',
  error: '#ef4444',
  errorSoft: '#7f1d1d',
  bullish: '#10b981',
  bearish: '#ef4444',
  neutral: '#6b7280',
};

interface Props {
  nav?: any;
  selectedAddress?: string | null;
}

export default function GraphLegacyTab({ nav, selectedAddress }: Props) {
  return (
    <div 
      data-testid="graph-explorer-tab"
      style={{ 
        width: '100%', 
        minHeight: 'calc(100vh - 140px)',
      }}
    >
      <GraphExplorer colors={GRAPH_COLORS} initialNodeId={selectedAddress || null} nav={nav} />
    </div>
  );
}
