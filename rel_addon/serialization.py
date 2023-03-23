import sys
from dataclasses import dataclass
from typing import NewType, get_type_hints, get_args
from struct import pack, pack_into
from warnings import warn


def typehint_of_name(name: str, ns=sys.modules[__name__]):
    return get_type_hints(ns).get(name)


@dataclass
class Numeric:
    """Contains numeric types"""
    type_info = {
        # newtype name: python type, structlib format
        "U8": (int, "<B"),
        "U16": (int, "<H"),
        "U32": (int, "<L"),
        "I8": (int, "<b"),
        "I16": (int, "<h"),
        "I32": (int, "<l"),
        "F32": (float, "<f"),
        "Ptr16": (int, "<H"),
        "Ptr32": (int, "<L")
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
        return None

    @classmethod
    def offset_of_member(cls, member: str) -> int:
        # XXX: Only supports objects with primitive type members
        fmt_str = ""
        for name in cls.__annotations__:
            if name == member:
                break
            tp = cls.__annotations__[name]
            fmt = Numeric.format_of_type(tp)
            if fmt:
                fmt_str += fmt
        return Numeric.size_of_format(fmt_str)
    
    @classmethod
    def pointer_member_offsets(cls) -> list[int]:
        # XXX: Only supports objects with primitive type members
        offsets = []
        for name in cls.__annotations__:
            tp = cls.__annotations__[name]
            if tp == Numeric.Ptr16 or tp == Numeric.Ptr32:
                offsets.append(cls.offset_of_member(name))
        return offsets
    
    @classmethod
    def size(cls) -> int:
        # XXX: Only supports objects with primitive type members
        fmt_str = ""
        for name in cls.__annotations__:
            tp = cls.__annotations__[name]
            fmt = Numeric.format_of_type(tp)
            if fmt:
                fmt_str += fmt
        return Numeric.size_of_format(fmt_str)
    
    def _warn_unserializable(self, name):
        warn("Serializable class \"{}\" has unserializable member \"{}\"".format(type(self).__name__, name))

    def _visit(self, buf: ResizableBuffer, value, name, tp) -> int:
        if isinstance(value, Serializable):
            # Serialize object
            return value.serialize_into(buf)

        is_list = type(value) is list
        is_tuple = type(value) is tuple
        if is_list or is_tuple:
            container_type = None
            # Need to get typehint to get the element type
            if name is not None:
                container_type = typehint_of_name(name, self)
            elif tp is not None:
                container_type = tp
            elem_types = get_args(container_type)
            if len(elem_types) < 1:
                # Can't continue
                self._warn_unserializable(name)
                return None
            first_write_offset = None
            for i in range(len(value)):
                # Get type of current element
                # Lists have one element type, tuples have n
                type_idx = 0
                if is_tuple:
                    type_idx = i
                elem_type = elem_types[type_idx]
                # Visit element
                offset = self._visit(buf, value[i], None, elem_type)
                # Save offset of first write
                if first_write_offset is None:
                    first_write_offset = offset
            return first_write_offset

        # Value is primitive
        # Determine format from name or type
        fmt = None
        if name is not None:
            fmt = self.format_of_member(name)
        elif tp is not None:
            fmt = Numeric.format_of_type(tp)
        if fmt is None:
            # Can't continue
            self._warn_unserializable(name)
            return None
        return buf.pack(fmt, value)

    def serialize_into(self, buf: ResizableBuffer) -> int:
        """Writes serializable members of this object into given buffer.
        Returns absolute offset of where data was written."""
        first_write_offset = None
        # Visit members
        for name in self.__dict__:
            value = self.__dict__[name]
            offset = self._visit(buf, value, name, None)
            # Save offset of first write
            if first_write_offset is None:
                first_write_offset = offset
        return first_write_offset
            
