import { useCallback } from "react";
import { getSentimentAdminSnapshot, getSentimentIntelligenceData } from "../lib/adminSentimentApi";
import { SentimentAdminSnapshot, SentimentIntelligenceData } from "../types/sentimentAdmin.types";
import { usePolling } from "./usePolling";

export function useSentimentAdminStatus(opts?: { pollMs?: number }) {
  const pollMs = opts?.pollMs ?? 15000;

  const fetcher = useCallback(() => getSentimentAdminSnapshot(), []);

  return usePolling<SentimentAdminSnapshot>(fetcher, pollMs);
}

export function useSentimentIntelligence(opts?: { pollMs?: number }) {
  const pollMs = opts?.pollMs ?? 30000; // Less frequent polling for intelligence data

  const fetcher = useCallback(() => getSentimentIntelligenceData(), []);

  return usePolling<SentimentIntelligenceData | null>(fetcher, pollMs);
}
