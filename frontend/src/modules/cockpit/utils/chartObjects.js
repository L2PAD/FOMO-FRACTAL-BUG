/**
 * Object Types and Contracts for Chart Rendering
 * ================================================
 * 
 * Frontend renders ONLY from these objects.
 * NO manual pattern drawing.
 */

export const ObjectCategory = {
  PATTERN: "pattern",
  LEVEL: "level",
  STRUCTURE: "structure",
  LIQUIDITY: "liquidity",
  INDICATOR: "indicator",
  HYPOTHESIS: "hypothesis",
  TRADING: "trading",
};

export const ObjectType = {
  // Pattern
  CHANNEL: "CHANNEL",
  TRIANGLE: "TRIANGLE",
  WEDGE: "WEDGE",
  RANGE_BOX: "RANGE_BOX",
  
  // Level
  HORIZONTAL_LEVEL: "HORIZONTAL_LEVEL",
  SUPPORT_CLUSTER: "SUPPORT_CLUSTER",
  RESISTANCE_CLUSTER: "RESISTANCE_CLUSTER",
  FIBONACCI: "FIBONACCI",
  
  // Structure
  STRUCTURE_POINT: "STRUCTURE_POINT",
  BOS_MARKER: "BOS_MARKER",
  CHOCH_MARKER: "CHOCH_MARKER",
  
  // Indicator
  EMA_SERIES: "EMA_SERIES",
  SMA_SERIES: "SMA_SERIES",
  BOLLINGER_BAND: "BOLLINGER_BAND",
  RSI_SERIES: "RSI_SERIES",
  
  // Hypothesis
  HYPOTHESIS_PATH: "HYPOTHESIS_PATH",
  CONFIDENCE_CORRIDOR: "CONFIDENCE_CORRIDOR",
  
  // Trading
  ENTRY_ZONE: "ENTRY_ZONE",
  STOP_LOSS: "STOP_LOSS",
  TAKE_PROFIT: "TAKE_PROFIT",
  INVALIDATION_LINE: "INVALIDATION_LINE",
};

/**
 * Filter objects by Research mode
 */
export const filterResearchObjects = (objects) => {
  const researchCategories = [
    ObjectCategory.PATTERN,
    ObjectCategory.LEVEL,
    ObjectCategory.STRUCTURE,
    ObjectCategory.LIQUIDITY,
    ObjectCategory.INDICATOR,
  ];
  return objects.filter(obj => researchCategories.includes(obj.category));
};

/**
 * Filter objects by Hypothesis mode
 */
export const filterHypothesisObjects = (objects) => {
  const hypothesisCategories = [
    ObjectCategory.PATTERN,
    ObjectCategory.HYPOTHESIS,
  ];
  return objects.filter(obj => hypothesisCategories.includes(obj.category));
};

/**
 * Filter objects by Trading mode
 */
export const filterTradingObjects = (objects) => {
  const tradingCategories = [
    ObjectCategory.TRADING,
    ObjectCategory.LEVEL,
  ];
  return objects.filter(obj => tradingCategories.includes(obj.category));
};

/**
 * Sort objects by priority (lower = render first = below)
 */
export const sortByPriority = (objects) => {
  return [...objects].sort((a, b) => a.priority - b.priority);
};

/**
 * Filter by layer toggles
 */
export const filterByLayers = (objects, layers) => {
  return objects.filter(obj => {
    if (obj.category === ObjectCategory.PATTERN && !layers.patterns) return false;
    if (obj.category === ObjectCategory.LEVEL && !layers.levels) return false;
    if (obj.category === ObjectCategory.STRUCTURE && !layers.structure) return false;
    if (obj.category === ObjectCategory.HYPOTHESIS && !layers.hypothesis) return false;
    if (obj.category === ObjectCategory.TRADING && !layers.trading) return false;
    return true;
  });
};
