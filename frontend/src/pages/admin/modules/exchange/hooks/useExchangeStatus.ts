/**
 * Exchange Admin Status Hook
 * ===========================
 * 
 * BLOCK E6: Hook for fetching Exchange admin snapshot with polling
 */

import { usePolling } from './usePolling';
import { getExchangeAdminSnapshot } from '../lib/adminExchangeApi';
import { ExchangeAdminSnapshot } from '../types/exchangeAdmin.types';

export function useExchangeAdminStatus(opts?: { pollMs?: number }) {
  return usePolling<ExchangeAdminSnapshot>(getExchangeAdminSnapshot, opts?.pollMs ?? 15000);
}
