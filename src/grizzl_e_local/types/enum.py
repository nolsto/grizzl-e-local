import inspect
from enum import _EnumDict
from enum import Enum as BaseEnum
from enum import EnumMeta as BaseEnumMeta


class EnumMeta(BaseEnumMeta):
    label: str

    def __new__(cls, name: str, bases, namespace: _EnumDict, **kwargs):
        Labels = namespace.get('Labels')

        if Labels is not None and inspect.isclass(Labels):
            del namespace['Labels']

        namespace._cls_name = name

        obj = super().__new__(cls, name, bases, namespace, **kwargs)
        for m in obj:
            try:
                m.label = getattr(Labels, m.name)
            except AttributeError:
                m.label = m.name.replace('_', ' ').title()
        return obj


class Enum(EnumMeta('Enum', (BaseEnum,), _EnumDict())):
    def __str__(self):
        return str(self.label)


class IntEnum(int, Enum):
    pass
