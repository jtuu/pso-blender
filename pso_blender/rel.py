from struct import pack_into, unpack_from
from warnings import warn
from .serialization import Serializable, ResizableBuffer
from .util import AbstractFileArchive


class Rel(AbstractFileArchive):
    ALIGNMENT = 4
    POINTER_TABLE_POINTER_OFFSET = -0x20
    POINTER_COUNT_OFFSET = -0x1c
    PAYLOAD_POINTER_OFFSET = -0x10

    def __init__(self, *args, buf=None):
        if buf is None:
            self.buf = ResizableBuffer(0)
            # Consume the 0th offset to ensure that no userdata can have pointers that point to 0
            # because we use 0 as nullptr even though technically it would be a valid offset
            self.buf.pack("<L", 0)
            self.payload_offset = None
        else:
            self.buf = buf
        self.pointer_offsets: list[int] = []
        self.warned_misalignment = False

    def write(self, item: Serializable, ensure_aligned=False) -> int:
        item_offset = item.serialize_into(self.buf, Rel.ALIGNMENT if ensure_aligned else None)
        if not self.warned_misalignment and self.buf.offset % Rel.ALIGNMENT != 0:
            self.warned_misalignment = True
            warn("REL warning: Potential misalignment after writing \"{}\"".format(type(item).__name__))
        # Remember where pointers are written
        for member_offset in item.nonnull_pointer_member_offsets():
            ptr_offset = item_offset + member_offset
            if ptr_offset % Rel.ALIGNMENT != 0:
                raise Exception("REL error: Misaligned pointer in \"{}\" ({} + {})".format(type(item).__name__, item_offset, member_offset))
            self.pointer_offsets.append(ptr_offset)
        return item_offset

    def finish(self, payload_offset: int) -> bytearray:
        # Create pointer table
        self.pointer_offsets.sort()
        pointer_count = len(self.pointer_offsets)
        pointer_size = 2
        pointer_table_size = pointer_count * pointer_size
        self.buf.grow_by(pointer_table_size)
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
        self.buf.grow_by(0x20)
        pack_into("<L", self.buf.buffer, Rel.POINTER_TABLE_POINTER_OFFSET, pointer_table_offset)
        pack_into("<L", self.buf.buffer, Rel.POINTER_COUNT_OFFSET, pointer_count)
        pack_into("<L", self.buf.buffer, Rel.PAYLOAD_POINTER_OFFSET, payload_offset)
        self.payload_offset = payload_offset
        return self.buf.buffer

    @staticmethod
    def read_from(data: bytearray) -> "Rel":
        (pointer_count, ) = unpack_from("<L", data, Rel.POINTER_COUNT_OFFSET)
        (pointer_table_offset, ) = unpack_from("<L", data, Rel.POINTER_TABLE_POINTER_OFFSET)
        (payload_offset, ) = unpack_from("<L", data, Rel.PAYLOAD_POINTER_OFFSET)
        rel = Rel(buf=ResizableBuffer(buf=data))
        rel.payload_offset = payload_offset

        pointer_size = 2
        prev_pointer_offset = 0
        for i in range(pointer_count):
            table_entry_offset = pointer_table_offset + i * pointer_size
            (rel_offset, ) = unpack_from("<H", data, table_entry_offset)
            abs_offset = prev_pointer_offset + rel_offset * 4
            prev_pointer_offset = abs_offset
            rel.pointer_offsets.append(abs_offset)

        return rel
    
    def read(self, cls, offset=0):
        return cls.deserialize_from(self.buf.buffer, offset)
    
    def is_nonnull_pointer(self, offset: int) -> bool:
        return offset in self.pointer_offsets
            
