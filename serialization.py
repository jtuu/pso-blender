import sys
from dataclasses import dataclass
from typing import NewType, get_type_hints
from struct import pack, pack_into
from warnings import warn


def typehint_of_name(name: str, ns=sys.modules[__name__]):
    return get_type_hints(ns).get(name)


@dataclass
class Numeric:
    """Contains numeric types"""
    type_info = {
        # newtype name: python type, structlib format
        "U8": (int, "B"),
        "U16": (int, "H"),
        "U32": (int, "L"),
        "I8": (int, "b"),
        "I16": (int, "h"),
        "I32": (int, "l"),
        "F32": (float, "f"),
    }

    type_sizes = {
        "B": 1,
        "H": 2,
        "L": 4,
        "b": 1,
        "h": 2,
        "l": 4,
        "f": 4,
    }

    @staticmethod
    def format_of_type(tp) -> str:
        """Returns the structlib format of the given type"""
        entry = Numeric.type_info.get(tp.__name__)
        if not entry:
            return None
        return entry[1]
    
    @staticmethod
    def size_of_format(fmt: str) -> int:
        size_sum = 0
        for ch in fmt:
            size_sum += Numeric.type_sizes.get(ch, 0)
        return size_sum


# Create NewTypes and store them in Numeric class
for name in Numeric.type_info:
    (tp, fmt) = Numeric.type_info[name]
    setattr(Numeric, name, NewType(name, tp))


class ResizableBuffer:
    def __init__(self, size):
        self.buffer = bytearray(size)
        self.capacity = size
        self.offset = 0
    
    def grow(self, by):
        self.buffer += bytearray(by)
        self.capacity += by

    def pack(self, fmt: str, *vals) -> int:
        """Returns absolute offset of where data was written"""
        offset_before = self.offset
        item_size = Numeric.size_of_format(fmt)
        remaining = self.capacity - self.offset
        # Grow if needed
        if item_size > remaining:
            need = item_size - remaining
            self.grow(need)
        pack_into(fmt, self.buffer, self.offset, *vals)
        self.offset += item_size
        return offset_before


class Serializable:
    def __init__(self):
        pass

    def format_of_member(self, member: str) -> str:
        fmt = Numeric.format_of_type(typehint_of_name(member, self))
        if fmt:
            return fmt
        warn("Serializable class \"{}\" has non-serializable member \"{}\"".format(type(self).__name__, member))
        return None

    def offset_of_member(self, member: str) -> int:
        fmt_str = ""
        for name in self.__dict__:
            if name == member:
                break
            fmt = Numeric.format_of_type(typehint_of_name(name, self))
            if fmt:
                fmt_str += fmt
        return Numeric.size_of_format(fmt_str)

    def serialize_into(self, buf: CursorBuffer) -> int:
        """Writes serializable members of this object into given buffer"""
        fmt_str = ""
        vals = []
        # Get structlib format of each instance member
        for name in self.__dict__:
            fmt = self.format_of_member(name)
            if fmt:
                fmt_str += fmt
                vals.append(self.__dict__[name])
        return buf.pack(fmt_str, *vals)
