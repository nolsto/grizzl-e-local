from __future__ import annotations

from typing import TypeVar, overload


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
