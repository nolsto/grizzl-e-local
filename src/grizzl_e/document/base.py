from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .validation import Validator


class BaseDocument(BaseModel):
    """Flat model mirroring the device's JSON document structure.

    Fields are parsed from their native device types (int, float, str). Since there is no
    guarantee that valid data will be sent by the device, only serialization/deserialization logic
    belongs here. Additional validation and business logic belongs in the device/component layers.
    """

    validators: ClassVar[list[Validator[Self]]]

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    def diff(self, other: BaseDocument) -> set[str]:
        old_dump = self.model_dump()
        new_dump = other.model_dump()
        return {k for k in new_dump if old_dump.get(k) != new_dump.get(k)}
