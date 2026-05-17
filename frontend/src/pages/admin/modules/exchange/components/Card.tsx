/**
 * Card Component (Light Theme)
 * =============================
 * 
 * BLOCK E6: Base card component for Exchange Admin
 */

import React from 'react';

interface CardProps {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}

export default function Card({ title, children, right }: CardProps) {
  return (
    <div className="bg-white rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {right && <div>{right}</div>}
      </div>
      {children}
    </div>
  );
}
