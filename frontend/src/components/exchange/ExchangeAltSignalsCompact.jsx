/**
 * ExchangeAltSignalsCompact — Compact two-column BUY/SELL alt signals
 * 
 * Data: /api/market/exchange/top-alts-v2
 * Format: Strong BUYs (left) | Strong SELLs (right)
 * Max 10 per side, clickable rows
 */

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const RISK_STYLE = {
  LOW:     'bg-emerald-50 text-emerald-700',
  MEDIUM:  'bg-amber-50 text-amber-700',
  HIGH:    'bg-orange-50 text-orange-700',
  EXTREME: 'bg-red-50 text-red-700',
};

function getRisk(flags) {
  if (!flags?.length) return 'LOW';
  if (flags.includes('SAFE_MODE')) return 'EXTREME';
  if (flags.length >= 2) return 'HIGH';
  return 'MEDIUM';
}

export default function ExchangeAltSignalsCompact({
  horizon = '7D',
  onSelectSymbol,
  selectedSymbol,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/market/exchange/top-alts-v2?horizon=${horizon}&limit=20`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok) {
        setData(json);
        setUpdatedAt(new Date());
      }
    } catch (e) {
      console.error('[ExchangeAltSignals] Error:', e);
    } finally {
      setLoading(false);
    }
  }, [horizon]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="exchange-alt-signals">
        <div className="flex items-center gap-2 text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading signals...</span>
        </div>
      </div>
    );
  }

  if (!data?.rows?.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 text-center" data-testid="exchange-alt-signals">
        <p className="text-gray-400 text-sm">No exchange signals available</p>
      </div>
    );
  }

  const { rows, uriLevel, safeMode, activeCount } = data;
  const buys = rows.filter(r => r.direction === 'LONG').slice(0, 10);
  const sells = rows.filter(r => r.direction === 'SHORT').slice(0, 10);
  const hasSells = sells.length > 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="exchange-alt-signals">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Exchange Alt Signals
        </div>
        <div className="flex items-center gap-2">
          {safeMode && (
            <span className="text-[10px] font-semibold text-amber-800">
              SAFE
            </span>
          )}
          <span className={`text-[10px] font-semibold ${
            uriLevel === 'OK' ? 'text-emerald-700' :
            uriLevel === 'WARN' ? 'text-amber-700' :
            'text-red-700'
          }`}>
            {uriLevel}
          </span>
          <span className="text-xs text-gray-400">
            {activeCount} assets
          </span>
          {loading && <RefreshCw className="w-3 h-3 animate-spin text-gray-400" />}
        </div>
      </div>

      {/* Two-column layout */}
      <div className={`grid ${hasSells ? 'grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-100' : 'grid-cols-1'}`}>
        {/* BUYs */}
        <div>
          <div className="px-4 py-2 text-xs font-medium text-emerald-700" style={{ background: 'rgba(16,185,129,0.06)' }}>
            Strong BUYs
          </div>
          <SignalList
            items={buys}
            type="BUY"
            selectedSymbol={selectedSymbol}
            onSelect={onSelectSymbol}
          />
          {buys.length === 0 && (
            <div className="px-4 py-4 text-xs text-gray-400 text-center">No BUY signals</div>
          )}
        </div>

        {/* SELLs — only if present */}
        {hasSells && (
          <div>
            <div className="px-4 py-2 text-xs font-medium text-red-700" style={{ background: 'rgba(239,68,68,0.05)' }}>
              Strong SELLs
            </div>
            <SignalList
              items={sells}
              type="SELL"
              selectedSymbol={selectedSymbol}
              onSelect={onSelectSymbol}
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <span className="text-[11px] text-gray-400">
          {updatedAt ? `Updated: ${updatedAt.toLocaleTimeString()}` : ''}
        </span>
        <span className="text-[11px] text-gray-400">
          Click row to view chart
        </span>
      </div>
    </div>
  );
}

function SignalList({ items, type, selectedSymbol, onSelect }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-[11px] text-gray-400 uppercase">
        <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
          <th className="text-left py-1.5 px-4 font-medium">Symbol</th>
          <th className="text-right py-1.5 px-3 font-medium">Conf</th>
          <th className="text-right py-1.5 px-3 font-medium">Move</th>
          <th className="text-center py-1.5 px-3 font-medium">Risk</th>
        </tr>
      </thead>
      <tbody>
        {items.map((row) => {
          const isSelected = selectedSymbol === row.symbol;
          const conf = Math.round((row.confidenceFinal || 0) * 100);
          const move = row.expectedMovePctFinal || 0;
          const risk = getRisk(row.flags);

          return (
            <tr
              key={row.symbol}
              onClick={() => onSelect?.(row.symbol)}
              className={`cursor-pointer transition-colors ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'}`}
              style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}
              data-testid={`exchange-signal-${row.symbol}`}
            >
              <td className="py-2 px-4">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900">{row.symbol}</span>
                  <span className={`text-[10px] font-bold ${
                    type === 'BUY'
                      ? 'text-emerald-600'
                      : 'text-red-600'
                  }`}>
                    {type}
                  </span>
                </div>
              </td>
              <td className="py-2 px-3 text-right tabular-nums font-medium text-gray-700">
                {conf}%
              </td>
              <td className={`py-2 px-3 text-right tabular-nums font-medium ${
                move >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}>
                {move >= 0 ? '+' : ''}{move.toFixed(2)}%
              </td>
              <td className="py-2 px-3 text-center">
                <span className={`text-[10px] font-semibold ${
                  risk === 'LOW' ? 'text-emerald-700' :
                  risk === 'MEDIUM' ? 'text-amber-700' :
                  risk === 'HIGH' ? 'text-orange-700' :
                  'text-red-700'
                }`}>
                  {risk}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
