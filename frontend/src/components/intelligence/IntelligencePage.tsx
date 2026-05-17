/**
 * Intelligence Page Framework
 * ============================
 * Reusable layout for all analytical pages:
 * Token Intelligence, Entities, Graph, etc.
 *
 * Structure: Header → Narrative → Row blocks (3-col grid)
 */

import React from 'react';

interface IntelligencePageProps {
  header?: React.ReactNode;
  narrative?: React.ReactNode;
  rows: React.ReactNode[][];
  footer?: React.ReactNode;
}

export function IntelligencePage({ header, narrative, rows, footer }: IntelligencePageProps) {
  return (
    <div className="space-y-4" data-testid="intelligence-page">
      {header}
      {narrative}
      {rows.map((row, i) => (
        <IntelligenceRow key={i} blocks={row} />
      ))}
      {footer}
    </div>
  );
}

function IntelligenceRow({ blocks }: { blocks: React.ReactNode[] }) {
  const cols = blocks.length;
  const gridClass =
    cols === 1 ? 'grid-cols-1' :
    cols === 2 ? 'grid-cols-1 lg:grid-cols-2' :
    'grid-cols-1 lg:grid-cols-3';

  return (
    <div className={`grid ${gridClass} gap-4`}>
      {blocks.map((block, i) => (
        <React.Fragment key={i}>{block}</React.Fragment>
      ))}
    </div>
  );
}

export function IntelligenceBlock({ children, dark, className, testId }: {
  children: React.ReactNode;
  dark?: boolean;
  className?: string;
  testId?: string;
}) {
  return (
    <div
      className={`rounded-2xl p-5 ${dark ? 'bg-gray-900 text-white intelligence-dark' : 'bg-white text-gray-900'} ${className || ''}`}
      data-testid={testId}
    >
      {children}
    </div>
  );
}
