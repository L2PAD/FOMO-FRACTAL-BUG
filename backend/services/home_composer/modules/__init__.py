"""Per-section assemblers for the Home Composer.

Every module exposes a single `assemble(ctx)` function. They are pure:
no DB I/O, no network, no recomputation. They only consume already-
fetched payloads from HomeContext and return a dict slice of the final
public payload.
"""
