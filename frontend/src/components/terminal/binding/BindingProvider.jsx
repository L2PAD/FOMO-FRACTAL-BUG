/**
 * Binding Provider - Context for chart ↔ panel linking
 * ====================================================
 * 
 * Manages hover and selection state for bidirectional binding
 */

'use client'

import { createContext, useContext, useMemo, useState } from 'react';

const BindingContext = createContext(null);

export function BindingProvider({ children }) {
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);

  const clearHovered = () => setHovered(null);
  const clearSelected = () => setSelected(null);

  const value = useMemo(
    () => ({
      hovered,
      selected,
      setHovered,
      setSelected,
      clearHovered,
      clearSelected,
    }),
    [hovered, selected]
  );

  return (
    <BindingContext.Provider value={value}>
      {children}
    </BindingContext.Provider>
  );
}

export function useBinding() {
  const ctx = useContext(BindingContext);
  if (!ctx) {
    throw new Error('useBinding must be used inside BindingProvider');
  }
  return ctx;
}
