"""
services/exchange — read-only exchange transport layer.

This package is the ONLY place in the codebase that imports ccxt or any
other exchange transport. Every public adapter exposed from here MUST
inherit from `ReadonlyExchangeAdapter` and MUST surface only the six
whitelisted methods.

Forbidden across this entire package (enforced by AST-level invariant
tests in `tests/test_sprint_t10_2b_binance_readonly.py`):

  * any function named `create_order`, `cancel_order`, `submit_order`,
    `withdraw`, `transfer`, or anything containing `futures` / `leverage`
  * any attribute access on the underlying transport that is not one of
    the six whitelist methods
  * dynamic dispatch via `getattr(self._exchange, ...)`

T10.2B invariant:
    "T10.2B is an observability bridge, not an execution bridge."

If you find yourself adding write capability here, STOP. That belongs
in a future T10.3 module behind a separate gate.
"""
from .base import ReadonlyExchangeAdapter, ExchangeCapability  # noqa: F401
from .binance_readonly import BinanceReadonlyAdapter  # noqa: F401
