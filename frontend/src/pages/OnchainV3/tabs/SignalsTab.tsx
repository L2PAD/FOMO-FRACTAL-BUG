/**
 * Signals Tab — On-chain v3
 * ==========================
 * 
 * PHASE 3: Signal Center
 * STEP 3: Strong-only filter + confidence-based dimming
 */

import React, { useState, useEffect, useCallback, useMemo, Suspense, lazy } from 'react';
import { 
  RefreshCw, 
  Loader2, 
  AlertTriangle,
  Clock,
  Database,
  Cpu,
  CheckCircle,
  XCircle,
  BarChart2,
  Filter,
  Eye,
  EyeOff,
  X,
  User,
  Zap,
  Radio
} from 'lucide-react';
import { useOnchainChain } from '../context/OnchainChainContext';
import { 
  fetchAltFlow, 
  fetchAltFlowJobStatus,
  refreshAltFlow,
  type AltFlowResponse,
  type AltFlowItem,
  type AltFlowJobStatus
} from '../api';
import { AltFlowTable, AltFlowDetailsDrawer } from '../components';
import LegacyTabWrapper from '../components/LegacyTabWrapper';
import { SignalsDeviationsMode } from './SignalsDeviationsTab';
import { DataStatusBanner, computeSignalsStatus } from '../components/DataStatusBanner';

// Lazy load D1 Live Signals
// @ts-ignore
const SignalsPageD1 = lazy(() => import('../../SignalsPageD1'));

type TimeWindow = '24h' | '7d';

// STEP 3: Confidence threshold for "strong" signals
const CONF_STRONG = 0.55;

// =====================
// P0.7: Entity Filter Pill
// =====================

interface EntityFilterPillProps {
  entityId: string;
  onClear: () => void;
}

function EntityFilterPill({ entityId, onClear }: EntityFilterPillProps) {
  // Format display name
  const displayName = entityId.startsWith('0x') 
    ? `${entityId.slice(0, 6)}...${entityId.slice(-4)}`
    : entityId.replace(/:unknown$/, ' (unknown)').replace(/:/g, ' ');
  
  return (
    <div 
      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-50"
      data-testid="entity-filter-pill"
    >
      <User className="w-4 h-4 text-purple-600" />
      <span className="text-sm text-purple-700">
        Filtered by: <span className="font-bold">{displayName}</span>
      </span>
      <button
        onClick={onClear}
        className="ml-2 p-1 rounded-full hover:bg-purple-100 transition-colors"
        data-testid="clear-entity-filter"
      >
        <X className="w-4 h-4 text-purple-600" />
      </button>
    </div>
  );
}

// =====================
// Status Bar
// =====================

interface StatusBarProps {
  data: AltFlowResponse | null;
  jobStatus: AltFlowJobStatus | null;
  loading: boolean;
  strongOnly: boolean;
  onToggleStrong: () => void;
  strongCount: number;
  totalCount: number;
}

function StatusBar({ data, jobStatus, loading, strongOnly, onToggleStrong, strongCount, totalCount }: StatusBarProps) {
  const updatedAgo = data?.updatedAt 
    ? Math.round((Date.now() - data.updatedAt) / 60000) 
    : null;
  
  const job = jobStatus?.job;
  const isDemo = data?.isDemo;

  return (
    <div className="flex items-center gap-4 text-sm text-gray-500 flex-wrap">
      {/* Demo Mode Indicator */}
      {isDemo && (
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span className="text-amber-600 font-medium">DEMO DATA</span>
        </div>
      )}
      
      {/* Strong Only Toggle */}
      <button
        onClick={onToggleStrong}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
          strongOnly 
            ? 'bg-blue-50 text-blue-700' 
            : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
        }`}
        data-testid="strong-only-toggle"
      >
        {strongOnly ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
        <span className="font-medium">
          {strongOnly ? 'Strong Only' : 'Show All'}
        </span>
        <span className="text-xs opacity-70">
          ({strongCount}/{totalCount})
        </span>
      </button>
      
      {/* Coverage */}
      <div className="flex items-center gap-2">
        <Database className="w-4 h-4" />
        <span>
          <span className="text-gray-700 font-medium">{data?.meta?.tokenCount ?? 0}</span> tokens
        </span>
      </div>
      
      {/* Avg Confidence */}
      <div className="flex items-center gap-2">
        <BarChart2 className="w-4 h-4" />
        <span>
          Avg: <span className="text-gray-700 font-medium">{Math.round((data?.meta?.confidence ?? 0) * 100)}%</span>
        </span>
      </div>
      
      {/* Updated */}
      <div className="flex items-center gap-2">
        <Clock className="w-4 h-4" />
        <span>
          {updatedAgo !== null ? (
            <span className={updatedAgo > 15 ? 'text-amber-500 font-medium' : 'text-gray-700'}>
              {updatedAgo}m ago
            </span>
          ) : (
            <span className="text-gray-400">—</span>
          )}
        </span>
      </div>
      
      {/* Job Status */}
      <div className="flex items-center gap-1.5">
        <Cpu className="w-4 h-4" />
        {job ? (
          job.running ? (
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle className="w-3.5 h-3.5" />
              Live
            </span>
          ) : (
            <span className="text-gray-500">Idle</span>
          )
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </div>
      
      {loading && (
        <Loader2 className="w-4 h-4 animate-spin text-blue-500 ml-auto" />
      )}
    </div>
  );
}

// =====================
// Main Component
// =====================

interface SignalsTabProps {
  externalEntity?: string | null;
  onEntityConsumed?: () => void;
}

export function SignalsTab(props?: SignalsTabProps) {
  const { chainId } = useOnchainChain();
  const [mode, setMode] = useState<'flow' | 'live' | 'deviations'>('flow');
  const [timeframe, setTimeframe] = useState<TimeWindow>('24h');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // STEP 3: Strong-only filter (default ON)
  const [strongOnly, setStrongOnly] = useState(true);
  
  // PHASE 5.3: Entity filter from URL
  const [entityFilter, setEntityFilter] = useState<string | null>(null);
  
  // Data state
  const [data, setData] = useState<AltFlowResponse | null>(null);
  const [jobStatus, setJobStatus] = useState<AltFlowJobStatus | null>(null);
  
  // Drawer state
  const [selectedItem, setSelectedItem] = useState<AltFlowItem | null>(null);
  
  // Handle external entity from URL (PHASE 5.3)
  useEffect(() => {
    if (props?.externalEntity) {
      setEntityFilter(props.externalEntity);
      props.onEntityConsumed?.();
    }
  }, [props?.externalEntity]);

  const fetchData = useCallback(async (showRefresh = false) => {
    try {
      if (showRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      
      const [flowData, status] = await Promise.all([
        fetchAltFlow(timeframe, entityFilter || undefined, chainId),
        fetchAltFlowJobStatus(),
      ]);
      
      setData(flowData);
      setJobStatus(status);
    } catch (err) {
      console.error('[SignalsTab] Error fetching data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load signals');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [timeframe, entityFilter, chainId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshAltFlow(timeframe);
      await fetchData(true);
    } finally {
      setRefreshing(false);
    }
  };

  // STEP 3: Filter items by confidence
  const filteredAccum = useMemo(() => {
    const items = data?.topAccumulation || [];
    if (!strongOnly) return items;
    return items.filter(i => (i.confidence ?? 0) >= CONF_STRONG);
  }, [data, strongOnly]);

  const filteredDist = useMemo(() => {
    const items = data?.topDistribution || [];
    if (!strongOnly) return items;
    return items.filter(i => (i.confidence ?? 0) >= CONF_STRONG);
  }, [data, strongOnly]);

  const totalCount = (data?.topAccumulation?.length || 0) + (data?.topDistribution?.length || 0);
  const strongCount = useMemo(() => {
    const acc = (data?.topAccumulation || []).filter(i => (i.confidence ?? 0) >= CONF_STRONG).length;
    const dist = (data?.topDistribution || []).filter(i => (i.confidence ?? 0) >= CONF_STRONG).length;
    return acc + dist;
  }, [data]);

  // Loading state
  if (loading && !data) {
    return (
      <div className="space-y-6" data-testid="signals-tab">
        <div className="h-96 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="text-sm text-gray-500">Loading signals...</span>
          </div>
        </div>
      </div>
    );
  }

  // Error state (only if no cached data)
  if (error && !data) {
    return (
      <div className="space-y-6" data-testid="signals-tab">
        <div className="rounded-xl bg-red-50 p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <div className="text-red-600 font-medium mb-2">Failed to load signals</div>
          <div className="text-sm text-gray-500 mb-4">{error}</div>
          <button
            onClick={() => fetchData()}
            className="px-4 py-2 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const hasNoStrong = strongOnly && filteredAccum.length === 0 && filteredDist.length === 0;

  // Mode toggle (shared between Flow, Live, and Deviations)
  const ModeToggle = (
    <div className="flex p-1" data-testid="signals-mode-toggle">
      <button
        onClick={() => setMode('flow')}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-all ${
          mode === 'flow' ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
        }`}
        data-testid="signals-mode-flow"
      >
        <BarChart2 className="w-3.5 h-3.5" />
        Flow
      </button>
      <button
        onClick={() => setMode('live')}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-all ${
          mode === 'live' ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
        }`}
        data-testid="signals-mode-live"
      >
        <Zap className="w-3.5 h-3.5" />
        Live
      </button>
      <button
        onClick={() => setMode('deviations')}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-all ${
          mode === 'deviations' ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
        }`}
        data-testid="signals-mode-deviations"
      >
        <Radio className="w-3.5 h-3.5" />
        Deviations
      </button>
    </div>
  );

  // Deviations mode: render deviation watchlist
  if (mode === 'deviations') {
    return (
      <div className="space-y-4" data-testid="signals-tab">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Signals</h2>
            <p className="text-sm text-gray-500 mt-1">Emerging deviations and unusual activity watchlist</p>
          </div>
          {ModeToggle}
        </div>
        <SignalsDeviationsMode />
      </div>
    );
  }

  // Live mode: render D1 signals page
  if (mode === 'live') {
    return (
      <div className="space-y-4" data-testid="signals-tab">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Signals</h2>
            <p className="text-sm text-gray-500 mt-1">Live event-based signals with filters and alerts</p>
          </div>
          {ModeToggle}
        </div>
        <Suspense fallback={
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        }>
          <LegacyTabWrapper>
            <SignalsPageD1 layoutMode="embedded" />
          </LegacyTabWrapper>
        </Suspense>
      </div>
    );
  }

  // Flow mode (default)
  return (
    <div className="space-y-6" data-testid="signals-tab">
      {/* Data Status Banner */}
      <DataStatusBanner
        status={computeSignalsStatus(
          (data?.topAccumulation || []).concat(data?.topDistribution || []),
          data?.meta
        )}
      />

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {ModeToggle}
          <div className="flex items-center gap-2 p-1">
            {(['24h', '7d'] as const).map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                timeframe === tf
                  ? 'text-gray-900'
                  : 'text-gray-400 hover:text-gray-700'
              }`}
              data-testid={`signals-timeframe-${tf}`}
            >
              {tf.toUpperCase()}
            </button>
          ))}
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm transition-colors disabled:opacity-50"
          data-testid="signals-refresh-btn"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* P0.7: Entity Filter Pill */}
      {entityFilter && (
        <EntityFilterPill 
          entityId={entityFilter} 
          onClear={() => setEntityFilter(null)} 
        />
      )}

      {/* Status Bar */}
      <StatusBar 
        data={data} 
        jobStatus={jobStatus} 
        loading={refreshing}
        strongOnly={strongOnly}
        onToggleStrong={() => setStrongOnly(!strongOnly)}
        strongCount={strongCount}
        totalCount={totalCount}
      />

      {/* No Strong Signals State */}
      {hasNoStrong && totalCount > 0 && (
        <div className="rounded-xl bg-amber-50 p-6 text-center">
          <Filter className="w-10 h-10 text-amber-500 mx-auto mb-3" />
          <div className="text-amber-700 font-medium mb-2">No strong signals</div>
          <div className="text-sm text-gray-600 mb-4">
            All {totalCount} signals have confidence below {Math.round(CONF_STRONG * 100)}%
          </div>
          <button
            onClick={() => setStrongOnly(false)}
            className="px-4 py-2 rounded-lg bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors text-sm font-medium"
          >
            Show All Signals
          </button>
        </div>
      )}

      {/* Tables Grid */}
      {!hasNoStrong && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <AltFlowTable
            title="Strong Accumulation"
            type="accumulation"
            items={filteredAccum}
            onItemClick={setSelectedItem}
            confThreshold={CONF_STRONG}
          />

          <AltFlowTable
            title="Strong Distribution"
            type="distribution"
            items={filteredDist}
            onItemClick={setSelectedItem}
            confThreshold={CONF_STRONG}
          />
        </div>
      )}

      {/* Empty State (no data at all) */}
      {data && data.meta.tokenCount === 0 && (
        <div className="rounded-xl bg-gray-50 p-8 text-center">
          <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <div className="text-gray-600 font-medium mb-2">No signals detected</div>
          <div className="text-sm text-gray-500">
            Flow data is being collected. Check back in a few minutes.
          </div>
        </div>
      )}

      {/* Details Drawer */}
      <AltFlowDetailsDrawer
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
