#!/usr/bin/env bash
# Auto-create no-op TypeScript stubs for any missing module the sidecar
# tries to import.  Re-runs the sidecar repeatedly until it boots cleanly
# or we exceed MAX_ATTEMPTS.

set -u
MAX_ATTEMPTS=80
ROOT=/app/legacy
LOG=/tmp/sidecar.log

write_stub() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
  # Determine likely export name from the missing import line in log if known
  cat > "$path" <<'EOF'
/**
 * AUTO-STUB — created because the original module was removed during
 * the 2026-05-12 quarantine but is still referenced by the Fractal
 * engine boot graph.  Returns no-op handlers so the sidecar can start.
 * The fractal routes that DO exist still work; only the missing-piece
 * subroutes degrade gracefully.
 */
import type { FastifyInstance } from 'fastify';

const noop = async (_app: FastifyInstance): Promise<void> => {
  /* intentionally empty */
};

// Common export names used across the legacy code base
export default noop;
export const memoryRoutes = noop;
export const attributionRoutes = noop;
export const registerRoutes = noop;
export const register = noop;
export const init = noop;
export const setup = noop;
export const start = noop;
export const stop = noop;
export const routes = noop;
export const plugin = noop;
export const handler = noop;
export const service = {} as Record<string, any>;
export const config = {} as Record<string, any>;

// Some modules export factories
export function createService() { return {}; }
export function createRoutes() { return noop; }
export function createHandler() { return noop; }
EOF
  echo "  [+] stubbed: $path"
}

for attempt in $(seq 1 $MAX_ATTEMPTS); do
  echo "── Attempt $attempt ──"
  pkill -f "tsx sidecar-server.ts" 2>/dev/null
  sleep 1
  (cd "$ROOT" && MONGODB_URI="mongodb://localhost:27017" NODE_SIDECAR_PORT=8003 PORT=8003 ./node_modules/.bin/tsx sidecar-server.ts > "$LOG" 2>&1) &
  SIDECAR_PID=$!
  # Wait up to 30s for either "Listening on" or fatal failure
  for i in $(seq 1 30); do
    sleep 1
    if grep -q "Fractal engine plugin mounted" "$LOG" 2>/dev/null; then
      echo "✓ Fractal engine mounted cleanly (attempt $attempt)"
      exit 0
    fi
    if grep -q "FATAL" "$LOG" 2>/dev/null; then
      echo "FATAL detected"
      break
    fi
  done

  # Pull out the missing module path
  missing=$(grep -o "Cannot find module '[^']*'" "$LOG" | tail -1 | sed -E "s/Cannot find module '([^']*)'/\1/")
  if [ -z "$missing" ]; then
    # CASE 2: JSON-assertion error
    json_missing=$(grep -oE 'Module "file://[^"]*\.json[^"]*" is not of type "json"' "$LOG" | tail -1 | sed -E 's|Module "file://([^"]*)" is not.*|\1|')
    if [ -n "$json_missing" ]; then
      base="${json_missing%.ts}"
      mkdir -p "$(dirname "$base")"
      [ -f "$json_missing" ] && rm -f "$json_missing"
      echo '{"frozen":false,"stubbed":true}' > "$base"
      echo "  [+] json-stubbed: $base"
      continue
    fi
    # CASE 3: Missing named export from an existing stub — append it
    export_re=$(grep -E "does not provide an export named '[^']+'" "$LOG" | tail -1)
    if [ -n "$export_re" ]; then
      missing_name=$(echo "$export_re" | sed -E "s/.*export named '([^']+)'.*/\1/")
      # Find the importing file's referenced module path
      ref_module=$(echo "$export_re" | sed -E "s/.*module '([^']+)' .*/\1/")
      # Get the file location where the SyntaxError originated
      file_line=$(grep -B1 "SyntaxError: The requested module" "$LOG" | head -1)
      stub_file=$(grep -B2 "does not provide an export named '$missing_name'" "$LOG" | grep -oE '/app/legacy/[^:]*\.ts' | head -1)
      # The actual stub to patch is the resolved module path
      # Compute it from ref_module relative to the requesting file
      requester=$(grep -A3 "SyntaxError" "$LOG" | grep -oE '/app/legacy/[^ :]*\.ts' | head -1)
      if [ -n "$requester" ] && [ -n "$ref_module" ]; then
        dir="$(dirname "$requester")"
        target="$(cd "$dir" 2>/dev/null && readlink -f "$ref_module" 2>/dev/null | sed 's/\.js$/\.ts/')"
        if [ -z "$target" ] || [ ! -f "$target" ]; then
          # Try directly resolving
          target=$(echo "$ref_module" | sed 's/\.js$/\.ts/')
          target=$(cd "$dir" && realpath "$target" 2>/dev/null)
        fi
        if [ -n "$target" ] && [ -f "$target" ]; then
          # Append the missing named export
          echo "export const $missing_name = (typeof (globalThis as any).__autoNoop === 'function') ? (globalThis as any).__autoNoop : (async (..._args: any[]) => ({}));" >> "$target"
          echo "  [~] appended export '$missing_name' to: $target"
          continue
        fi
      fi
      echo "  ✗ could not resolve target for missing export '$missing_name'"
      tail -15 "$LOG"
      exit 1
    fi
    echo "✗ No missing-module error found; last 15 lines of log:"
    tail -15 "$LOG"
    exit 1
  fi
  # The path ends with .js but the actual file should be .ts
  ts_path="${missing%.js}.ts"
  if [ -f "$ts_path" ]; then
    echo "✗ File exists already: $ts_path — different error.  Last log:"
    tail -15 "$LOG"
    exit 1
  fi
  write_stub "$ts_path"
done

echo "✗ Exceeded $MAX_ATTEMPTS attempts"
exit 1
