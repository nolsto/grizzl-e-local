from __future__ import annotations

import inspect
import collections
from typing import TYPE_CHECKING, ClassVar

from ..constants import Endpoint
from ..util import extract_base_type
from .fields import FIELD_CONVERSIONS
from .validation import ValidationError

if TYPE_CHECKING:
    from .validation import Validator


class BaseDocument(collections.UserDict):
    """Runtime document base — accepts complex types, normalizes on storage."""

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

        if callable(item):
            source = item
            def resolve():
                return self.normalize(key, source())
            item = resolve
        else:
            item = self.normalize(key, item)
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

    def serialize(self) -> dict[str, object]:
        result = {}
        field_types = type(self).get_field_types()
        for key, value in self.data.items():
            if callable(value):
                value = value()
            raw_hint = field_types.get(key)
            if raw_hint is None:
                continue
            py_type, _metadata = extract_base_type(raw_hint)
            entry = FIELD_CONVERSIONS.get(py_type)
            if isinstance(value, py_type):
                result[key] = entry[1](value) if entry else value
        return result

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
    def get_field_types(cls) -> dict[str, object]:
        if '_field_types_cache' not in cls.__dict__:
            result: dict[str, object] = {}
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
    def normalize(cls, key: str, value: object) -> object:
        field_types = cls.get_field_types()
        raw_hint = field_types.get(key)
        if raw_hint is None:
            return value
        py_type, _metadata = extract_base_type(raw_hint)
        if isinstance(value, py_type):
            return value
        entry = FIELD_CONVERSIONS.get(py_type)
        if entry is None:
            try:
                return py_type(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{key}: expected {py_type.__name__}, got {type(value).__name__}"
                ) from None
        deserializer, _, *raw_types = entry
        if not raw_types or not isinstance(value, tuple(raw_types)):
            raise ValueError(
                f"{key}: expected {py_type.__name__} or"
                f" {tuple(t.__name__ for t in raw_types)}, got {type(value).__name__}"
            )
        return deserializer(value)

    @classmethod
    def validate(cls, data: dict[str, object]) -> None:
        for key, value in data.items():
            cls.normalize(key, value)
