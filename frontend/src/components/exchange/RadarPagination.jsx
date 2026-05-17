/**
 * Radar Pagination — minimal, dense, matches control bar style
 */
import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function RadarPagination({ page, pages, total, limit, onPageChange }) {
  if (pages <= 1) return null;
  const from = (page - 1) * limit + 1;
  const to = Math.min(page * limit, total);

  const pageNums = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || (i >= page - 1 && i <= page + 1)) {
      pageNums.push(i);
    } else if (pageNums[pageNums.length - 1] !== '...') {
      pageNums.push('...');
    }
  }

  return (
    <div data-testid="radar-pagination" className="flex items-center justify-between px-4 mt-4" style={{ maxWidth: '1200px' }}>
      <span className="text-[12px] tabular-nums" style={{ color: '#94a3b8' }}>{from}-{to} of {total}</span>
      <div className="flex items-center gap-1">
        <button data-testid="radar-page-prev" onClick={() => onPageChange(page - 1)} disabled={page <= 1}
          className="p-1 rounded transition-colors disabled:opacity-30" style={{ color: '#64748b' }}>
          <ChevronLeft className="w-4 h-4" />
        </button>
        {pageNums.map((n, i) =>
          n === '...' ? (
            <span key={`dot-${i}`} className="text-[12px] px-1" style={{ color: '#94a3b8' }}>...</span>
          ) : (
            <button key={n} data-testid={`radar-page-${n}`} onClick={() => onPageChange(n)}
              className="text-[12px] font-medium rounded transition-colors"
              style={{
                minWidth: '28px', height: '28px',
                color: n === page ? '#0f172a' : '#94a3b8',
                background: n === page ? 'rgba(15,23,42,0.06)' : 'transparent',
                fontWeight: n === page ? 600 : 400,
              }}>
              {n}
            </button>
          )
        )}
        <button data-testid="radar-page-next" onClick={() => onPageChange(page + 1)} disabled={page >= pages}
          className="p-1 rounded transition-colors disabled:opacity-30" style={{ color: '#64748b' }}>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
