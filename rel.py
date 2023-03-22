from dataclasses import dataclass
from serialization import Serializable, Numeric, ResizableBuffer
from struct import pack_into


@dataclass
class Rel:
    buf: ResizableBuffer = ResizableBuffer(0)
    pointer_offsets: list[int] = []

    def write(self, item: Serializable) -> int:
        ptr = item.serialize_into(self.buf)
        # Remember where pointers are written
        for offset in item.pointer_member_offsets():
            self.pointer_offsets.append(ptr + offset)
        return ptr

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
        for abs_offset in self.pointer_offsets:
            rel_offset = abs_offset - prev_pointer_offset
            prev_pointer_offset = abs_offset
            self.buf.pack("H", rel_offset)
        # Create trailer
        self.buf.grow(0x20)
        pack_into("I", trailer, pointer_table_pointer_offset, pointer_table_offset)
        pack_into("I", trailer, pointer_count_offset, pointer_count)
        pack_into("I", trailer, payload_pointer_offset, payload_offset)
        return self.buf.buffer
