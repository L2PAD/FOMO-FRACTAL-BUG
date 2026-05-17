/**
 * Terminal Guard — Sprint 3: Loading & Error states
 * 
 * Wraps terminal content with:
 * - Loading timeout (10s → error state)
 * - Empty state messaging
 * - API error fallback
 */
import { useState, useEffect } from 'react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';

export function LoadingGuard({ loading, error, children, timeout = 10000, emptyMessage = "No data available" }) {
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!loading) {
      setTimedOut(false);
      return;
    }
    const timer = setTimeout(() => setTimedOut(true), timeout);
    return () => clearTimeout(timer);
  }, [loading, timeout]);

  if (loading && timedOut) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400" data-testid="loading-timeout">
        <AlertCircle size={24} className="text-yellow-500 mb-2" />
        <div className="text-sm font-medium text-yellow-400">Loading taking longer than expected</div>
        <div className="text-xs text-gray-500 mt-1">Service may be unavailable</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="loading-spinner">
        <Loader2 size={20} className="animate-spin text-gray-400" />
        <span className="ml-2 text-sm text-gray-500">Loading...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400" data-testid="error-state">
        <AlertCircle size={24} className="text-red-400 mb-2" />
        <div className="text-sm text-red-400">Connection issue</div>
        <div className="text-xs text-gray-500 mt-1">System will retry automatically</div>
      </div>
    );
  }

  return children;
}

export function EmptyState({ icon: Icon = AlertCircle, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center" data-testid="empty-state">
      <Icon size={28} className="text-gray-600 mb-3" />
      <div className="text-sm font-medium text-gray-400">{title}</div>
      {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
    </div>
  );
}
