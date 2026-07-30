from __future__ import annotations

from typing import Protocol

from ..types import DocT


class ValidationError(Exception):
    pass


class Validator(Protocol[DocT]):
    """Base class for document validators."""

    fields: set[str] = set()
    def __call__(self, doc: DocT) -> None: ...


class PasswordLengthValidator:
    def __init__(self, field: str):
        self.fields = {field}
        self._field = field

    def __call__(self, doc: DocT) -> None:
        value: str = getattr(doc, self._field, "")
        if value and len(value) < 8:
            raise ValidationError(f"{self._field} must be at least 8 characters")
