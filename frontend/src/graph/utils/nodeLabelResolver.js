/**
 * Node Label Resolver
 * 
 * Resolves node labels from:
 * 1. Anchor entities (known addresses → labels)
 * 2. Known protocol names
 * 3. Address shortening fallback
 */

import anchorEntities from '../seeds/baseEntities.json';

// Build address → label lookup from anchor entities
const ADDRESS_LABELS = new Map();
anchorEntities.forEach(entity => {
  if (entity.address) {
    ADDRESS_LABELS.set(entity.address.toLowerCase(), entity.label);
  }
});

/**
 * Resolve a human-readable label for a node
 * 
 * Priority:
 * 1. If node already has a non-address label → use it
 * 2. If address matches anchor entity → use anchor label
 * 3. If address → shorten to 0xABCD…1234
 * 4. Fallback → node.id truncated
 */
export function resolveNodeLabel(node) {
  if (!node) return '';

  const id = node.id || '';
  const raw = node.label || node.name || '';
  const idParts = id.split(':');
  const nodeType = idParts[0] || '';
  const identifier = idParts[1] || '';

  // For typed IDs (cluster:name:chain, cex:addr:chain, entity:name:chain)
  // Extract the meaningful name, not the full ID
  if (idParts.length >= 2 && ['cluster', 'entity', 'protocol'].includes(nodeType)) {
    // Try anchor label first
    if (identifier) {
      const anchorLabel = ADDRESS_LABELS.get(identifier.toLowerCase());
      if (anchorLabel) return anchorLabel.replace(/_/g, ' ');
    }
    // Use the identifier as label (e.g., "jump-trading")
    if (identifier && !identifier.startsWith('0x')) {
      const clean = identifier.replace(/_/g, ' ');
      return clean.length > 18 ? clean.slice(0, 15) + '...' : clean;
    }
  }

  // If node already has a good label (not an address, not a typed ID)
  if (raw && !raw.startsWith('0x') && !raw.includes(':') && raw.length <= 20) {
    return raw.replace(/_/g, ' ');
  }

  // Try to resolve from anchor entities by address
  const addr = node.address || '';
  if (addr) {
    const anchorLabel = ADDRESS_LABELS.get(addr.toLowerCase());
    if (anchorLabel) return anchorLabel.replace(/_/g, ' ');
  }

  // Try to resolve from node ID address part
  if (idParts.length >= 2 && identifier) {
    const anchorLabel = ADDRESS_LABELS.get(identifier.toLowerCase());
    if (anchorLabel) return anchorLabel.replace(/_/g, ' ');
  }

  // For typed labels like "cluster:something:chain" — extract middle part
  if (raw && raw.includes(':')) {
    const parts = raw.split(':');
    const name = (parts[1] || parts[0]).replace(/_/g, ' ');
    if (name.startsWith('0x') && name.length >= 10) {
      return `${name.slice(0, 6)}\u2026${name.slice(-4)}`;
    }
    return name.length > 18 ? name.slice(0, 15) + '...' : name;
  }

  // Use raw label
  if (raw) {
    if (raw.startsWith('0x') && raw.length >= 10) {
      return `${raw.slice(0, 6)}\u2026${raw.slice(-4)}`;
    }
    return (raw.length > 16 ? raw.slice(0, 12) + '...' : raw).replace(/_/g, ' ');
  }

  // Fallback: shorten node ID
  if (identifier) {
    if (identifier.startsWith('0x') && identifier.length >= 10) {
      return `${identifier.slice(0, 6)}\u2026${identifier.slice(-4)}`;
    }
    return (identifier.length > 16 ? identifier.slice(0, 12) + '...' : identifier).replace(/_/g, ' ');
  }

  return (id.length > 16 ? id.slice(0, 12) + '...' : id).replace(/_/g, ' ');
}

/**
 * Check if a given address is a known anchor entity
 */
export function isKnownEntity(address) {
  if (!address) return false;
  return ADDRESS_LABELS.has(address.toLowerCase());
}

/**
 * Get the anchor label for an address, or null
 */
export function getAnchorLabel(address) {
  if (!address) return null;
  return ADDRESS_LABELS.get(address.toLowerCase()) || null;
}
