import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export default function PortfolioBreakdown({ assets }) {
  const [expandedRows, setExpandedRows] = useState([]);
  const [filter, setFilter] = useState('ALL');

  const toggleRow = (asset) => {
    setExpandedRows(prev =>
      prev.includes(asset) ? prev.filter(a => a !== asset) : [...prev, asset]
    );
  };

  const filteredAssets = assets.filter(asset => {
    if (filter === 'ALL') return true;
    if (filter === 'WINNERS') return asset.pnl > 0;
    if (filter === 'LOSERS') return asset.pnl < 0;
    if (filter === 'CORE') return asset.allocation_pct > 20;
    return true;
  });

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg p-3" data-testid="portfolio-breakdown">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Portfolio Breakdown</h3>
          <p className="text-xs text-gray-500">Current asset composition and contribution</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-1">
          {['ALL', 'WINNERS', 'LOSERS', 'CORE'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-0.5 text-xs font-medium rounded-lg transition-colors ${
                filter === f
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              data-testid={`filter-${f}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#E5E7EB]">
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Asset</th>
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Category</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Held</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Invested</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Avg Price</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Current</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Value</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">PnL</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">%</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-500 uppercase">Allocation</th>
            </tr>
          </thead>
          <tbody>
            {filteredAssets.map((asset) => {
              const isExpanded = expandedRows.includes(asset.asset);
              
              return (
                <React.Fragment key={`asset-${asset.asset}`}>
                  <tr
                    className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => toggleRow(asset.asset)}
                    data-testid={`asset-row-${asset.asset}`}
                  >
                  <td className="py-2 px-2">
                    <div className="flex items-center gap-1.5">
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3 text-gray-400" />
                      ) : (
                        <ChevronRight className="w-3 h-3 text-gray-400" />
                      )}
                      <span className="font-semibold text-gray-900">{asset.asset}</span>
                    </div>
                  </td>
                  <td className="py-2 px-2 text-gray-600">{asset.category}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-900">{asset.amount}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-900">${asset.invested.toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-900">${asset.avg_entry.toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-900">${asset.current_price.toLocaleString()}</td>
                  <td className="py-2 px-2 text-right font-mono font-semibold text-gray-900">${asset.current_value.toLocaleString()}</td>
                  <td className={`py-2 px-2 text-right font-mono font-semibold ${
                    asset.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {asset.pnl >= 0 ? '+' : ''}${asset.pnl.toLocaleString()}
                  </td>
                  <td className={`py-2 px-2 text-right font-mono font-semibold ${
                    asset.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {asset.pnl_pct >= 0 ? '+' : ''}{asset.pnl_pct.toFixed(2)}%
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-gray-600">{asset.allocation_pct.toFixed(1)}%</td>
                </tr>

                {/* Expanded Details */}
                {isExpanded && (
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <td colSpan="10" className="py-3 px-6">
                      <div className="grid grid-cols-5 gap-4 text-xs">
                        <div>
                          <div className="text-xs text-gray-500 mb-1">Trade Count</div>
                          <div className="font-mono font-semibold text-gray-900">{asset.trade_count}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">Win / Loss</div>
                          <div className="font-mono font-semibold text-gray-900">{asset.win_count} / {asset.loss_count}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">Avg Trade PnL</div>
                          <div className={`font-mono font-semibold ${
                            asset.avg_trade_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {asset.avg_trade_pnl >= 0 ? '+' : ''}${asset.avg_trade_pnl.toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">Best Trade</div>
                          <div className="font-mono font-semibold text-green-600">+${asset.best_trade.toLocaleString()}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">Worst Trade</div>
                          <div className="font-mono font-semibold text-red-600">${asset.worst_trade.toLocaleString()}</div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
