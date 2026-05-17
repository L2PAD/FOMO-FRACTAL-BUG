/**
 * NetworkPathsPanel - Clean network paths display
 * No colored badges, no visual noise. Plain text only.
 */
import { useState, useEffect } from 'react';
import { Network, Route, Target, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const PathVisual = ({ path }) => (
  <div className="py-2 hover:bg-gray-50 transition-all">
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="font-medium text-gray-700">{path.kind}</span>
        <span>{path.hops} hop{path.hops !== 1 ? 's' : ''}</span>
        <span>str: {path.strength.toFixed(2)}</span>
      </div>
      <span className="text-xs font-medium text-green-600">+{Math.round(path.contribution_0_1 * 100)}%</span>
    </div>
    <div className="flex items-center gap-1 flex-wrap text-xs">
      {path.nodes.map((node, idx) => (
        <div key={node.id} className="flex items-center gap-1">
          <span className="text-gray-900">@{node.handle || node.id}</span>
          {idx < path.nodes.length - 1 && <ArrowRight className="w-3 h-3 text-gray-300" />}
        </div>
      ))}
    </div>
    {path.explain_text && <p className="text-[10px] text-gray-400 mt-1 italic">{path.explain_text}</p>}
  </div>
);

const ExposureCard = ({ exposure }) => (
  <div className="mb-2">
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-2">
        <Network className="w-4 h-4 text-blue-600" />
        <span className="text-sm font-semibold text-gray-900">Network Exposure</span>
        <span className="text-xs text-gray-500">{exposure.exposure_tier}</span>
      </div>
      <span className="text-lg font-bold text-blue-600">{Math.round(exposure.exposure_score_0_1 * 100)}</span>
    </div>
    <div className="grid grid-cols-4 gap-2 text-center text-xs">
      <div><div className="font-semibold text-gray-900">{exposure.reachable_elite}</div><div className="text-gray-400">Elite Reach</div></div>
      <div><div className="font-semibold text-gray-900">{exposure.reachable_high}</div><div className="text-gray-400">High Reach</div></div>
      <div><div className="font-semibold text-gray-900">{exposure.avg_hops_to_elite != null ? exposure.avg_hops_to_elite.toFixed(1) : '—'}</div><div className="text-gray-400">Hops to Elite</div></div>
      <div><div className="font-semibold text-gray-900">{exposure.avg_hops_to_high != null ? exposure.avg_hops_to_high.toFixed(1) : '—'}</div><div className="text-gray-400">Hops to High</div></div>
    </div>
  </div>
);

export default function NetworkPathsPanel({ accountId, onHighlightPath }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      if (!accountId) return;
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/connections/paths/${accountId}`);
        const json = await res.json();
        if (json.ok) setData(json.data);
        else setError(json.message || 'Failed to load');
      } catch (err) { setError(err.message); }
      setLoading(false);
    };
    fetchData();
  }, [accountId]);

  if (loading) return <div className="animate-pulse"><div className="h-24 bg-gray-200 rounded mb-2"></div><div className="h-16 bg-gray-200 rounded"></div></div>;
  if (error || !data) return <div className="text-center py-4"><Network className="w-8 h-8 mx-auto mb-2 text-gray-300" /><p className="text-gray-500 text-sm">No network data</p></div>;

  const { paths, exposure, explain } = data;
  const displayPaths = showAll ? paths.paths : paths.paths.slice(0, 3);

  return (
    <div data-testid="network-paths-panel">
      <ExposureCard exposure={exposure} />
      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Route className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-semibold uppercase tracking-wider">Paths ({paths.paths.length})</span>
          </div>
          {paths.paths.length > 3 && (
            <button onClick={() => setShowAll(!showAll)} className="text-[10px] text-blue-600 hover:text-blue-800">
              {showAll ? 'Show less' : `Show all ${paths.paths.length}`}
            </button>
          )}
        </div>
        {paths.paths.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-3">No paths found</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {displayPaths.map((path, idx) => <PathVisual key={idx} path={path} />)}
          </div>
        )}
      </div>
    </div>
  );
}
