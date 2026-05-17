/**
 * Research Tabs — Export Index
 * =============================
 * 
 * 5 cognitive layers:
 * - Overview: Що відбувається
 * - Structure: Як устроєний ринок
 * - Signals: Чому так думаємо
 * - Execution: Що робити
 * - DeepDive: Деталі (advanced)
 */

export { default as OverviewTab } from './OverviewTab';
export { default as StructureTab } from './StructureTab';
export { default as SignalsTab } from './SignalsTab';
export { default as ExecutionTab } from './ExecutionTab';
export { default as DeepDiveTab } from './DeepDiveTab';

// Tab configuration
export const RESEARCH_TABS = [
  { id: 'overview', label: 'Overview', description: 'Що відбувається' },
  { id: 'structure', label: 'Structure', description: 'Як устроєний ринок' },
  { id: 'signals', label: 'Signals', description: 'Чому так думаємо' },
  { id: 'execution', label: 'Execution', description: 'Що робити' },
  { id: 'deep', label: 'Deep', description: 'Деталі' },
];
