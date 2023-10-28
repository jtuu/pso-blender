import sys
from dataclasses import dataclass, field
from typing import NewType, get_type_hints, get_args, get_origin, Annotated
from struct import pack_into, unpack_from, error as StructError
from warnings import warn
from operator import itemgetter


def typehint_of_name(name: str, ns=sys.modules[__name__]):
    return get_type_hints(ns).get(name)


def FixedArray(tp, length):
    return NewType("FixedArray", Annotated[tp, length])


@dataclass
class Numeric:
    """Contains numeric types"""
    NULLPTR = 0

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
def generate_numeric_types():
    for name in Numeric.type_info:
        (tp, fmt) = Numeric.type_info[name]
        setattr(Numeric, name, NewType(name, tp))
generate_numeric_types()


class ResizableBuffer:
    def __init__(self, *args, size=0, buf=None):
        if buf is None:
            self.buffer = bytearray(size)
        else:
            self.buffer = buf
        self.capacity = size
        self.offset = 0
    
    def grow_by(self, by: int):
        self.buffer += bytearray(by)
        self.capacity += by
    
    def grow_to(self, to: int):
        if self.capacity > to:
            raise Exception("Failed to grow ResizableBuffer because it is already bigger than requested size ({}/{})".format(self.capacity, to))
        self.grow_by(to - self.capacity)

    def append(self, other: bytearray) -> int:
        offset_before = self.offset
        self.buffer += other
        self.capacity += len(other)
        return offset_before
    
    def seek_to_end(self):
        self.offset = self.capacity

    def pack(self, fmt: str, *vals) -> int:
        """Returns absolute offset of where data was written"""
        offset_before = self.offset
        item_size = Numeric.size_of_format(fmt)
        remaining = self.capacity - self.offset
        # Grow if needed
        if item_size > remaining:
            need = item_size - remaining
            self.grow_by(need)
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
        (fmt, ctx) = itemgetter("fmt", "ctx")(kwargs)
        if ctx["filter"](**kwargs):
            ctx["offsets"].append(ctx["size_sum"])
        if fmt:
            ctx["size_sum"] += Numeric.size_of_format(fmt)
        return True

    def nonnull_pointer_member_offsets(self) -> list[int]:
        ctx = {
            "size_sum": 0,
            "offsets": [],
            "filter": lambda **kwargs: kwargs["tp"] is not None and kwargs["tp"] is Numeric.Ptr32 and kwargs["value"] != Numeric.NULLPTR}
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
        if name is not None and name.startswith("_"):
            return True
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
        is_fixed_array = tp.__name__ == "FixedArray"
        if is_list or is_tuple or is_fixed_array:
            container_type = None
            length = 0
            # Need to get typehint to get the element type
            if is_fixed_array:
                (elem_type, expected_length) = get_args(tp.__supertype__)
                elem_types = [elem_type] * expected_length
                length = expected_length
                if is_list:
                    if len(value) > expected_length:
                        warn("FixedArray member '{}' of class '{}' was truncated during serialization".format(name, cls.__name__))
                        value = value[:expected_length]
                    elif len(value) < expected_length:
                        # Pad with zeros
                        value += [0] * (expected_length - len(value))
            elif name is not None:
                container_type = typehint_of_name(name, cls)
                elem_types = get_args(container_type)
                length = len(value)
            elif tp is not None:
                container_type = tp
                elem_types = get_args(container_type)
                length = len(value)
            if len(elem_types) < 1:
                # Can't continue
                cls._warn_unserializable(name)
                return None
            should_continue = True
            for i in range(length):
                # Get type of current element
                # Lists have one element type, tuples have n
                type_idx = 0
                if is_tuple:
                    type_idx = i
                elem_type = elem_types[type_idx]
                elem_value = None
                if hasattr(value, "__getitem__"):
                    elem_value = value[i]
                # Visit element
                should_continue = cls._visit(elem_value, ctx, visitor, name=name, tp=elem_type)
                if not should_continue:
                    break
            return should_continue
        fmt = None
        is_buffer = type(value) is bytes or type(value) is bytearray
        if is_buffer:
            tp = type(value)
        elif get_origin(value) is not list and get_origin(value) is not tuple:
            # Value is primitive
            # Determine format from name or type
            if tp is not None:
                fmt = Numeric.format_of_type(tp)
            elif name is not None:
                fmt = cls.format_of_member(name)
            if fmt is None:
                # Can't continue
                cls._warn_unserializable(name)
                return None
        # Call visitor on value
        return visitor(value=value, name=name, tp=tp, fmt=fmt, ctx=ctx)
    
    @staticmethod
    def _serializer_visitor(**kwargs) -> bool:
        (name, value, ctx, fmt, tp) = itemgetter("name", "value", "ctx", "fmt", "tp")(kwargs)
        if fmt:
            try:
                offset = ctx["buf"].pack(fmt, value)
            except StructError as err:
                # Rethrow with more info
                orig_msg = err.args[0]
                raise Exception("Serialization error in member '{}' with value '{}' and type '{}': {}".format(name, value, tp, orig_msg))
        elif tp is bytes or tp is bytearray:
            offset = ctx["buf"].append(value)
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
        if ctx["first_offset"] is None:
            raise Exception("Serialization error: Did not write anything")
        return ctx["first_offset"]
    
    def _deserializer_visitor(**kwargs) -> bool:
        (name, ctx, fmt) = itemgetter("name", "ctx", "fmt")(kwargs)
        if fmt:
            sz = Numeric.size_of_format(fmt)
            (value, ) = unpack_from(fmt, ctx["buf"], ctx["offset"])
            if type(ctx["result"].__dict__[name]) is list:
                ctx["result"].__dict__[name].append(value)
            else:
                ctx["result"].__dict__[name] = value
            ctx["offset"] += sz
        return True
    
    @classmethod
    def deserialize_from(cls, buf, offset=0):
        """Assumes class has default constructor"""
        result = cls() # Default construct
        ctx = {"result": result, "offset": offset, "buf": buf}
        cls._visit(cls, ctx, Serializable._deserializer_visitor)
        return (result, ctx["offset"])
    
    @classmethod
    def read_sequence(cls, buf, offset, count) -> list:
        items = []
        if count < 1:
            return items
        size = cls.type_size()
        for _ in range(count):
            (item, _) = cls.deserialize_from(buf, offset)
            items.append(item)
            offset += size
        return items
        

@dataclass
class AlignmentHelper(Serializable):
    wrapped: Serializable
    padding: list[Numeric.U8] = field(default_factory=list)


class AlignedString(Serializable):
    chars: list[Numeric.U8] = field(default_factory=list)

    def __init__(self, s: str, alignment: int):
        self.chars = list(str.encode(s))
        self.chars.append(0)
        self._alignment = alignment

    def serialize_into(self, buf, unused):
        return super().serialize_into(buf, self._alignment)
