/**
 * Error Card Component
 * =====================
 */

import React from 'react';

interface ErrorCardProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorCard({ title, message, onRetry }: ErrorCardProps) {
  return (
    <div className="bg-white border border-red-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-red-700">{title}</h3>
      </div>
      <p className="text-sm text-red-600 mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1.5 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
