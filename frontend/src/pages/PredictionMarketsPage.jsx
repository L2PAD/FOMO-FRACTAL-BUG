/**
 * Prediction OS — Terminal Layout (4 tabs)
 *
 * LIGHT theme consistent with the rest of the app.
 * Dark accents only for key elements (hero, action banners).
 * Tabs: Overview | Markets | Signals | Analytics
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw, Crosshair, LayoutGrid, TrendingUp, Bell, BarChart3,
} from 'lucide-react';

import { mapAllCases, groupByStatus } from '../adapters/uiCase.adapter';
import TerminalOverview from '../components/prediction/TerminalOverview';
import FeedTab from '../components/prediction/FeedTab';
import SignalsTab from '../components/prediction/SignalsTab';
import TerminalAnalytics from '../components/prediction/TerminalAnalytics';

const API = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: 'overview',  label: 'Overview',  icon: LayoutGrid },
  { id: 'markets',   label: 'Markets',   icon: TrendingUp },
  { id: 'signals',   label: 'Signals',   icon: Bell },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
];

export default function PredictionMarketsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [rawData, setRawData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const activeTab = searchParams.get('tab') || 'overview';
  const setTab = (id) => setSearchParams({ tab: id }, { replace: true });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/prediction/run?limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRawData(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const uiCases = useMemo(() => {
    if (!rawData?.sections) return [];
    return mapAllCases(rawData.sections);
  }, [rawData]);

  const grouped = useMemo(() => groupByStatus(uiCases), [uiCases]);

  const [metaAlerts, setMetaAlerts] = useState([]);
  useEffect(() => {
    fetch(`${API}/api/alert-correlation/history?limit=10`)
      .then(r => r.ok ? r.json() : { metaAlerts: [] })
      .then(d => setMetaAlerts(d.metaAlerts || []))
      .catch(() => {});
  }, []);

  return (
    <div data-testid="prediction-markets-page" className="flex flex-col h-full min-w-0">
      {/* Header */}
      <div className="flex-shrink-0 min-w-0 border-b border-gray-200 z-20 bg-white/80 backdrop-blur-xl">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo + Title */}
            <div className="flex items-center gap-3">
              <Crosshair className="w-6 h-6 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">Prediction OS</h1>
                <p className="text-sm text-gray-500">Cross-platform edge detection & decision intelligence</p>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1" data-testid="prediction-tabs">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setTab(tab.id)}
                    data-testid={`prediction-tab-${tab.id}`}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-gray-900 text-white'
                        : 'text-gray-400 hover:text-gray-700'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}

              <div className="w-px h-5 bg-gray-200 mx-2" />
              <button
                data-testid="refresh-btn"
                onClick={fetchData}
                disabled={loading}
                className="p-1.5 rounded-md hover:bg-gray-100 transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 overflow-auto bg-gray-50/50">
        {error && (
          <div data-testid="error-msg" className="px-6 mt-4">
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          </div>
        )}

        {activeTab === 'overview' && (
          <TerminalOverview uiCases={uiCases} grouped={grouped} onNavigate={setTab} metaAlerts={metaAlerts} />
        )}
        {activeTab === 'markets' && <FeedTab />}
        {activeTab === 'signals' && <SignalsTab />}
        {activeTab === 'analytics' && <TerminalAnalytics />}
      </main>
    </div>
  );
}
