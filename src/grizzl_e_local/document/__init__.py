from .base import BaseDocument
from .validation import ValidationError
from .versions import Version_01 as Document

__all__ = ["BaseDocument", "Document", "ValidationError"]
