/**
 * SentimentForecastCard — Sentiment-specific forecast display
 * ============================================================
 * 
 * Shows forecast data specifically from Sentiment module API,
 * not from the general Verdict Engine / Meta-Brain.
 * 
 * Used when Sentiment layer is active on the Prediction page.
 */

import React, { useEffect, useState } from 'react';
import { TrendingUpIcon, TrendingDownIcon, MinusIcon, ShieldAlert, RefreshCwIcon, AlertTriangle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function windowKeyToHorizon(windowKey) {
  if (windowKey === '24H' || windowKey === '1D') return '24H';
  if (windowKey === '30D') return '30D';
  return '7D';
}

function horizonLabel(horizon) {
  if (horizon === '24H') return '24H FORECAST';
  if (horizon === '7D') return '7 DAY FORECAST';
  if (horizon === '30D') return '30 DAY FORECAST';
  return `${horizon} FORECAST`;
}

export default function SentimentForecastCard({ 
  symbol = 'BTC', 
  windowKey = '24H',
  currentPrice,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const horizon = windowKeyToHorizon(windowKey);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/market/chart/sentiment-v2?symbol=${symbol}&horizon=${horizon}`)
      .then(r => r.json())
      .then(res => {
        if (!alive) return;
        if (res.ok) {
          setData(res);
        } else {
          setError(res.error || 'Failed to load sentiment forecast');
        }
        setLoading(false);
      })
      .catch(err => {
        if (!alive) return;
        setError(err.message);
        setLoading(false);
      });

    return () => { alive = false; };
  }, [symbol, horizon]);

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-cyan-50/50 to-teal-50/50 border border-cyan-100 rounded-xl p-4">
        <div className="flex items-center gap-2 text-cyan-600">
          <RefreshCwIcon className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading sentiment forecast...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <div className="flex items-center gap-2 text-gray-500">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">{error || 'No sentiment data'}</span>
        </div>
      </div>
    );
  }

  const { forecast, meta, reliability } = data;
  const { safeMode, uriLevel } = meta;
  const { rawConfidence, finalConfidence, uriMultiplier, calibrationMultiplier, capitalMultiplier } = reliability;
  
  // Use horizon from API response for accurate label
  const actualHorizon = meta.horizon || horizon;

  const isUp = forecast.direction === 'LONG';
  const isDown = forecast.direction === 'SHORT';
  const isNeutral = forecast.direction === 'NEUTRAL';

  // Calculate target time
  const horizonMs = {
    '24H': 24 * 60 * 60 * 1000,
    '7D': 7 * 24 * 60 * 60 * 1000,
    '30D': 30 * 24 * 60 * 60 * 1000,
  };
  const targetTime = new Date(Date.now() + (horizonMs[actualHorizon] || horizonMs['24H']));

  // Kelly-based position sizing
  const confidence = finalConfidence;
  const rewardRisk = Math.abs(forecast.expectedMovePct) / 0.02; // Assume 2% stop
  const kellyFraction = Math.max(0, (confidence * rewardRisk - (1 - confidence)) / rewardRisk);
  const suggestedSize = Math.min(25, Math.round(kellyFraction * 100 * 0.5)); // Half-Kelly, max 25%

  // Direction badge color
  const directionColor = safeMode 
    ? 'text-amber-600' 
    : isUp 
      ? 'text-emerald-600' 
      : isDown 
        ? 'text-red-600' 
        : 'text-gray-500';

  const directionBg = safeMode
    ? 'bg-amber-50 border-amber-200'
    : isUp
      ? 'bg-emerald-50 border-emerald-200'
      : isDown
        ? 'bg-red-50 border-red-200'
        : 'bg-gray-50 border-gray-200';

  return (
    <div 
      className={`rounded-xl border p-4 ${
        safeMode 
          ? 'bg-gradient-to-r from-amber-50/50 to-orange-50/50 border-amber-200' 
          : 'bg-gradient-to-r from-cyan-50/50 to-teal-50/50 border-cyan-100'
      }`}
      data-testid="sentiment-forecast-card"
    >
      {/* Header — unified single row */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-sm font-medium text-gray-600">Sentiment</span>
        {!safeMode && isUp
          ? <TrendingUpIcon className="w-4 h-4 text-emerald-600" />
          : !safeMode && isDown
            ? <TrendingDownIcon className="w-4 h-4 text-red-600" />
            : <MinusIcon className="w-4 h-4 text-gray-400" />
        }
        <span
          className={`text-sm font-bold ${
            !safeMode && isUp ? 'text-emerald-600'
              : !safeMode && isDown ? 'text-red-600'
              : 'text-gray-500'
          }`}
        >
          {!safeMode && isUp ? 'Bullish'
            : !safeMode && isDown ? 'Bearish'
            : 'HOLD'}
        </span>
        <span className="text-sm font-medium text-gray-500">
          {(finalConfidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Main forecast info */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Target price */}
        <div>
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">
            {horizonLabel(actualHorizon)}
          </div>
          <div className="flex items-center gap-2">
            {isUp && !safeMode && <TrendingUpIcon className="w-5 h-5 text-emerald-600" />}
            {isDown && !safeMode && <TrendingDownIcon className="w-5 h-5 text-red-600" />}
            {(isNeutral || safeMode) && <MinusIcon className="w-5 h-5 text-gray-400" />}
            <span className="text-2xl font-bold text-gray-900">
              ${forecast.target?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </span>
            <span className={`text-sm font-semibold px-2 py-0.5 rounded-lg ${
              forecast.expectedMovePct > 0 && !safeMode
                ? 'text-emerald-600 bg-emerald-50' 
                : forecast.expectedMovePct < 0 && !safeMode
                  ? 'text-red-600 bg-red-50' 
                  : 'text-gray-500 bg-gray-50'
            }`}>
              {forecast.expectedMovePct > 0 ? '+' : ''}{(forecast.expectedMovePct * 100).toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Confidence */}
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">CONFIDENCE</div>
          <div className="flex items-center gap-1.5 justify-end">
            <div className={`text-xl font-bold ${
              finalConfidence === 0 ? 'text-amber-600' : 'text-gray-900'
            }`}>
              {(finalConfidence * 100).toFixed(0)}%
            </div>
            {rawConfidence !== finalConfidence && (
              <span className="text-[11px] text-gray-400 line-through">
                {(rawConfidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {/* Band */}
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-right">
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">BAND</div>
              <div className="text-sm text-gray-600 font-medium">
                ${forecast.bandLow?.toLocaleString(undefined, { maximumFractionDigits: 0 })} — ${forecast.bandHigh?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            </TooltipTrigger>
            <TooltipContent className="bg-gray-900 text-white border-gray-800">
              <p className="text-xs">Expected price range based on volatility</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {/* Position Size */}
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-right">
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">POSITION SIZE</div>
              <div className={`text-lg font-bold ${
                suggestedSize >= 15 ? 'text-emerald-600' : 
                suggestedSize >= 8 ? 'text-amber-600' : 'text-red-500'
              }`}>
                {suggestedSize}%
              </div>
              <div className="text-[10px] text-gray-400">Kelly-based</div>
            </TooltipTrigger>
            <TooltipContent className="bg-gray-900 text-white border-gray-800">
              <p className="text-xs">Recommended position size using Half-Kelly criterion</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {/* Evaluate at */}
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">EVALUATE AT</div>
          <div className="text-sm text-gray-600 font-medium">
            {targetTime.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Applied Multipliers */}
      <div className="mt-3 pt-3 border-t border-gray-200/50">
        <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wide font-medium">APPLIED MULTIPLIERS</div>
        <div className="flex flex-wrap gap-2">
          {uriMultiplier !== 1 && (
            <span className="px-2.5 py-1 bg-indigo-50 border border-indigo-100 rounded-lg text-[10px] text-indigo-700">
              URI: ×{uriMultiplier.toFixed(2)}
            </span>
          )}
          {calibrationMultiplier !== 1 && (
            <span className="px-2.5 py-1 bg-blue-50 border border-blue-100 rounded-lg text-[10px] text-blue-700">
              Calibration: ×{calibrationMultiplier.toFixed(2)}
            </span>
          )}
          {capitalMultiplier !== 1 && (
            <span className="px-2.5 py-1 bg-purple-50 border border-purple-100 rounded-lg text-[10px] text-purple-700">
              Capital: ×{capitalMultiplier.toFixed(2)}
            </span>
          )}
          {safeMode && (
            <span className="px-2.5 py-1 bg-amber-50 border border-amber-100 rounded-lg text-[10px] text-amber-700">
              SafeMode: confidence → 0
            </span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-3 pt-2 border-t border-gray-200/30 text-[10px] text-gray-400 flex items-center justify-between">
        <span>Source: Sentiment Module</span>
        <span>Current: ${currentPrice?.toLocaleString() || forecast.entry?.toLocaleString()}</span>
      </div>
    </div>
  );
}
