/**
 * Twitter Feed — Signal-Enriched Posts
 * 
 * KEY UX:
 * - HIGH impact tweets = large cards, LOW = collapsed
 * - Each tweet shows affected assets with direction (ETH ↑, SOL ↑)
 * - Signal injection from entity_alerts
 * - Top Signal Strip shared with AI page
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Skeleton } from '../components/ui/skeleton';
import { 
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { 
  Search, 
  RefreshCw, 
  ChevronRight, 
  ChevronDown,
  MessageCircle, 
  Repeat2, 
  Heart, 
  Eye, 
  Bookmark,
  Info,
  TrendingUp,
  TrendingDown,
  Inbox,
  MessageSquare,
  Filter,
  AlertTriangle,
  RotateCcw,
  Zap,
  Clock,
  ArrowUp,
  ArrowDown,
  Minus,
  X,
  Loader2,
  Plus,
  Hash,
  User,
  Trash2,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============================================
// Signal Config
// ============================================
const SIGNAL_CONFIG = {
  MOMENTUM: { icon: TrendingUp, bg: 'bg-emerald-50', text: 'text-emerald-700', gradient: 'from-emerald-500 to-teal-600' },
  ATTENTION: { icon: AlertTriangle, bg: 'bg-amber-50', text: 'text-amber-700', gradient: 'from-amber-500 to-orange-600' },
  NEUTRAL: { icon: Minus, bg: 'bg-gray-50', text: 'text-gray-600', gradient: 'from-gray-400 to-gray-500' },
};

// ============================================
// Freshness + Confidence styles
// ============================================
const FRESHNESS_STYLES = {
  FRESH: { opacity: 'opacity-100', badge: 'bg-emerald-500 text-white', label: 'FRESH' },
  ACTIVE: { opacity: 'opacity-90', badge: 'bg-blue-500 text-white', label: 'ACTIVE' },
  AGING: { opacity: 'opacity-60', badge: 'bg-amber-500 text-white', label: 'AGING' },
  DEAD: { opacity: 'opacity-40', badge: 'bg-gray-400 text-white', label: 'STALE' },
};

// ============================================
// Top Signal Strip (shared concept)
// ============================================
const TopSignalStrip = ({ signals }) => {
  if (!signals || signals.length === 0) return null;
  return (
    <div className="mb-5" data-testid="top-signal-strip">
      <div className="flex items-center gap-2 mb-2">
        <Zap className="w-4 h-4 text-amber-500" />
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Active Signals</h2>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {signals.filter(s => s.freshness !== 'DEAD').slice(0, 5).map(sig => {
          const config = SIGNAL_CONFIG[sig.signalType] || SIGNAL_CONFIG.NEUTRAL;
          const fresh = FRESHNESS_STYLES[sig.freshness] || FRESHNESS_STYLES.ACTIVE;
          return (
            <div key={sig.entityId}
              className={`flex-shrink-0 rounded-lg bg-gradient-to-r ${config.gradient} text-white px-3 py-2 text-xs shadow-md ${fresh.opacity}`}
              data-testid={`top-signal-${sig.entityId}`}>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="font-bold">{sig.symbol}</span>
                <span className="text-sm">{sig.setupType === 'BREAKOUT' ? '↗' : sig.setupType === 'EXHAUSTION' ? '⚠' : '→'}</span>
                <span className="uppercase opacity-80">{sig.setupType || sig.signalType}</span>
                <span className="opacity-50">—</span>
                <span className="font-bold opacity-80">{sig.signalMaturity || ''}</span>
                {sig.alignment && (
                  <span className={`text-[8px] px-1 py-0.5 rounded-full font-bold ml-1 ${
                    sig.alignment === 'STRONG' ? 'bg-white/30' : sig.alignment === 'MIXED' ? 'bg-white/20' : 'bg-white/10'
                  }`}>{sig.alignment}</span>
                )}
                {sig.rank && sig.rank <= 3 && (
                  <span className="text-[8px] px-1 py-0.5 rounded-full bg-white/20 font-bold ml-1">Top {sig.rank}</span>
                )}
                <span className={`text-[8px] px-1 py-0.5 rounded-full ${fresh.badge} font-bold ml-1`}>{fresh.label}</span>
              </div>
              <div className="text-white/70 text-[10px] truncate max-w-[180px]">{sig.spikeText}</div>
              {sig.expectedMove && (
                <div className="text-white/60 text-[10px] mt-0.5">Expected: {sig.expectedMove.text}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================
// Affected Assets under tweet
// ============================================
const AffectedAssets = ({ assets }) => {
  if (!assets || assets.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-3" data-testid="affected-assets">
      {assets.map(a => {
        const dirIcon = a.direction === 'up' 
          ? <ArrowUp className="w-3 h-3 text-emerald-500" />
          : a.direction === 'down' 
            ? <ArrowDown className="w-3 h-3 text-red-500" />
            : <Minus className="w-3 h-3 text-gray-400" />;
        const dirColor = a.direction === 'up' 
          ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
          : a.direction === 'down'
            ? 'bg-red-50 text-red-700 border-red-100'
            : 'bg-gray-50 text-gray-600 border-gray-100';
        return (
          <span key={a.id} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${dirColor}`}>
            {dirIcon}
            {a.symbol}
            <span className="opacity-60 text-[10px]">({a.signal})</span>
          </span>
        );
      })}
    </div>
  );
};

// ============================================
// Signal injection badge on tweet
// ============================================
const TweetSignalBadge = ({ signal }) => {
  if (!signal) return null;
  const config = SIGNAL_CONFIG[signal.type] || SIGNAL_CONFIG.NEUTRAL;
  const Icon = config.icon;
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${config.bg}`}
      data-testid={`tweet-signal-${signal.type?.toLowerCase()}`}>
      <Icon className={`w-3 h-3 ${config.text}`} />
      <span className={`text-[10px] font-bold uppercase ${config.text}`}>{signal.type}</span>
      <span className={`text-[10px] ${config.text} opacity-70`}>({signal.score})</span>
    </div>
  );
};

// ============================================
// Sentiment Bar
// ============================================
const SentimentBar = ({ sentiment, size = 'default' }) => {
  const score = sentiment.score;
  const confidence = sentiment.confidence;
  const percentage = Math.round(score * 100);
  const confidencePct = Math.round(confidence * 100);
  const barHeight = size === 'small' ? 'h-1.5' : 'h-2';
  const isAdjusted = sentiment.rulesBoost !== 0 || (sentiment.rulesApplied && sentiment.rulesApplied.length > 0);

  const getLabelColor = (s) => {
    if (s >= 0.6) return 'text-emerald-600';
    if (s <= 0.4) return 'text-red-500';
    return 'text-amber-500';
  };
  const getLabel = (s) => {
    if (s >= 0.6) return 'Positive';
    if (s <= 0.4) return 'Negative';
    return 'Neutral';
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-gray-500">Confidence</span>
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-gray-400 hover:text-gray-700 focus:outline-none">
                  <Info className="w-3.5 h-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-gray-800 border-gray-700 text-white max-w-xs">
                <div className="space-y-2 p-1">
                  <div className="font-medium text-sm border-b pb-1.5">Why this result?</div>
                  {sentiment.reasons && sentiment.reasons.length > 0 && (
                    <ul className="text-sm space-y-0.5">
                      {sentiment.reasons.map((r, i) => (
                        <li key={i} className="text-gray-300 flex items-start gap-1.5">
                          <span className="text-emerald-400 mt-0.5">*</span>{r}
                        </li>
                      ))}
                    </ul>
                  )}
                  {sentiment.rulesApplied && sentiment.rulesApplied.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {sentiment.rulesApplied.map((r, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{r}</span>
                      ))}
                    </div>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {isAdjusted && (
            <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-medium">Adjusted</span>
          )}
        </div>
        <span className={`font-medium ${getLabelColor(score)}`}>{getLabel(score)}</span>
      </div>
      <div className={`w-full ${barHeight} rounded-full overflow-hidden relative`}
        style={{ background: 'linear-gradient(to right, #ef4444, #f59e0b, #22c55e)' }}>
        <div className="absolute top-0 h-full w-1 bg-white shadow-md rounded"
          style={{ left: `calc(${percentage}% - 2px)` }} />
      </div>
      <div className="flex justify-between text-xs text-gray-400">
        <span>{confidencePct}%</span>
      </div>
    </div>
  );
};

// ============================================
// HIGH impact tweet card (full)
// ============================================
const HighImpactTweetCard = ({ tweet, onClick }) => (
  <Card 
    className="bg-white hover:bg-gray-50 cursor-pointer transition-all duration-200 border-gray-100 group"
    onClick={() => onClick(tweet)}
    data-testid={`tweet-card-${tweet.id}`}
  >
    <CardContent className="p-5">
      <div className="flex items-start gap-3">
        <img src={tweet.avatar} alt={tweet.username}
          className="w-12 h-12 rounded-full object-cover bg-gray-100"
          onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${tweet.username}`; }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-gray-900 text-base">{tweet.username}</span>
            <span className="text-gray-500 text-sm">{tweet.handle}</span>
            <span className="text-gray-400 text-sm">· {tweet.timestamp}</span>
            <span className="text-xs font-bold uppercase text-amber-700">HIGH IMPACT</span>
          </div>
          <p className="text-gray-700 mt-1.5 text-sm leading-relaxed">{tweet.content}</p>
          {tweet.image && (
            <img src={tweet.image} alt="Tweet media"
              className="mt-3 rounded-xl w-full max-h-64 object-cover"
              onError={(e) => { e.target.style.display = 'none'; }} />
          )}
          
          {/* Signal + Affected Assets */}
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            <TweetSignalBadge signal={tweet.signal} />
            <AffectedAssets assets={tweet.affectedAssets} />
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0 group-hover:text-gray-600 group-hover:translate-x-0.5 transition-all" />
      </div>

      <div className="flex items-center gap-6 mt-4 text-gray-500 text-sm pl-13">
        <div className="flex items-center gap-1"><MessageCircle className="w-4 h-4" /><span>{tweet.metrics.comments}</span></div>
        <div className="flex items-center gap-1"><Repeat2 className="w-4 h-4" /><span>{tweet.metrics.retweets}</span></div>
        <div className="flex items-center gap-1"><Heart className="w-4 h-4" /><span>{tweet.metrics.likes}</span></div>
        <div className="flex items-center gap-1"><Eye className="w-4 h-4" /><span>{tweet.metrics.views}</span></div>
        <div className="flex items-center gap-1"><Bookmark className="w-4 h-4" /><span>{tweet.metrics.bookmarks}</span></div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-100">
        <SentimentBar sentiment={tweet.sentiment} />
      </div>
    </CardContent>
  </Card>
);

// ============================================
// MEDIUM impact tweet card
// ============================================
const MediumTweetCard = ({ tweet, onClick }) => (
  <Card 
    className="bg-white hover:bg-gray-50 hover:shadow-sm cursor-pointer transition-all duration-200 border-gray-200 group"
    onClick={() => onClick(tweet)}
    data-testid={`tweet-card-${tweet.id}`}
  >
    <CardContent className="p-4">
      <div className="flex items-start gap-3">
        <img src={tweet.avatar} alt={tweet.username}
          className="w-10 h-10 rounded-full object-cover bg-gray-100"
          onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${tweet.username}`; }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 truncate">{tweet.username}</span>
            <span className="text-gray-500 text-sm">{tweet.handle}</span>
            <span className="text-gray-400 text-sm">· {tweet.timestamp}</span>
          </div>
          <p className="text-gray-700 mt-1 text-sm leading-relaxed">{tweet.content}</p>
          
          {/* Signal + Affected Assets */}
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            <TweetSignalBadge signal={tweet.signal} />
            <AffectedAssets assets={tweet.affectedAssets} />
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0 group-hover:text-gray-600 transition-all" />
      </div>

      <div className="flex items-center gap-6 mt-3 text-gray-500 text-xs">
        <div className="flex items-center gap-1"><Heart className="w-3.5 h-3.5" /><span>{tweet.metrics.likes}</span></div>
        <div className="flex items-center gap-1"><Repeat2 className="w-3.5 h-3.5" /><span>{tweet.metrics.retweets}</span></div>
        <div className="flex items-center gap-1"><Eye className="w-3.5 h-3.5" /><span>{tweet.metrics.views}</span></div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-100">
        <SentimentBar sentiment={tweet.sentiment} size="small" />
      </div>
    </CardContent>
  </Card>
);

// ============================================
// LOW impact tweet (collapsed)
// ============================================
const LowTweetCard = ({ tweet, onClick }) => (
  <div 
    className="flex items-center gap-3 p-3 hover:bg-gray-50 rounded-lg cursor-pointer border border-transparent hover:border-gray-200 transition-all"
    onClick={() => onClick(tweet)}
    data-testid={`tweet-card-${tweet.id}`}
  >
    <img src={tweet.avatar} alt={tweet.username}
      className="w-8 h-8 rounded-full object-cover bg-gray-100"
      onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${tweet.username}`; }} />
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium text-gray-900 truncate">{tweet.username}</span>
        <span className="text-gray-400 text-xs">· {tweet.timestamp}</span>
      </div>
      <p className="text-gray-600 text-xs truncate">{tweet.content}</p>
    </div>
    <div className="flex items-center gap-2 flex-shrink-0">
      {tweet.affectedAssets && tweet.affectedAssets.length > 0 && (
        <span className="text-xs text-gray-400">{tweet.affectedAssets.length} assets</span>
      )}
      <ChevronRight className="w-4 h-4 text-gray-300" />
    </div>
  </div>
);

// ============================================
// Tweet detail modal
// ============================================
const TweetDetailModal = ({ tweet, open, onClose }) => {
  if (!tweet) return null;
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl bg-white border-gray-200 p-0 max-h-[90vh] overflow-hidden [&>button]:text-gray-500 [&>button]:hover:text-gray-900 [&>button]:hover:bg-gray-100 [&>button]:top-3 [&>button]:right-3 [&>button]:z-50" style={{ borderRadius: '16px' }}>
        <div className="flex items-center gap-3 p-4 pr-12 border-b border-gray-100">
          <img src={tweet.avatar} alt={tweet.username}
            className="w-10 h-10 rounded-full bg-gray-100 object-cover"
            onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${tweet.username}`; }} />
          <div>
            <div className="font-semibold text-gray-900">{tweet.username}</div>
            <div className="text-gray-500 text-sm">{tweet.handle}</div>
          </div>
          {tweet.impact === 'HIGH' && (
            <span className="ml-auto px-2 py-0.5 bg-amber-50 text-amber-700 rounded text-xs font-bold uppercase">HIGH IMPACT</span>
          )}
        </div>

        <ScrollArea className="max-h-[calc(90vh-80px)]">
          <div className="p-4">
            <p className="text-gray-800 leading-relaxed">{tweet.content}</p>
            {tweet.image && (
              <img src={tweet.image} alt="Tweet media" className="mt-4 rounded-xl w-full"
                onError={(e) => { e.target.style.display = 'none'; }} />
            )}

            <div className="flex items-center gap-6 mt-4 pt-4 border-t border-gray-100 text-gray-500">
              <div className="flex items-center gap-1.5"><MessageCircle className="w-5 h-5" /><span>{tweet.metrics.comments}</span></div>
              <div className="flex items-center gap-1.5"><Repeat2 className="w-5 h-5" /><span>{tweet.metrics.retweets}</span></div>
              <div className="flex items-center gap-1.5"><Heart className="w-5 h-5" /><span>{tweet.metrics.likes}</span></div>
              <div className="flex items-center gap-1.5"><Eye className="w-5 h-5" /><span>{tweet.metrics.views}</span></div>
              <div className="flex items-center gap-1.5"><Bookmark className="w-5 h-5" /><span>{tweet.metrics.bookmarks}</span></div>
            </div>

            {/* Signal Block */}
            {tweet.signal && (
              <div className={`mt-4 p-3 rounded-lg ${SIGNAL_CONFIG[tweet.signal.type]?.bg || 'bg-gray-50'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Zap className={`w-4 h-4 ${SIGNAL_CONFIG[tweet.signal.type]?.text || 'text-gray-500'}`} />
                  <span className={`text-sm font-bold ${SIGNAL_CONFIG[tweet.signal.type]?.text || 'text-gray-600'}`}>
                    {tweet.signal.type} Signal
                  </span>
                  <span className="text-xs text-gray-500">Score: {tweet.signal.score} · Conf: {tweet.signal.confidence}%</span>
                </div>
                <p className="text-xs text-gray-600">Affects: {tweet.signal.entity}</p>
              </div>
            )}

            {/* Affected Assets */}
            {tweet.affectedAssets && tweet.affectedAssets.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-2">Affected Assets</h4>
                <AffectedAssets assets={tweet.affectedAssets} />
              </div>
            )}

            <div className="mt-4 pt-4 border-t border-gray-100">
              <h4 className="text-sm font-medium text-gray-500 mb-2">Post Sentiment</h4>
              <SentimentBar sentiment={tweet.sentiment} />
            </div>

            {tweet.commentsAggregate && tweet.commentsAggregate.total > 0 && (
              <div className="mt-4 rounded-lg p-4 border bg-gray-50 border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900 text-sm">Community Sentiment</h4>
                  <span className={`text-sm font-medium ${
                    tweet.commentsAggregate.dominant === 'POSITIVE' ? 'text-emerald-600' : 
                    tweet.commentsAggregate.dominant === 'NEGATIVE' ? 'text-red-600' : 'text-amber-600'
                  }`}>{tweet.commentsAggregate.dominant}</span>
                </div>
                <div className="h-2.5 rounded-full overflow-hidden flex bg-gray-200">
                  <div className="bg-red-400" style={{ width: `${tweet.commentsAggregate.percentages.negative}%` }} />
                  <div className="bg-amber-300" style={{ width: `${tweet.commentsAggregate.percentages.neutral}%` }} />
                  <div className="bg-emerald-400" style={{ width: `${tweet.commentsAggregate.percentages.positive}%` }} />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-600 mt-1">
                  <span>{tweet.commentsAggregate.percentages.positive}% Positive</span>
                  <span>{tweet.commentsAggregate.percentages.neutral}% Neutral</span>
                  <span>{tweet.commentsAggregate.percentages.negative}% Negative</span>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Sparkline
// ============================================
const Sparkline = ({ data, width = 80, height = 24 }) => {
  if (!data || data.length < 2) return null;
  const scores = data.map(d => d.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 0.1;
  const points = scores.map((score, i) => {
    const x = (i / (scores.length - 1)) * width;
    const y = height - ((score - min) / range) * height;
    return `${x},${y}`;
  });
  const trendUp = scores[scores.length - 1] > scores[0];
  const lineColor = trendUp ? '#10b981' : '#ef4444';
  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={`M ${points.join(' L ')}`} fill="none" stroke={lineColor}
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={height - ((scores[scores.length - 1] - min) / range) * height}
        r="2" fill={lineColor} />
    </svg>
  );
};

// ============================================
// Account card
// ============================================
const AccountCard = ({ account, selected, onClick }) => {
  const sent = account.accountSentiment;
  const label = sent?.current?.label;
  const delta24h = sent?.delta?.['24h'] || 0;
  const getLabelBg = (l) => l === 'POSITIVE' ? 'bg-emerald-50 text-emerald-600' : l === 'NEGATIVE' ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600';

  return (
    <div className={`p-3 rounded-lg cursor-pointer transition-colors ${
      selected ? 'bg-teal-50 border border-teal-200' : 'hover:bg-gray-50 border border-transparent'
    }`} onClick={() => onClick(account)} data-testid={`account-card-${account.id}`}>
      <div className="flex items-center gap-3">
        <img src={account.avatar} alt={account.username}
          className="w-10 h-10 rounded-full object-cover bg-gray-100"
          onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${account.username}`; }} />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-gray-900 truncate">{account.username}</div>
          <div className="text-gray-500 text-sm truncate">{account.handle}</div>
        </div>
      </div>
      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
        <span>{account.followers} followers</span>
        {account.signalScore > 0 && (
          <span className="font-medium text-gray-700">Score: {account.signalScore}</span>
        )}
        {account.hitRate > 0 && (
          <span className={`font-medium ${account.hitRate >= 60 ? 'text-emerald-600' : 'text-gray-500'}`}>
            Hit: {account.hitRate}%
          </span>
        )}
      </div>
      {sent && (
        <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-between">
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${getLabelBg(label)}`}>{label}</span>
          <div className="flex items-center gap-2">
            <span className={`text-xs flex items-center gap-0.5 ${delta24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {delta24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {delta24h >= 0 ? '+' : ''}{Math.round(delta24h * 100)}%
            </span>
            <Sparkline data={sent.history} width={50} height={16} />
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================
// Filter button
// ============================================
const FilterButton = ({ active, onClick, children }) => (
  <Button variant={active ? 'default' : 'outline'} size="sm" onClick={onClick}
    className={`transition-all duration-150 ${active 
      ? 'bg-teal-500 hover:bg-teal-600 text-white' 
      : 'border-gray-300 text-gray-600 hover:bg-gray-50 hover:border-gray-400'
    }`}>
    {children}
  </Button>
);

// ============================================
// Main component
// ============================================
export default function TwitterSentimentPage() {
  const [accounts, setAccounts] = useState([]);
  const [tweets, setTweets] = useState([]);
  const [trendingKeywords, setTrendingKeywords] = useState([]);
  const [topSignals, setTopSignals] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [selectedTweet, setSelectedTweet] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [showLowImpact, setShowLowImpact] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchSource, setSearchSource] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [parserActive, setParserActive] = useState(false);
  const [proxyInfo, setProxyInfo] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  // New states
  const [sidebarTab, setSidebarTab] = useState('accounts');
  const [myKeywords, setMyKeywords] = useState([]);
  const [newKeyword, setNewKeyword] = useState('');
  const [addingKeyword, setAddingKeyword] = useState(false);
  const [extStatus, setExtStatus] = useState({ hasExtension: false, limits: { accounts: 2, keywords: 2 } });
  const [myAccountIds, setMyAccountIds] = useState([]);

  useEffect(() => {
    fetchAccounts();
    fetchTweets();
    fetchTrendingKeywords();
    fetchTopSignals();
    checkParserStatus();
    fetchMyKeywords();
    fetchExtensionStatus();
    fetchMyAccountIds();
  }, []);

  const fetchAccounts = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/accounts`);
      const data = await res.json();
      if (data.ok && data.data) setAccounts(data.data);
    } catch (err) { console.error('Failed to fetch accounts:', err); }
  };

  const fetchTweets = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/feed?limit=50`);
      const data = await res.json();
      if (data.ok && data.data) setTweets(data.data);
    } catch (err) { console.error('Failed to fetch tweets:', err); }
    finally { setLoading(false); }
  };

  const fetchTrendingKeywords = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/live-trending`);
      const data = await res.json();
      if (data.ok && data.data) setTrendingKeywords(data.data);
    } catch (err) { console.error('Failed to fetch trending keywords:', err); }
  };

  const fetchTopSignals = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/top-signals`);
      const data = await res.json();
      if (data.ok && data.data) setTopSignals(data.data);
    } catch (err) { console.error('Failed to fetch top signals:', err); }
  };

  const checkParserStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/search-status`);
      const data = await res.json();
      if (data.ok) {
        setParserActive(data.sessionActive);
        setProxyInfo(data.proxies);
      }
    } catch (err) { console.error(err); }
  };

  const fetchMyKeywords = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/my-keywords`);
      const data = await res.json();
      if (data.ok) setMyKeywords(data.keywords || []);
    } catch (err) { console.error(err); }
  };

  const addMyKeyword = async () => {
    const kw = newKeyword.trim();
    if (!kw) return;
    if (myKeywords.length >= extStatus.limits.keywords) return;
    setAddingKeyword(true);
    try {
      await fetch(`${API_URL}/api/v4/sentiment/my-keywords`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: kw }),
      });
      setNewKeyword('');
      await fetchMyKeywords();
    } catch (err) { console.error(err); }
    finally { setAddingKeyword(false); }
  };

  const deleteMyKeyword = async (keyword) => {
    try {
      await fetch(`${API_URL}/api/v4/sentiment/my-keywords?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE' });
      await fetchMyKeywords();
    } catch (err) { console.error(err); }
  };

  const fetchExtensionStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/user/extension-status`);
      const data = await res.json();
      if (data.ok) setExtStatus(data);
    } catch (err) { console.error('Extension status error:', err); }
  };

  const fetchMyAccountIds = async () => {
    try {
      const res = await fetch(`${API_URL}/api/user/my-accounts`);
      const data = await res.json();
      if (data.ok) setMyAccountIds(data.accounts || []);
    } catch (err) { console.error(err); }
  };

  const addMyAccount = async (accountId) => {
    if (myAccountIds.length >= extStatus.limits.accounts) return;
    try {
      const res = await fetch(`${API_URL}/api/user/my-accounts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId }),
      });
      const data = await res.json();
      if (data.ok) setMyAccountIds(data.accounts);
    } catch (err) { console.error(err); }
  };

  const removeMyAccount = async (accountId) => {
    try {
      const res = await fetch(`${API_URL}/api/user/my-accounts?id=${encodeURIComponent(accountId)}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.ok) setMyAccountIds(data.accounts);
    } catch (err) { console.error(err); }
  };

  const handleSearch = async (query) => {
    const q = (query || searchQuery).trim();
    if (!q) { setSearchResults(null); setSearchError(null); return; }
    setSearching(true);
    setSearchError(null);
    setSearchSource(null);
    try {
      const res = await fetch(`${API_URL}/api/v4/sentiment/twitter-search?q=${encodeURIComponent(q)}&count=20`);
      const data = await res.json();
      if (data.ok) {
        setSearchResults(data.tweets || []);
        setSearchSource(data.source);
        if (data.error) setSearchError(data.error);
        // Показать прокси инфо
        if (data.proxy_used) setSearchError(prev => prev ? `${prev} (proxy: ${data.proxy_used})` : null);
      } else {
        setSearchError(data.error || 'Ошибка поиска');
        setSearchResults([]);
      }
    } catch (err) {
      setSearchError('Ошибка сети');
      setSearchResults([]);
    } finally { setSearching(false); }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
    setSearchError(null);
    setSearchSource(null);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  // Typeahead — live подсказки при вводе
  const typeaheadTimeout = React.useRef(null);
  const fetchTypeahead = (q) => {
    if (typeaheadTimeout.current) clearTimeout(typeaheadTimeout.current);
    if (!q || q.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    typeaheadTimeout.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/api/v4/sentiment/typeahead?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (data.ok) {
          setSuggestions(data.users || []);
          setShowSuggestions(true);
        }
      } catch (err) { console.error(err); }
    }, 300);
  };

  const selectSuggestion = (user) => {
    const accountId = `twitter:${user.username}`;
    if (myAccountIds.length < extStatus.limits.accounts && !myAccountIds.includes(accountId)) {
      addMyAccount(accountId);
    }
    setSearchQuery(`@${user.username}`);
    setShowSuggestions(false);
    handleSearch(`@${user.username}`);
  };

  // Build tracked handle set for filtering
  const trackedHandleSet = new Set(
    myAccountIds.map(id => id.replace('twitter:', '').toLowerCase())
  );
  const trackedKeywordSet = new Set(
    myKeywords.map(kw => kw.keyword.toLowerCase())
  );

  const filteredTweets = tweets.filter(tweet => {
    // Only show tweets from tracked accounts or matching tracked keywords
    const tweetHandle = (tweet.accountId || tweet.handle || '').replace('@', '').toLowerCase();
    const isTrackedAccount = trackedHandleSet.has(tweetHandle);
    const isTrackedKeyword = tweet.source === 'keyword' && trackedKeywordSet.has((tweet.keyword || '').toLowerCase());
    
    if (!isTrackedAccount && !isTrackedKeyword) return false;

    if (selectedAccount) {
      const accHandle = selectedAccount.handle?.replace('@', '').toLowerCase();
      if (tweetHandle !== accHandle) return false;
    }
    // Source filters
    if (filter === 'keywords' && tweet.source !== 'keyword') return false;
    if (filter === 'accounts' && tweet.source === 'keyword') return false;
    // Sentiment/impact filters
    if (filter === 'positive' && tweet.sentiment.label !== 'POSITIVE') return false;
    if (filter === 'neutral' && tweet.sentiment.label !== 'NEUTRAL') return false;
    if (filter === 'negative' && tweet.sentiment.label !== 'NEGATIVE') return false;
    if (filter === 'high-impact' && tweet.impact !== 'HIGH') return false;
    if (filter === 'with-signal' && !tweet.signal) return false;
    return true;
  });

  // Separate by impact
  const highImpactTweets = filteredTweets.filter(t => t.impact === 'HIGH');
  const mediumImpactTweets = filteredTweets.filter(t => t.impact === 'MEDIUM');
  const lowImpactTweets = filteredTweets.filter(t => t.impact === 'LOW');

  const handleTweetClick = (tweet) => {
    setSelectedTweet(tweet);
    setModalOpen(true);
  };

  const handleRefresh = async () => {
    await Promise.all([fetchTweets(), fetchAccounts(), fetchTrendingKeywords(), fetchTopSignals(), fetchMyKeywords()]);
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="twitter-sentiment-page">
      <div className="flex">
        <aside className="w-80 bg-white border-r border-gray-200 min-h-screen p-4">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold text-gray-900">Search</h2>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); setShowSuggestions(false); handleSearch(); }} className="relative" data-testid="search-form">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Keyword, #hashtag or @account..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); fetchTypeahead(e.target.value); }}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                className="pl-9 pr-20"
                data-testid="account-search-input"
              />
              <div className="absolute right-1 top-1/2 -translate-y-1/2 flex gap-1">
                {searchQuery && (
                  <button type="button" onClick={clearSearch} className="p-1.5 text-gray-400 hover:text-gray-600">
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
                <button type="submit" disabled={searching || !searchQuery.trim()}
                  className="px-2 py-1 bg-gray-900 text-white rounded text-xs font-medium disabled:opacity-40 hover:bg-gray-700 transition-colors"
                  data-testid="search-submit-btn">
                  {searching ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Go'}
                </button>
              </div>

              {/* Typeahead подсказки */}
              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-50 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden" data-testid="typeahead-dropdown">
                  {suggestions.map((u) => (
                    <button key={u.id || u.username} type="button"
                      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors text-left"
                      onClick={() => selectSuggestion(u)}
                      data-testid={`suggestion-${u.username}`}>
                      <img src={u.avatar} alt="" className="w-8 h-8 rounded-full bg-gray-100 flex-shrink-0"
                        onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${u.username}`; }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-sm font-medium text-gray-900 truncate">{u.name}</span>
                          {u.verified && <span className="text-blue-500 text-xs">✓</span>}
                        </div>
                        <span className="text-xs text-gray-400">@{u.username}</span>
                      </div>
                      <span className="text-[10px] text-gray-400 flex-shrink-0">{u.followers > 1000 ? `${(u.followers/1000).toFixed(0)}K` : u.followers}</span>
                    </button>
                  ))}
                </div>
              )}
            </form>
            {searchError && searchError !== 'HTTP_404' && (
              <p className="text-[10px] text-amber-600 mt-1">{searchError === 'AUTH_EXPIRED' ? 'Сессия Twitter устарела' : searchError}</p>
            )}
            {searchSource === 'database' && searchResults && (
              <p className="text-[10px] text-gray-400 mt-1">Found in database ({searchResults.length})</p>
            )}
            {searchSource === 'database_cache' && searchResults && (
              <p className="text-[10px] text-gray-400 mt-1">Cached ({searchResults.length})</p>
            )}
            {searchSource === 'search_api' && searchResults && (
              <p className="text-[10px] text-emerald-600 mt-1">Live API ({searchResults.length} tweets)</p>
            )}
            {searchSource === 'playwright' && searchResults && (
              <p className="text-[10px] text-emerald-600 mt-1">Live browser ({searchResults.length} tweets)</p>
            )}
            {searchSource === 'live' && searchResults && (
              <p className="text-[10px] text-emerald-600 mt-1">Live ({searchResults.length} tweets)</p>
            )}
            {searchSource === 'api' && searchResults && (
              <p className="text-[10px] text-emerald-600 mt-1">Live ({searchResults.length} tweets)</p>
            )}
            {!searchSource && searchResults && (
              <p className="text-[10px] text-emerald-600 mt-1">Results ({searchResults.length})</p>
            )}
          </div>

          {/* Результаты поиска */}
          {searchResults !== null ? (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-700">Results: "{searchQuery}"</h3>
                <button onClick={clearSearch} className="text-xs text-gray-400 hover:text-gray-600">Clear</button>
              </div>
              {searchResults.length === 0 ? (
                <p className="text-sm text-gray-400 py-4 text-center">No results found</p>
              ) : (
                <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                  {searchResults.map((t, i) => (
                    <div key={t.tweetId || i} className="rounded-lg border border-gray-100 bg-gray-50 p-3 hover:bg-white transition-colors cursor-pointer"
                      onClick={() => { setSelectedTweet({ id: t.tweetId, text: t.text, handle: `@${t.username}`, username: t.displayName || t.username, avatar: t.avatar, likes: t.likes, reposts: t.reposts, replies: t.replies, views: t.views, sentiment: { label: 'NEUTRAL', score: 0.5 } }); setModalOpen(true); }}
                      data-testid={`search-result-${i}`}>
                      <div className="flex items-start gap-2">
                        {t.avatar ? (
                          <img src={t.avatar} alt="" className="w-7 h-7 rounded-full" onError={(e) => { e.target.style.display = 'none'; }} />
                        ) : (
                          <div className="w-7 h-7 rounded-full bg-gray-200 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-gray-900 truncate">{t.displayName || t.username}</span>
                            <span className="text-[10px] text-gray-400">@{t.username}</span>
                          </div>
                          <p className="text-xs text-gray-600 mt-0.5 line-clamp-3">{t.text}</p>
                          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-gray-400">
                            {t.likes > 0 && <span>{t.likes} likes</span>}
                            {t.reposts > 0 && <span>{t.reposts} RT</span>}
                            {t.views > 0 && <span>{t.views} views</span>}
                            {t.keyword && <span className="text-teal-600 font-medium">{t.keyword}</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Sidebar tabs: Accounts | My Keywords */}
              <div className="flex border-b border-gray-200 mb-3" data-testid="sidebar-tabs">
                <button
                  onClick={() => setSidebarTab('accounts')}
                  className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
                    sidebarTab === 'accounts'
                      ? 'text-gray-900 border-b-2 border-gray-900'
                      : 'text-gray-400 hover:text-gray-600'
                  }`}
                  data-testid="tab-accounts"
                >
                  <User className="w-3 h-3 inline mr-1" />Accounts
                </button>
                <button
                  onClick={() => setSidebarTab('keywords')}
                  className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
                    sidebarTab === 'keywords'
                      ? 'text-gray-900 border-b-2 border-gray-900'
                      : 'text-gray-400 hover:text-gray-600'
                  }`}
                  data-testid="tab-keywords"
                >
                  <Hash className="w-3 h-3 inline mr-1" />My Keywords
                </button>
              </div>

              {sidebarTab === 'accounts' ? (
                <>
                  {/* Limit indicator */}
                  <div className="flex items-center justify-between mb-2 px-1">
                    <span className="text-[10px] text-gray-400">
                      {myAccountIds.length} / {extStatus.limits.accounts} accounts
                    </span>
                    {!extStatus.hasExtension && (
                      <span className="text-[10px] text-amber-500">Free plan</span>
                    )}
                  </div>

                  {/* User's tracked accounts only */}
                  {myAccountIds.length > 0 ? (
                    <div className="space-y-1">
                      {accounts.filter(a => myAccountIds.includes(a.id)).map(account => (
                        <div key={account.id} className="group relative">
                          <AccountCard account={account}
                            selected={selectedAccount?.id === account.id} onClick={setSelectedAccount} />
                          <button
                            onClick={(e) => { e.stopPropagation(); removeMyAccount(account.id); }}
                            className="absolute top-2 right-2 p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all"
                            data-testid={`remove-account-${account.id}`}
                            title="Remove"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-gray-400 text-xs">
                      <User className="w-5 h-5 mx-auto mb-1 text-gray-300" />
                      <p>No tracked accounts</p>
                      <p className="text-[10px] mt-1">Search and add accounts to start tracking</p>
                    </div>
                  )}

                  {/* Add prompt when under limit */}
                  {myAccountIds.length < extStatus.limits.accounts && myAccountIds.length > 0 && (
                    <p className="text-[10px] text-gray-400 mt-2 px-1">
                      Search above to add more accounts ({extStatus.limits.accounts - myAccountIds.length} remaining)
                    </p>
                  )}

                  {/* Limit reached banner */}
                  {myAccountIds.length >= extStatus.limits.accounts && !extStatus.hasExtension && (
                    <div className="mt-3 p-3 bg-amber-50 rounded-lg text-xs text-amber-700" data-testid="account-limit-banner">
                      <p className="font-medium mb-1">Limit reached ({extStatus.limits.accounts}/{extStatus.limits.accounts})</p>
                      <p className="text-amber-600">Install extension for up to 30</p>
                    </div>
                  )}

                  {selectedAccount && (
                    <Button variant="ghost" size="sm" className="w-full mt-4 text-gray-500"
                      onClick={() => setSelectedAccount(null)}>Clear selection</Button>
                  )}
                </>
              ) : (
                <div data-testid="my-keywords-section">
                  {/* Limit indicator */}
                  <div className="flex items-center justify-between mb-2 px-1">
                    <span className="text-[10px] text-gray-400">
                      {myKeywords.length} / {extStatus.limits.keywords} keywords
                    </span>
                    {!extStatus.hasExtension && (
                      <span className="text-[10px] text-amber-500">Free plan</span>
                    )}
                  </div>

                  {/* Add keyword form */}
                  <form onSubmit={(e) => { e.preventDefault(); addMyKeyword(); }} className="flex gap-1.5 mb-3">
                    <Input
                      placeholder="Add keyword..."
                      value={newKeyword}
                      onChange={(e) => setNewKeyword(e.target.value)}
                      className="text-xs h-8"
                      disabled={myKeywords.length >= extStatus.limits.keywords}
                      data-testid="add-keyword-input"
                    />
                    <Button type="submit" size="sm" disabled={addingKeyword || !newKeyword.trim() || myKeywords.length >= extStatus.limits.keywords}
                      className="h-8 px-2 bg-gray-900 hover:bg-gray-700"
                      data-testid="add-keyword-btn">
                      {addingKeyword ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                    </Button>
                  </form>

                  {/* Limit reached banner */}
                  {myKeywords.length >= extStatus.limits.keywords && !extStatus.hasExtension && (
                    <div className="mb-3 p-2.5 bg-amber-50 rounded-lg text-xs text-amber-700" data-testid="keyword-limit-banner">
                      <p className="font-medium">Keyword limit reached</p>
                      <p className="text-amber-600 mt-0.5">Install extension for up to 30 keywords</p>
                    </div>
                  )}

                  {/* Saved keywords list */}
                  {myKeywords.length === 0 ? (
                    <div className="py-6 text-center text-gray-400 text-xs">
                      <Hash className="w-5 h-5 mx-auto mb-1 text-gray-300" />
                      No saved keywords yet
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {myKeywords.map((kw) => (
                        <div key={kw.keyword}
                          className="flex items-center gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-white transition-colors group"
                          data-testid={`my-kw-${kw.keyword}`}>
                          <Hash className="w-3 h-3 text-teal-500 flex-shrink-0" />
                          <button
                            className="flex-1 text-left text-xs font-medium text-gray-700 hover:text-gray-900 truncate"
                            onClick={() => { setSearchQuery(kw.keyword); handleSearch(kw.keyword); }}
                          >
                            {kw.keyword}
                          </button>
                          {kw.resultCount > 0 && (
                            <span className="text-[10px] text-gray-400">{kw.resultCount}</span>
                          )}
                          <button
                            onClick={() => deleteMyKeyword(kw.keyword)}
                            className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            data-testid={`delete-kw-${kw.keyword}`}
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          <div className="mt-6">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Trending Keywords</h3>
            <div className="flex flex-wrap gap-2">
              {trendingKeywords.map(item => (
                <Badge key={item.keyword} variant="secondary"
                  className="bg-gray-100 text-gray-700 hover:bg-gray-200 cursor-pointer text-xs"
                  onClick={() => { setSearchQuery(item.keyword); handleSearch(item.keyword); }}
                  data-testid={`keyword-${item.keyword}`}>
                  {item.keyword} <span className="ml-1 text-gray-400">{item.count}</span>
                </Badge>
              ))}
            </div>
          </div>
        </aside>

        <main className="flex-1 min-w-0 p-6">
          <div className="mb-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                {['all', 'keywords', 'accounts', 'high-impact', 'with-signal', 'positive', 'neutral', 'negative'].map(f => (
                  <FilterButton key={f} active={filter === f} onClick={() => setFilter(f)}>
                    {f === 'all' ? 'All' : f === 'keywords' ? 'Keywords' : f === 'accounts' ? 'Accounts' : f === 'high-impact' ? 'High Impact' : f === 'with-signal' ? 'With Signal' : f.charAt(0).toUpperCase() + f.slice(1)}
                  </FilterButton>
                ))}
              </div>
              <Button variant="outline" onClick={handleRefresh} disabled={loading} data-testid="refresh-button">
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />Refresh
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <Card key={i} className="bg-white"><CardContent className="p-4">
                  <div className="flex items-start gap-3"><Skeleton className="w-10 h-10 rounded-full" />
                    <div className="flex-1 space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-full" /></div>
                  </div></CardContent></Card>
              ))}
            </div>
          ) : filteredTweets.length === 0 ? (
            <Card className="border-gray-100">
              <CardContent className="py-12 text-center">
                <Inbox className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <h3 className="text-gray-900 font-medium mb-1">
                  {myAccountIds.length === 0 && myKeywords.length === 0
                    ? 'Add accounts or keywords to start'
                    : 'No posts matching your tracked sources'
                  }
                </h3>
                <p className="text-gray-500 text-sm mb-4">
                  {myAccountIds.length === 0 && myKeywords.length === 0
                    ? 'Search for an account or add a keyword in the sidebar'
                    : 'Try adjusting filters or wait for new posts'
                  }
                </p>
                {filter !== 'all' && (
                  <Button variant="outline" size="sm" onClick={() => setFilter('all')}>Clear filters</Button>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* HIGH impact — full cards */}
              {highImpactTweets.map(tweet => (
                <HighImpactTweetCard key={tweet.id} tweet={tweet} onClick={handleTweetClick} />
              ))}

              {/* MEDIUM — normal cards */}
              {mediumImpactTweets.map(tweet => (
                <MediumTweetCard key={tweet.id} tweet={tweet} onClick={handleTweetClick} />
              ))}

              {/* LOW impact — collapsed */}
              {lowImpactTweets.length > 0 && (
                <div className="mt-2">
                  <button
                    onClick={() => setShowLowImpact(!showLowImpact)}
                    className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-2"
                    data-testid="toggle-low-impact"
                  >
                    <ChevronDown className={`w-4 h-4 transition-transform ${showLowImpact ? 'rotate-180' : ''}`} />
                    Low impact ({lowImpactTweets.length})
                  </button>
                  {showLowImpact && (
                    <Card className="bg-white/50 border-gray-100">
                      <CardContent className="p-2 divide-y divide-gray-50">
                        {lowImpactTweets.map(tweet => (
                          <LowTweetCard key={tweet.id} tweet={tweet} onClick={handleTweetClick} />
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      <TweetDetailModal tweet={selectedTweet} open={modalOpen} onClose={setModalOpen} />
    </div>
  );
}
