from __future__ import annotations

from datetime import datetime, timezone

from typing import Annotated, Any, TypeVar, get_args, get_origin, overload


def tznow():
    return datetime.now(timezone.utc).astimezone()


ExceptionT = TypeVar('ExceptionT', bound=Exception)
BaseExceptionT = TypeVar('BaseExceptionT', bound=BaseException)

@overload
def flatten_exceptions[ExceptionT](group: ExceptionGroup) -> list[ExceptionT]: ...

@overload
def flatten_exceptions[BaseExceptionT](group: BaseExceptionGroup) -> list[BaseExceptionT]: ...

def flatten_exceptions(group):
    """Flatten an ExceptionGroup into a list of exceptions."""
    exceptions = []
    for exc in group.exceptions:
        if isinstance(exc, BaseExceptionGroup):
            exceptions.extend(flatten_exceptions(exc))
        else:
            exceptions.append(exc)
    return exceptions


def extract_base_type(hint: Any) -> tuple[type, tuple[Any, ...]]:
    """Extract the base type from an Annotated[...] type.

    Returns (base_type, metadata_tuple). If not annotated, returns (hint, ()).
    """
    origin = get_origin(hint)
    if origin is Annotated:
        args = get_args(hint)
        return args[0], args[1:]
    return hint, ()
