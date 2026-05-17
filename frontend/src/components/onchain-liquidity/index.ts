/**
 * OnChain Liquidity Module Exports
 * =================================
 * 
 * PHASE 3 + BLOCK 3.6: Alt Liquidity Signal components
 * BLOCK 8: LARE v2 UI Discipline
 */

// LARE v2 (New - BLOCK 8)
export { LareV2Panel } from './LareV2Panel';
export { LareV2Header } from './LareV2Header';
export { LareV2Components } from './LareV2Components';
export { LareV2Drivers } from './LareV2Drivers';
export { LareV2DataFlag } from './LareV2DataFlag';
export { LareV2Chart } from './LareV2Chart';
export { useLareV2 } from './useLareV2';

// Legacy (v1)
export { AltLiquidityPanel } from './AltLiquidityPanel';
export { AltLiquidityCard } from './AltLiquidityCard';
export { AltLiquidityChart } from './AltLiquidityChart';
export { AltLiquidityDrivers } from './AltLiquidityDrivers';
export { AltLiquidityFlags } from './AltLiquidityFlags';
export { AltLiquidityInputs } from './AltLiquidityInputs';
export { AltFlowTable } from './AltFlowTable';
export { useAltLiquidity } from './useAltLiquidity';
export { useAltFlow } from './useAltFlow';
export * from './types';
export * from './ui';
