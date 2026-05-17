/**
 * Leaderboard Pagination (Block UI-1)
 */
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function LeaderboardPagination({ page, pages, total, limit, onPageChange }) {
  if (pages <= 1) return null;

  const canPrev = page > 1;
  const canNext = page < pages;

  const start = (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);

  return (
    <div className="flex items-center justify-between bg-white border border-gray-200 rounded-xl px-4 py-3" data-testid="pagination">
      <div className="text-sm text-gray-500">
        Showing <span className="font-medium">{start}</span> to <span className="font-medium">{end}</span> of{' '}
        <span className="font-medium">{total}</span> channels
      </div>
      
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={!canPrev}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          data-testid="prev-page-btn"
        >
          <ChevronLeft className="w-4 h-4" />
          Prev
        </button>
        
        <span className="px-3 py-1.5 text-sm font-medium text-gray-700">
          {page} / {pages}
        </span>
        
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={!canNext}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          data-testid="next-page-btn"
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
