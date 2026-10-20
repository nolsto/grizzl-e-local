import locale

from .client import Client

__all__ = ["Client"]

locale.setlocale(locale.LC_MONETARY, 'en_US.UTF-8')
