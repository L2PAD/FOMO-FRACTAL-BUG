/**
 * MODULE CONTROLLER SERVICE
 * =========================
 * 
 * Reads system_feature_flags from MongoDB.
 * Provides API for MetaBrain to query module state.
 * 
 * MetaBrain calls:
 *   getActiveModules()
 *   getModuleMode(moduleName)
 *   isModuleEnabled(moduleName)
 * 
 * Admin UI calls:
 *   getAllModules()
 *   updateModule(name, patch)
 */

import { getDb } from '../../../db/mongodb.js';

export type ModuleMode = 'live' | 'snapshot' | 'off';

export interface ModuleFlag {
  module: string;
  enabled: boolean;
  mode: ModuleMode;
  weight: number;
  weightOverride: number | null;
  maxSnapshotAgeHours: number;
  lastUpdated: string;
}

const COLLECTION = 'system_feature_flags';

const DEFAULT_MODULES: ModuleFlag[] = [
  { module: 'exchange',  enabled: true,  mode: 'live',     weight: 0.38, weightOverride: null, maxSnapshotAgeHours: 24, lastUpdated: new Date().toISOString() },
  { module: 'fractal',   enabled: true,  mode: 'live',     weight: 0.30, weightOverride: null, maxSnapshotAgeHours: 24, lastUpdated: new Date().toISOString() },
  { module: 'onchain',   enabled: true,  mode: 'snapshot', weight: 0.20, weightOverride: null, maxSnapshotAgeHours: 24, lastUpdated: new Date().toISOString() },
  { module: 'sentiment', enabled: true,  mode: 'live',     weight: 0.12, weightOverride: null, maxSnapshotAgeHours: 24, lastUpdated: new Date().toISOString() },
];

function col() {
  return getDb().collection<ModuleFlag>(COLLECTION);
}

/**
 * Initialize default modules if collection is empty.
 */
export async function initModuleFlags(): Promise<void> {
  const count = await col().countDocuments();
  if (count === 0) {
    await col().insertMany(DEFAULT_MODULES);
    console.log('[ModuleController] Initialized default feature flags');
  }
}

/**
 * Get all modules (for admin UI).
 */
export async function getAllModules(): Promise<ModuleFlag[]> {
  const docs = await col().find({}, { projection: { _id: 0 } }).toArray();
  if (docs.length === 0) {
    await initModuleFlags();
    return col().find({}, { projection: { _id: 0 } }).toArray();
  }
  return docs;
}

/**
 * Get only active (enabled) modules.
 * MetaBrain uses this to decide which providers to call.
 */
export async function getActiveModules(): Promise<ModuleFlag[]> {
  const all = await getAllModules();
  return all.filter(m => m.enabled && m.mode !== 'off');
}

/**
 * Get single module state.
 */
export async function getModuleState(moduleName: string): Promise<ModuleFlag | null> {
  return col().findOne({ module: moduleName }, { projection: { _id: 0 } });
}

/**
 * Check if module is enabled and not OFF.
 */
export async function isModuleEnabled(moduleName: string): Promise<boolean> {
  const m = await getModuleState(moduleName);
  return m ? m.enabled && m.mode !== 'off' : false;
}

/**
 * Get module mode.
 */
export async function getModuleMode(moduleName: string): Promise<ModuleMode> {
  const m = await getModuleState(moduleName);
  return m?.mode ?? 'off';
}

/**
 * Update module settings (from admin UI).
 */
export async function updateModule(
  moduleName: string,
  patch: Partial<Pick<ModuleFlag, 'enabled' | 'mode' | 'weightOverride' | 'maxSnapshotAgeHours'>>
): Promise<ModuleFlag | null> {
  const update: Record<string, any> = { lastUpdated: new Date().toISOString() };
  if (patch.enabled !== undefined) update.enabled = patch.enabled;
  if (patch.mode !== undefined) update.mode = patch.mode;
  if (patch.weightOverride !== undefined) update.weightOverride = patch.weightOverride;
  if (patch.maxSnapshotAgeHours !== undefined) update.maxSnapshotAgeHours = patch.maxSnapshotAgeHours;

  await col().updateOne(
    { module: moduleName },
    { $set: update }
  );

  return getModuleState(moduleName);
}
