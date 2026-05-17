/**
 * Channel Header
 * Main info block for channel detail page
 */
import { Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react';

function TierBadge({ tier }) {
  const colors = {
    S: 'bg-violet-100 text-violet-700 border-violet-200',
    A: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    B: 'bg-blue-100 text-blue-700 border-blue-200',
    C: 'bg-amber-100 text-amber-700 border-amber-200',
    D: 'bg-gray-100 text-gray-500 border-gray-200',
  };
  return (
    <span className={`px-3 py-1 rounded-lg text-sm font-semibold border ${colors[tier] || colors.D}`}>
      {tier} Tier
    </span>
  );
}

function TrendBadge({ trend }) {
  if (!trend) return null;
  const isUp = trend === 'improving';
  const isDown = trend === 'deteriorating';
  
  if (isUp) return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-50 text-emerald-600 rounded-lg text-xs font-medium">
      <TrendingUp className="w-3 h-3" /> Improving
    </span>
  );
  if (isDown) return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-600 rounded-lg text-xs font-medium">
      <TrendingDown className="w-3 h-3" /> Deteriorating
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 text-gray-500 rounded-lg text-xs font-medium">
      <Minus className="w-3 h-3" /> Flat
    </span>
  );
}

export default function ChannelHeader({ data, credibility }) {
  if (!data) return null;
  
  const updated = data?.computedAt || data?.updatedAt;
  
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="channel-header">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link 
            to="/telegram" 
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Leaderboard
          </Link>
          
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">@{data.username}</h1>
            <TierBadge tier={data.tier} />
            <TrendBadge trend={credibility?.trend?.direction} />
          </div>
          
          <div className="mt-3 flex items-center gap-4 text-sm">
            <div>
              <span className="text-gray-500">Intel Score:</span>{' '}
              <span className="font-bold text-blue-600 text-lg">{Number(data.intelScore ?? 0).toFixed(1)}</span>
            </div>
            <div className="text-gray-300">|</div>
            <div>
              <span className="text-gray-500">Alpha:</span>{' '}
              <span className="font-semibold text-emerald-600">{Number(data.components?.alphaScore ?? 0).toFixed(1)}</span>
            </div>
            <div className="text-gray-300">|</div>
            <div>
              <span className="text-gray-500">Cred:</span>{' '}
              <span className="font-semibold text-amber-600">{Number(data.components?.credibilityScore ?? 0).toFixed(1)}</span>
            </div>
            <div className="text-gray-300">|</div>
            <div>
              <span className="text-gray-500">NetAlpha:</span>{' '}
              <span className="font-semibold text-violet-600">{Number(data.components?.networkAlphaScore ?? 0).toFixed(1)}</span>
            </div>
          </div>
        </div>
        
        <div className="text-right text-sm space-y-1">
          <div>
            <span className="text-gray-500">Fraud Risk:</span>{' '}
            <span className={`font-medium ${Number(data.components?.fraudRisk ?? 0) > 0.5 ? 'text-red-600' : 'text-gray-600'}`}>
              {(Number(data.components?.fraudRisk ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
          {credibility?.hitRatePosterior && (
            <div>
              <span className="text-gray-500">Hit Rate:</span>{' '}
              <span className="font-medium text-gray-600">
                {(Number(credibility.hitRatePosterior.mean ?? 0) * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {updated && (
            <div className="text-gray-400">
              Updated: {new Date(updated).toLocaleString()}
            </div>
          )}
          <a 
            href={`https://t.me/${data.username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-blue-500 hover:text-blue-600 mt-2"
          >
            <ExternalLink className="w-3 h-3" />
            Open in Telegram
          </a>
        </div>
      </div>
    </div>
  );
}
