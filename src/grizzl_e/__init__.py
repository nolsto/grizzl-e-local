import locale

from .client import Client
from .document import Document

__all__ = ["Client", "Document"]

locale.setlocale(locale.LC_MONETARY, 'en_US.UTF-8')
