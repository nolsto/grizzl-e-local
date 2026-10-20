from __future__ import annotations

import collections
import inspect
from typing import TYPE_CHECKING, ClassVar

from ..constants import Endpoint
from ..util import extract_base_type
from .validation import ValidationError

if TYPE_CHECKING:
    from .validation import Validator


class BaseDocument(collections.UserDict):
    """Stores document fields in their on-device representation (str, int or float)."""

    validators: ClassVar[list[Validator]] = []

    def __getattr__(self, name: str) -> object:
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: object) -> None:
        if name == 'data' or name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self[name] = value

    def __setitem__(self, key: str, item: object) -> None:
        if key not in type(self).get_field_types():
            raise KeyError(f"unknown field: {key}")
        self.check(key, item)
        self.data[key] = item

    def diff(self, other: BaseDocument) -> set[str]:
        return {k for k in other.data if self.data.get(k) != other.data[k]}

    def run_validators(self) -> None:
        keys = set(self.data)
        for validator in self.validators:
            if keys & validator.fields:
                validator(self)

    def is_valid(self) -> bool:
        try:
            self.run_validators()
            return True
        except ValidationError:
            return False

    @classmethod
    def get_endpoint(cls, field_name: str) -> Endpoint:
        resolved = inspect.get_annotations(cls, eval_str=True).get(field_name)
        if resolved is None:
            return Endpoint.SET
        _, metadata = extract_base_type(resolved)
        for arg in metadata:
            if isinstance(arg, Endpoint):
                return arg
        return Endpoint.SET

    @classmethod
    def get_field_types(cls) -> dict[str, type | None]:
        if '_field_types_cache' not in cls.__dict__:
            result: dict[str, type | None] = {}
            for name, resolved in inspect.get_annotations(cls, eval_str=True).items():
                if name == 'validators':
                    continue
                try:
                    result[name], _ = extract_base_type(resolved)
                except (TypeError, AttributeError):
                    continue
            cls._field_types_cache = result
        return cls._field_types_cache

    @classmethod
    def check(cls, key: str, value: object) -> None:
        try:
            py_type = cls.get_field_types()[key]
        except KeyError as e:
            raise KeyError(f"unknown field: {key}") from e
        if py_type is None:
            if value is py_type:
                return
            raise ValueError(f"{key}: expected None, got {value}")
        if isinstance(value, py_type):
            return
        # JSON numbers without a fractional part parse as int even on float fields.
        if py_type is float and type(value) is int:
            return
        raise ValueError(
            f"{key}: expected {py_type.__name__}, got {type(value).__name__}"
        )

    @classmethod
    def validate(cls, data: dict[str, object]) -> None:
        for key, value in data.items():
            if cls.get_field_types().get(key) is not None:
                cls.check(key, value)
