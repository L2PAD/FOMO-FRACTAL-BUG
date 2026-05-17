"use client";

import React from "react";

interface AdminGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4;
}

/**
 * Responsive Admin Grid
 * - ≥1600px → 4 columns
 * - ≥1200px → 3 columns  
 * - ≥768px → 2 columns
 * - <768px → 1 column
 */
export default function AdminGrid({ children, columns }: AdminGridProps) {
  return (
    <div
      className="grid gap-4"
      style={{
        gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
      }}
    >
      {children}
    </div>
  );
}

/**
 * Full-width row wrapper for panels that need more space
 */
export function AdminRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="col-span-full">
      {children}
    </div>
  );
}

/**
 * Two-column row for balanced panels
 */
export function AdminRow2({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {children}
    </div>
  );
}

/**
 * Three-column row
 */
export function AdminRow3({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {children}
    </div>
  );
}
