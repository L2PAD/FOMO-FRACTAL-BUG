/**
 * URL <-> Filters codec
 */
import { DEFAULT_FILTERS } from './telegramFilters';

function csv(arr) {
  if (!arr?.length) return undefined;
  return arr.join(',');
}

function parseCsv(v) {
  if (!v) return [];
  const s = Array.isArray(v) ? v[0] : v;
  return s.split(',').map(x => x.trim()).filter(Boolean);
}

function num(v) {
  if (!v) return null;
  const s = Array.isArray(v) ? v[0] : v;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function str(v) {
  if (!v) return undefined;
  return Array.isArray(v) ? v[0] : v;
}

export function filtersToQuery(f) {
  const q = {};
  
  if (f.q) q.q = f.q;
  
  if (f.lang?.length) q.lang = csv(f.lang);
  if (f.tier?.length) q.tier = csv(f.tier);
  if (f.lifecycle?.length) q.lifecycle = csv(f.lifecycle);
  if (f.group?.length) q.group = csv(f.group);
  if (f.type?.length) q.type = csv(f.type);
  if (f.segment?.length) q.segment = csv(f.segment);
  
  if (f.minMembers != null) q.minMembers = String(f.minMembers);
  if (f.maxMembers != null) q.maxMembers = String(f.maxMembers);
  if (f.minReach != null) q.minReach = String(f.minReach);
  if (f.maxReach != null) q.maxReach = String(f.maxReach);
  if (f.minGrowth7 != null) q.minGrowth7 = String(f.minGrowth7);
  if (f.maxGrowth7 != null) q.maxGrowth7 = String(f.maxGrowth7);
  if (f.minPostsPerDay != null) q.minPostsPerDay = String(f.minPostsPerDay);
  if (f.maxPostsPerDay != null) q.maxPostsPerDay = String(f.maxPostsPerDay);
  if (f.maxFraud != null) q.maxFraud = String(f.maxFraud);
  if (f.minCrypto != null) q.minCrypto = String(f.minCrypto);
  
  if (f.sort) q.sort = f.sort;
  if (f.order) q.order = f.order;
  if (f.page != null) q.page = String(f.page);
  if (f.limit != null) q.limit = String(f.limit);
  
  return q;
}

export function queryToFilters(query) {
  const f = { ...DEFAULT_FILTERS };
  
  f.q = str(query.q) || '';
  
  f.lang = parseCsv(query.lang);
  f.tier = parseCsv(query.tier);
  f.lifecycle = parseCsv(query.lifecycle);
  f.group = parseCsv(query.group);
  f.type = parseCsv(query.type);
  f.segment = parseCsv(query.segment);
  
  f.minMembers = num(query.minMembers);
  f.maxMembers = num(query.maxMembers);
  f.minReach = num(query.minReach);
  f.maxReach = num(query.maxReach);
  f.minGrowth7 = num(query.minGrowth7);
  f.maxGrowth7 = num(query.maxGrowth7);
  f.minPostsPerDay = num(query.minPostsPerDay);
  f.maxPostsPerDay = num(query.maxPostsPerDay);
  f.maxFraud = num(query.maxFraud);
  f.minCrypto = num(query.minCrypto);
  
  f.sort = str(query.sort) || 'utility';
  f.order = str(query.order) || 'desc';
  f.page = num(query.page) || 1;
  f.limit = num(query.limit) || 50;
  
  return f;
}
