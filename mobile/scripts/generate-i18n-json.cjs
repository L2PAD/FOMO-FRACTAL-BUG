#!/usr/bin/env node
/**
 * generate-i18n-json.cjs — emit a canonical JSON snapshot of i18n.ts
 *
 * Phase E1 / A2 — TG Mini-App server-side localization.
 *
 * Pattern: one language brain → two render surfaces.
 * The Expo client reads `i18n.ts` directly (TS source-of-truth).
 * The Python backend (TG Mini-App, miniapp_lite.py) reads the JSON snapshot
 * produced here. This script must be re-run whenever i18n.ts changes.
 *
 * Output: /app/backend/services/i18n_dictionary.json
 *   {
 *     "version": "<unix ts>",
 *     "locales": ["en", "ru", "uk"],
 *     "dictionary": {
 *       "en": { "key": "value", ... },
 *       "ru": { "key": "value", ... },
 *       "uk": { "key": "value", ... }
 *     }
 *   }
 *
 * Parse rules (kept deliberately simple to avoid pulling in a TS toolchain):
 *   - Treat i18n.ts as a flat record of single-quoted string keys → single-quoted
 *     string values, scoped under the top-level locale blocks `en:`, `ru:`, `uk:`.
 *   - Lines that don't match the `  '<key>': '<value>',` shape are ignored.
 *   - Single-quote escape support: \' → ' inside values.
 */

const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '../src/core/i18n.ts');
const OUT = path.resolve(__dirname, '../../backend/services/i18n_dictionary.json');

const src = fs.readFileSync(SRC, 'utf8');

const LOCALES = ['en', 'ru', 'uk'];
const out = { version: String(Math.floor(Date.now() / 1000)), locales: LOCALES, dictionary: {} };

for (const loc of LOCALES) {
  // Find the opening `  <loc>: {` line and walk braces to its matching `}`.
  const openRe = new RegExp(`^  ${loc}: \\{`, 'm');
  const m = openRe.exec(src);
  if (!m) {
    console.error(`! locale block not found: ${loc}`);
    out.dictionary[loc] = {};
    continue;
  }
  let i = m.index + m[0].length;
  let depth = 1;
  while (i < src.length && depth > 0) {
    const c = src[i];
    if (c === '{') depth++;
    else if (c === '}') depth--;
    if (depth === 0) break;
    i++;
  }
  const body = src.slice(m.index + m[0].length, i);

  // Match keys like:
  //   'foo.bar': 'value with maybe \\' escape',
  //   'foo.bar': "value with apostrophe (single-quoted string would need escape)",
  // Both delimiters supported because i18n.ts uses both styles depending on the
  // value content. The captured group preserves \n and other escape sequences
  // literally; we evaluate them via JSON.parse so the snapshot matches what
  // JS would see at runtime.
  const keyRe = /^\s+'([^']+)'\s*:\s*(['"])((?:\\.|[^\\])*?)\2\s*,?\s*$/gm;
  const block = {};
  let km;
  while ((km = keyRe.exec(body)) !== null) {
    const key = km[1];
    const quote = km[2];
    const raw = km[3];
    let value;
    try {
      // Reuse JSON.parse to evaluate escapes (\n, \', \", \\) consistently.
      // We re-wrap the raw value in double quotes; if it was single-quoted we
      // unescape its single quotes and escape any double quotes.
      let normalized = raw;
      if (quote === "'") {
        normalized = normalized.replace(/\\'/g, "'").replace(/"/g, '\\"');
      }
      value = JSON.parse('"' + normalized + '"');
    } catch (e) {
      // Fall back to raw (best effort) if JSON.parse fails on an exotic escape.
      value = raw.replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\\\/g, '\\');
    }
    block[key] = value;
  }
  out.dictionary[loc] = block;
  console.log(`  ${loc}: ${Object.keys(block).length} keys`);
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
console.log(`✓ wrote ${OUT}`);
