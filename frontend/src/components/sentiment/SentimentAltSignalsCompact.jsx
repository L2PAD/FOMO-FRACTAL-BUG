/**
 * SentimentAltSignalsCompact — Two-column BUY/SELL sentiment signals
 * Same visual format as Exchange and On-chain alt signals
 * Data: /api/market/sentiment/top-alts-v2
 */

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SentimentAltSignalsCompact({
  windowKey = '7D',
  onSelectSymbol,
  selectedSymbol,
}) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [safeMode, setSafeMode] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/market/sentiment/top-alts-v2?windowKey=${windowKey}&limit=20`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok !== false) {
        setRows(json.rows || []);
        setSafeMode(!!json.safeMode);
        setUpdatedAt(new Date());
      }
    } catch (e) {
      console.error('[SentimentAltSignals] Error:', e);
    } finally {
      setLoading(false);
    }
  }, [windowKey]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading && !rows.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="sentiment-alt-signals">
        <div className="flex items-center gap-2 text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading signals...</span>
        </div>
      </div>
    );
  }

  const buys = rows.filter(r => r.direction === 'LONG').slice(0, 10);
  const sells = rows.filter(r => r.direction === 'SHORT').slice(0, 10);
  const hasSells = sells.length > 0;
  const count = buys.length + sells.length;
  const maxRows = Math.max(buys.length, sells.length);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="sentiment-alt-signals">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Sentiment Signals</span>
          {safeMode && <span className="text-[10px] text-amber-600 font-medium">SAFE MODE</span>}
        </div>
        <div className="flex items-center gap-2">
          {loading && <RefreshCw className="w-3 h-3 animate-spin text-gray-400" />}
          <span className="text-xs text-gray-400">{count} active</span>
        </div>
      </div>

      {count === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-gray-400">
          No active sentiment signals — all assets NEUTRAL
        </div>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <th colSpan={4} className="text-left px-4 py-2 text-xs font-medium text-emerald-700" style={{ background: 'rgba(16,185,129,0.06)' }}>
                Strong BUYs
              </th>
              {hasSells && (
                <th colSpan={4} className="text-left px-4 py-2 text-xs font-medium text-red-700" style={{ background: 'rgba(239,68,68,0.05)' }}>
                  Strong SELLs
                </th>
              )}
            </tr>
            <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <th className="text-left py-1.5 px-4 font-medium text-[11px] text-gray-400 uppercase">Symbol</th>
              <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Conf</th>
              <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Move</th>
              <th className="text-center py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Score</th>
              {hasSells && (
                <>
                  <th className="text-left py-1.5 px-4 font-medium text-[11px] text-gray-400 uppercase">Symbol</th>
                  <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Conf</th>
                  <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Move</th>
                  <th className="text-center py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Score</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: maxRows }).map((_, i) => {
              const buy = buys[i];
              const sell = sells[i];
              return (
                <tr key={i} style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
                  {buy ? (
                    <>
                      <td className={`py-2 px-4 cursor-pointer hover:bg-gray-50 ${selectedSymbol === buy.symbol ? 'bg-blue-50' : ''}`} onClick={() => onSelectSymbol?.(buy.symbol)}>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900">{buy.symbol}</span>
                          <span className="text-[10px] font-bold text-emerald-600">BUY</span>
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums font-medium text-gray-700">
                        {Math.round((buy.confidenceFinal || 0) * 100)}%
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums font-medium text-emerald-600">
                        +{(buy.expectedMovePctFinal || 0).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 text-center tabular-nums text-gray-600">
                        {((buy.score || 0) * 100).toFixed(0)}%
                      </td>
                    </>
                  ) : <td colSpan={4}></td>}
                  {hasSells && (sell ? (
                    <>
                      <td className={`py-2 px-4 cursor-pointer hover:bg-gray-50 ${selectedSymbol === sell.symbol ? 'bg-blue-50' : ''}`} onClick={() => onSelectSymbol?.(sell.symbol)}>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900">{sell.symbol}</span>
                          <span className="text-[10px] font-bold text-red-600">SELL</span>
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums font-medium text-gray-700">
                        {Math.round((sell.confidenceFinal || 0) * 100)}%
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums font-medium text-red-600">
                        {(sell.expectedMovePctFinal || 0).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 text-center tabular-nums text-gray-600">
                        {((sell.score || 0) * 100).toFixed(0)}%
                      </td>
                    </>
                  ) : <td colSpan={4}></td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <span className="text-[11px] text-gray-400">
          {updatedAt ? `Updated: ${updatedAt.toLocaleTimeString()}` : ''}
        </span>
        <span className="text-[11px] text-gray-400">Click row to view chart</span>
      </div>
    </div>
  );
}
