/**
 * Exchange Alpha Tab — Radar + Signals combined
 * Signals integrated as a view mode alongside Spot/Alpha/Futures
 */
import React, { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import RadarControlBar from '../components/exchange/RadarControlBar';
import RadarTopSetups from '../components/exchange/RadarTopSetups';
import RadarScanList from '../components/exchange/RadarScanList';
import RadarExplainDrawer from '../components/exchange/RadarExplainDrawer';
import RadarPagination from '../components/exchange/RadarPagination';
import { fetchRadarData, fetchUniverse, fetchAlphaUniverse } from '../api/radarV11.api';
import { Loader2 } from 'lucide-react';

const SignalsIntelPage = lazy(() => import('./SignalsIntelPage'));

const PAGE_SIZE = 25;

export default function ExchangeRadarTab() {
  const [view, setView] = useState('spot'); // spot | alpha | futures | signals
  const [horizon, setHorizon] = useState('auto');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('all');
  const [minConviction, setMinConviction] = useState(0);
  const [sort, setSort] = useState('conviction');
  const [page, setPage] = useState(1);
  const [universe, setUniverse] = useState(null);
  const [alphaMeta, setAlphaMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedRow, setSelectedRow] = useState(null);
  const [updatedAt, setUpdatedAt] = useState('');
  const searchTimer = useRef(null);

  const isSignals = view === 'signals';
  const radarMode = isSignals ? 'spot' : view;

  const handleSearchChange = (s) => {
    setSearch(s);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(s);
      setPage(1);
    }, 300);
  };

  const loadData = useCallback(async () => {
    if (isSignals) return;
    setLoading(true);
    try {
      const result = await fetchRadarData({
        mode: radarMode,
        page,
        limit: PAGE_SIZE,
        search: debouncedSearch || undefined,
        verdict: verdictFilter,
        minConv: minConviction || undefined,
        sort,
      });
      setRows(result.rows);
      setMeta(result.meta);
      setUpdatedAt(result.updatedAt);
    } catch (err) {
      console.error('Radar fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [radarMode, page, debouncedSearch, verdictFilter, minConviction, sort, isSignals]);

  useEffect(() => {
    fetchUniverse().then(setUniverse).catch(console.error);
    fetchAlphaUniverse().then(setAlphaMeta).catch(console.error);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleViewChange = (v) => { setView(v); setPage(1); };
  const handleHorizonChange = (h) => { setHorizon(h); setPage(1); };
  const handleVerdictChange = (v) => { setVerdictFilter(v); setPage(1); };
  const handleConvChange = (c) => { setMinConviction(c); setPage(1); };
  const handleSortChange = (s) => { setSort(s); setPage(1); };

  return (
    <div data-testid="exchange-radar-tab" className="pb-8">
      <RadarControlBar
        mode={radarMode} setMode={handleViewChange}
        view={view}
        horizon={horizon} setHorizon={isSignals ? null : handleHorizonChange}
        search={search} setSearch={handleSearchChange}
        verdictFilter={verdictFilter} setVerdictFilter={handleVerdictChange}
        minConviction={minConviction} setMinConviction={handleConvChange}
        sort={sort} setSort={handleSortChange}
        universe={universe} loading={loading}
        updatedAt={updatedAt} onRefresh={loadData}
        alphaMeta={alphaMeta} currentMode={radarMode}
      />

      {isSignals ? (
        <Suspense fallback={<div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}>
          <SignalsIntelPage />
        </Suspense>
      ) : (
        <>
          <RadarTopSetups rows={rows} onRowClick={setSelectedRow} horizon={horizon} />
          <RadarScanList rows={rows} mode={radarMode} onRowClick={setSelectedRow} horizon={horizon} />
          {meta && meta.pages > 1 && (
            <RadarPagination page={meta.page} pages={meta.pages} total={meta.total} limit={meta.limit} onPageChange={setPage} />
          )}
          <RadarExplainDrawer row={selectedRow} open={!!selectedRow} onClose={() => setSelectedRow(null)} />
        </>
      )}
    </div>
  );
}
