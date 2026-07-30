from contextvars import ContextVar
from typing import Any

transaction_batch = ContextVar[dict[str, Any]]("transaction_batch")
