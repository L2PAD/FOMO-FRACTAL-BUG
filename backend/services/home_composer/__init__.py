"""
Home Composer — Phase D Pass 3

Extracts the orchestration of `/api/miniapp/home` from server.py into a layered
module package. The HTTP route stays in server.py and retains ownership.
Composition (data assembly) lives here.

Discipline (see /app/memory/PHASE_D_PASS_3_*.md):
  - Composer modules are ASSEMBLY ONLY (A10). They never call analyze(),
    recompute(), resolve(), sweep(), simulate(). They consume pre-fetched
    payloads.
  - The top-level composer.compose() is the *orchestration boundary*: it
    is allowed to call the existing cognition entry points to fetch
    payloads. Module adapters consume what compose() hands them.
  - Public payload topology is preserved byte-for-byte (A1 hard gate).
  - Truthful asymmetry: each module's state is independent. No "make it
    pretty" normalization.
  - Canonical snapshots (Pass 2A/2B) are INWARD-only — composer can
    consume them for coherence/discipline, but they MUST NOT replace the
    public payload schema.
"""

from .composer import compose  # noqa: F401

__all__ = ["compose"]
