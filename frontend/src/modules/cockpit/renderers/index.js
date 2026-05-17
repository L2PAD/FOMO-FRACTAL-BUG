/**
 * Render Plan Renderers
 * =====================
 * 
 * Component library for rendering render_plan v2 with 6 layers.
 * 
 * LAYERS:
 * A. Market State (context, NOT pattern)
 * B. Structure (swings, CHOCH, BOS)
 * C. Indicators (overlays, panes)
 * D. Pattern Figures (ONLY real patterns - NO channels/trends)
 * E. Liquidity (EQH/EQL, sweeps, OB)
 * F. Execution (ALWAYS visible)
 * 
 * RENDER MODES:
 * - figure_mode: Focus on pattern figure
 * - range_mode: Focus on range boundaries (NO pattern card)
 * - structure_mode: Focus on structure
 * 
 * Key principle: 1 graph = 1 setup = 1 story
 */

export { MarketStateRenderer } from './MarketStateRenderer.jsx';
export { ExecutionRenderer } from './ExecutionRenderer.jsx';
export { PatternRenderer } from './PatternRenderer.jsx';
export { PatternStatusRenderer } from './PatternStatusRenderer.jsx';
export { POIRenderer } from './POIRenderer.jsx';
export { StructureRenderer } from './StructureRenderer.jsx';
export { LiquidityRenderer } from './LiquidityRenderer.jsx';
export { RangeContextRenderer } from './RangeContextRenderer.jsx';
export { ChainHighlightRenderer } from './ChainHighlightRenderer.jsx';
export { RenderPlanOverlay } from './RenderPlanOverlay.jsx';
