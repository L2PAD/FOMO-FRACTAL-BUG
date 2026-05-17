/**
 * Loading Card Component
 * =======================
 */

import React from 'react';

interface LoadingCardProps {
  title: string;
}

export default function LoadingCard({ title }: LoadingCardProps) {
  return (
    <div className="bg-white rounded-xl p-4 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-5 w-32 bg-gray-200 rounded" />
        <div className="h-6 w-16 bg-gray-200 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-3/4 bg-gray-100 rounded" />
        <div className="h-4 w-1/2 bg-gray-100 rounded" />
        <div className="h-4 w-2/3 bg-gray-100 rounded" />
      </div>
    </div>
  );
}
