import sys
from dataclasses import dataclass, field
from typing import NewType, get_type_hints, get_args, get_origin
from struct import pack_into
from warnings import warn
from operator import itemgetter


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

    @classmethod
    def format_of_member(cls, member: str) -> str:
        fmt = Numeric.format_of_type(typehint_of_name(member, cls))
        if fmt:
            return fmt
        return None
    
    @staticmethod
    def _offset_visitor(**kwargs) -> bool:
        (fmt, ctx, name, tp) = itemgetter("fmt", "ctx", "name", "tp")(kwargs)
        if tp is not None and tp == ctx.get("type_needle"):
            ctx["offsets"].append(ctx["size_sum"])
        if name is not None and name == ctx.get("name_needle"):
            return False
        if fmt:
            ctx["size_sum"] += Numeric.size_of_format(fmt)
        return True

    @classmethod
    def type_offset_of_member(cls, member: str) -> int:
        ctx = {"name_needle": member, "size_sum": 0}
        cls._visit(cls, ctx, Serializable._offset_visitor)
        return ctx["size_sum"]
    
    def instance_offset_of_member(self, member: str) -> int:
        ctx = {"name_needle": member, "size_sum": 0}
        self._visit(self, ctx, Serializable._offset_visitor)
        return ctx["size_sum"]
    
    @classmethod
    def type_pointer_member_offsets(cls) -> list[int]:
        ctx = {"type_needle": Numeric.Ptr32, "size_sum": 0, "offsets": []}
        cls._visit(cls, ctx, Serializable._offset_visitor)
        return ctx["offsets"]
    
    def instance_pointer_member_offsets(self) -> list[int]:
        ctx = {"type_needle": Numeric.Ptr32, "size_sum": 0, "offsets": []}
        self._visit(self, ctx, Serializable._offset_visitor)
        return ctx["offsets"]
    
    @staticmethod
    def _size_visitor(**kwargs) -> bool:
        (fmt, ctx) = itemgetter("fmt", "ctx")(kwargs)
        if fmt:
            ctx["size_sum"] += Numeric.size_of_format(fmt)
        return True

    def instance_size(self) -> int:
        """Will also include size of data inside any list type members."""
        ctx = {"size_sum": 0}
        self._visit(self, ctx, Serializable._size_visitor)
        return ctx["size_sum"]

    @classmethod
    def type_size(cls) -> int:
        """Similar to sizeof(). Size of lists is considered to be 0."""
        ctx = {"size_sum": 0}
        cls._visit(cls, ctx, Serializable._size_visitor)
        return ctx["size_sum"]
    
    @classmethod
    def _warn_unserializable(cls, name):
        warn("Serializable class \"{}\" has unserializable member \"{}\"".format(cls.__name__, name), stacklevel=2)
    
    @classmethod
    def _visit(cls, value, ctx: dict, visitor, *args, name=None, tp=None) -> bool:
        is_instance = isinstance(value, Serializable)
        is_class = type(value) is type and issubclass(value, Serializable)
        if is_instance or is_class:
            should_continue = True
            members = value.__annotations__ if is_class else value.__dict__
            for member_name in members:
                member_value = members[member_name]
                member_type = None
                if is_instance:
                    member_type = typehint_of_name(member_name, value)
                elif is_class:
                    member_type = member_value
                should_continue = value._visit(member_value, ctx, visitor, name=member_name, tp=member_type)
                if not should_continue:
                    break
            return should_continue
        is_list = type(value) is list
        is_tuple = type(value) is tuple
        if is_list or is_tuple:
            container_type = None
            # Need to get typehint to get the element type
            if name is not None:
                container_type = typehint_of_name(name, cls)
            elif tp is not None:
                container_type = tp
            elem_types = get_args(container_type)
            if len(elem_types) < 1:
                # Can't continue
                cls._warn_unserializable(name)
                return None
            should_continue = True
            for i in range(len(value)):
                # Get type of current element
                # Lists have one element type, tuples have n
                type_idx = 0
                if is_tuple:
                    type_idx = i
                elem_type = elem_types[type_idx]
                # Visit element
                should_continue = cls._visit(value[i], ctx, visitor, tp=elem_type)
                if not should_continue:
                    break
            return should_continue
        
        fmt = None
        if get_origin(value) is not list and get_origin(value) is not tuple:
            # Value is primitive
            # Determine format from name or type
            if name is not None:
                fmt = cls.format_of_member(name)
            elif tp is not None:
                fmt = Numeric.format_of_type(tp)
            if fmt is None:
                # Can't continue
                cls._warn_unserializable(name)
                return None
        # Call visitor on value
        return visitor(value=value, name=name, tp=tp, fmt=fmt, ctx=ctx)
    
    @staticmethod
    def _serializer_visitor(**kwargs) -> bool:
        (value, ctx, fmt) = itemgetter("value", "ctx", "fmt")(kwargs)
        if fmt:
            offset = ctx["buf"].pack(fmt, value)
            if ctx["first_offset"] is None:
                ctx["first_offset"] = offset
        return True

    def serialize_into(self, buf: ResizableBuffer, alignment=None) -> int:
        """Writes serializable members of this object into given buffer.
        Returns absolute offset of where data was written."""
        item = self
        if alignment is not None:
            offset_after = buf.offset + self.instance_size()
            if offset_after % alignment != 0:
                padding = ((offset_after // alignment) + 1) * alignment - offset_after
                item = AlignmentHelper(wrapped=self, padding=[0] * padding)
        ctx = {"first_offset": None, "buf": buf}
        self._visit(item, ctx, Serializable._serializer_visitor)
        return ctx["first_offset"]


@dataclass
class AlignmentHelper(Serializable):
    wrapped: Serializable
    padding: list[Numeric.U8] = field(default_factory=list)