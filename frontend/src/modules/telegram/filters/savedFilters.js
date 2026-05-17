/**
 * Saved Filters (localStorage)
 */
const KEY = 'tg_saved_filters_v1';

export function loadSaved() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveSaved(list) {
  localStorage.setItem(KEY, JSON.stringify(list.slice(0, 30)));
}

export function addSaved(name, filters) {
  const list = loadSaved();
  const item = {
    id: crypto.randomUUID?.() || Date.now().toString(),
    name,
    filters,
    createdAt: Date.now(),
  };
  saveSaved([item, ...list]);
  return item;
}

export function removeSaved(id) {
  const list = loadSaved().filter((x) => x.id !== id);
  saveSaved(list);
  return list;
}
