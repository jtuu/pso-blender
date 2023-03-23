from dataclasses import dataclass
from struct import pack_into, unpack_from
from warnings import warn
from .serialization import Serializable, Numeric, ResizableBuffer


class Rel:
    def __init__(self):
        self.buf: ResizableBuffer = ResizableBuffer(0)
        self.pointer_offsets: list[int] = []
        self.warned_misalignment = False

    def write(self, item: Serializable) -> int:
        item_offset = item.serialize_into(self.buf)
        if not self.warned_misalignment and self.buf.offset % 4 != 0:
            self.warned_misalignment = True
            warn("REL warning: Potential misalignment after writing \"{}\"".format(type(item).__name__))
        # Remember where pointers are written
        for member_offset in item.pointer_member_offsets():
            ptr_offset = item_offset + member_offset
            if ptr_offset % 4 != 0:
                raise Exception("REL error: Misaligned pointer in \"{}\" ({} + {})".format(type(item).__name__, item_offset, member_offset))
            self.pointer_offsets.append(ptr_offset)
        return item_offset

    def finish(self, payload_offset: int) -> bytearray:
        pointer_table_pointer_offset = -0x20
        pointer_count_offset = -0x1c
        payload_pointer_offset = -0x10

        # Create pointer table
        self.pointer_offsets.sort()
        pointer_count = len(self.pointer_offsets)
        pointer_size = 2
        pointer_table_size = pointer_count * pointer_size
        self.buf.grow(pointer_table_size)
        prev_pointer_offset = 0
        pointer_table_offset = self.buf.offset
        # Pointer table contains locations of pointers within the payload
        # Offsets are from the previous pointer's location (the first one is absolute)
        # Offsets are divided by 4 (and thus pointers must be aligned to 4 bytes)
        for abs_offset in self.pointer_offsets:
            rel_offset = (abs_offset - prev_pointer_offset) // 4
            prev_pointer_offset = abs_offset
            self.buf.pack("<H", rel_offset)
        # Create trailer
        self.buf.grow(0x20)
        pack_into("<L", self.buf.buffer, pointer_table_pointer_offset, pointer_table_offset)
        pack_into("<L", self.buf.buffer, pointer_count_offset, pointer_count)
        pack_into("<L", self.buf.buffer, payload_pointer_offset, payload_offset)
        return self.buf.buffer
