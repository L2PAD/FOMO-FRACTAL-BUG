/**
 * Radar Table — Main data table for Spot/Alpha/Futures
 */
import React from 'react';
import { ChevronUp, ChevronDown, Minus, Info, Copy } from 'lucide-react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../components/ui/table';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../../components/ui/tooltip';

const VERDICT_COLORS = {
  buy: 'text-emerald-600',
  sell: 'text-red-500',
  watch: 'text-amber-500',
  neutral: 'text-gray-400',
};

const RISK_COLORS = {
  low: 'text-emerald-600',
  medium: 'text-amber-500',
  high: 'text-red-500',
};

function DirectionIcon({ dir }) {
  if (dir === 'long') return <ChevronUp className="w-3.5 h-3.5 text-emerald-600 inline" />;
  if (dir === 'short') return <ChevronDown className="w-3.5 h-3.5 text-red-500 inline" />;
  return <Minus className="w-3.5 h-3.5 text-gray-400 inline" />;
}

export default function RadarTable({ rows, onRowClick, mode }) {
  const handleCopy = (e, sym) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sym);
  };

  if (!rows.length) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm" data-testid="radar-empty">
        No signals match current filters
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="overflow-x-auto" data-testid="radar-table">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px] text-xs text-gray-500 font-medium">Asset</TableHead>
              <TableHead className="w-[80px] text-xs text-gray-500 font-medium">Direction</TableHead>
              <TableHead className="w-[80px] text-xs text-gray-500 font-medium">Verdict</TableHead>
              <TableHead className="w-[80px] text-xs text-gray-500 font-medium">Conviction</TableHead>
              <TableHead className="text-xs text-gray-500 font-medium">Why now</TableHead>
              <TableHead className="w-[70px] text-xs text-gray-500 font-medium">Risk</TableHead>
              <TableHead className="w-[60px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(row => (
              <TableRow
                key={row.symbol}
                data-testid={`radar-row-${row.symbol}`}
                onClick={() => onRowClick(row)}
                className="cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <TableCell className="py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-gray-900">{row.symbol.replace('USDT', '')}</span>
                    {row.venue === 'alpha' && (
                      <span className="text-[10px] text-purple-600">Alpha</span>
                    )}
                    {mode === 'futures' && row.squeezeRisk === 'high' && (
                      <span className="text-[10px] text-red-500">SQ</span>
                    )}
                  </div>
                </TableCell>

                <TableCell className="py-3">
                  <span className="text-sm flex items-center gap-1">
                    <DirectionIcon dir={row.direction} />
                    <span className={`capitalize ${row.direction === 'long' ? 'text-emerald-600' : row.direction === 'short' ? 'text-red-500' : 'text-gray-400'}`}>
                      {row.direction}
                    </span>
                  </span>
                </TableCell>

                <TableCell className="py-3">
                  <span className={`text-sm font-medium uppercase ${VERDICT_COLORS[row.verdict]}`}>
                    {row.verdict}
                  </span>
                </TableCell>

                <TableCell className="py-3">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          row.conviction >= 60 ? 'bg-emerald-500' :
                          row.conviction >= 45 ? 'bg-amber-400' : 'bg-gray-300'
                        }`}
                        style={{ width: `${row.conviction}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-gray-600">{row.conviction}</span>
                  </div>
                </TableCell>

                <TableCell className="py-3">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="text-xs text-gray-500 line-clamp-1 max-w-[260px] block">
                        {row.whyNow}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs text-xs">
                      {row.whyNow}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>

                <TableCell className="py-3">
                  <span className={`text-xs font-medium capitalize ${RISK_COLORS[row.riskLevel]}`}>
                    {row.riskLevel}
                  </span>
                </TableCell>

                <TableCell className="py-3">
                  <div className="flex items-center gap-1">
                    <button
                      data-testid={`radar-info-${row.symbol}`}
                      onClick={(e) => { e.stopPropagation(); onRowClick(row); }}
                      className="p-1 rounded hover:bg-gray-100 transition-colors"
                    >
                      <Info className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                    <button
                      data-testid={`radar-copy-${row.symbol}`}
                      onClick={(e) => handleCopy(e, row.symbol)}
                      className="p-1 rounded hover:bg-gray-100 transition-colors"
                    >
                      <Copy className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  );
}
