/**
 * P1 <GatedBlock> — Platform-split wrapper.
 * 
 * On iOS/Android → renders children as-is (pass-through).
 * On Web (see GatedBlock.web.tsx) → checks access store and renders either
 *   children or a locked placeholder + CTA that opens AuthGateModal.
 */
import React from 'react';

export interface GatedBlockProps {
  blockKey: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  /** Optional — forces a specific CTA label (usually backend provides it). */
  ctaOverride?: string;
  /** Analytics — which surface this block appears on. */
  surface?: string;
}

export default function GatedBlock({ children }: GatedBlockProps) {
  // Mobile: pass-through. Mobile already has its own FREE/PRO logic.
  return <>{children}</>;
}
