/**
 * Credibility Combined Page — Bakery wrapper
 * Renders BakeryPage (list) or BakerDetailPage (detail) based on URL params
 * Uses useSearchParams for reactive URL-based rendering
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import BakeryPage from '../connections/BakeryPage';
import BakerDetailPage from '../connections/BakerDetailPage';

export default function CredibilityCombinedPage() {
  const [searchParams] = useSearchParams();
  const bakerSlug = searchParams.get('baker');

  return (
    <div data-testid="credibility-combined-page">
      {bakerSlug ? <BakerDetailPage slugOverride={bakerSlug} /> : <BakeryPage />}
    </div>
  );
}
