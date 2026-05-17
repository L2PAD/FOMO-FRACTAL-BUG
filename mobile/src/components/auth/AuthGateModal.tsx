/**
 * AuthGateModal — mobile stub (pass-through).
 * Real implementation is in AuthGateModal.web.tsx.
 */
import React from 'react';

export interface AuthGateModalProps {
  open: boolean;
  onClose: () => void;
  surface?: string;
  blockKey?: string;
  onSuccess?: () => void;
}

export default function AuthGateModal(_: AuthGateModalProps) {
  return null;
}
