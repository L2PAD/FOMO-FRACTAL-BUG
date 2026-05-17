/**
 * Exit Types
 */

export type ExitAction = 'HOLD' | 'TRIM' | 'REDUCE' | 'EXIT';

export interface ExitPlan {
  action: ExitAction;
  confidence: number;         // 0–1
  reasons: string[];
}
