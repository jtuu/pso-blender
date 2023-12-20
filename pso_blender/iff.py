from warnings import warn
from struct import pack_into, unpack_from
from dataclasses import dataclass, field
from .serialization import ResizableBuffer, Numeric, FixedArray, Serializable
from . import util


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


@dataclass
class IffHeader(Serializable):
    type_name: FixedArray(U8, 4) = field(default_factory=list)
    body_size: U32 = 0


class IffChunk(util.AbstractFileArchive):
    ALIGNMENT = 4

    def __init__(self, type_name: str):
        self.buf = ResizableBuffer(0)
        self.pointer_offsets: list[int] = []
        self.warned_misalignment = False
        header = IffHeader(
            type_name=list(bytes(type_name, "ascii")),
            body_size=0xdeadbeef) # Body size is not known yet, we will write it here at the end
        header.serialize_into(self.buf)

    def write(self, item: Serializable, ensure_aligned=False) -> int:
        header_size = IffHeader.type_size()
        # Subtract header to make pointers relative to body
        item_offset = item.serialize_into(self.buf, IffChunk.ALIGNMENT if ensure_aligned else None) - header_size
        if not self.warned_misalignment and self.buf.offset % IffChunk.ALIGNMENT != 0:
            self.warned_misalignment = True
            warn("BML warning: Potential misalignment after writing \"{}\"".format(type(item).__name__))
        # Remember where pointers are written
        for member_offset in item.nonnull_pointer_member_offsets():
            ptr_offset = item_offset + member_offset
            if ptr_offset % IffChunk.ALIGNMENT != 0:
                raise Exception("BML error: Misaligned pointer in \"{}\" ({} + {})".format(type(item).__name__, item_offset, member_offset))
            self.pointer_offsets.append(ptr_offset)
        return item_offset
    
    def finish(self) -> bytearray:
        size_control_1 = 0x40
        size_control_2 = 0x80
        size_control_4 = 0xc0
        size_offset = 4
        header_size = IffHeader.type_size()
        # Write size of body into header
        pack_into(Numeric.endianness_prefix + "L", self.buf.buffer, size_offset, self.buf.offset - header_size)
        # Write pointer table header
        pof0_offset = self.buf.offset
        pof0_header = IffHeader(
            type_name=list(bytes("POF0", "ascii")),
            body_size=0xdeadbeef) # Body size is not known yet, we will write it here at the end
        pof0_header.serialize_into(self.buf)
        # Write pointer table
        self.pointer_offsets.sort()
        prev_pointer_offset = 0
        for abs_offset in self.pointer_offsets:
            rel_offset = (abs_offset - prev_pointer_offset) // 4
            prev_pointer_offset = abs_offset
            # Add pointer size control flag based on how big the pointer is
            if rel_offset < size_control_1:
                rel_offset |= size_control_1
                self.buf.pack(">B", rel_offset)
            elif rel_offset < (size_control_1 << 0x8):
                rel_offset |= size_control_2 << 0x8
                self.buf.pack(">H", rel_offset)
            elif rel_offset < (size_control_1 << 0x18):
                rel_offset |= size_control_4 << 0x18
                self.buf.pack(">L", rel_offset)
            else:
                raise Exception("BML error: Gap between pointers is too big ({})".format(abs_offset - prev_pointer_offset))
        # Write POF0 body size
        pack_into(Numeric.endianness_prefix + "L", self.buf.buffer, pof0_offset + size_offset, self.buf.offset - pof0_offset - header_size)
        return self.buf.buffer


def parse_pof0(filename: str, file_data: bytearray, prev_chunk_offset: int, prev_chunk_size: int, pof0_offset: int, pof0_size: int) -> list[int]:
    "POF0 chunk contains a pointer rewrite table for the preceding chunk"
    header_size = IffHeader.type_size()
    pointer_table = []
    read_cursor = pof0_offset + header_size
    pointer_offset = prev_chunk_offset + header_size
    
    while read_cursor < pof0_offset + header_size + pof0_size:
        pof_byte = file_data[read_cursor]
        pof_flags = pof_byte & (0x40 | 0x80)
        if pof_flags == 0:
            # Not a valid flag, but not necessarily malformed
            read_cursor += 1
            continue
        elif pof_flags == 0x40:
            # One byte offset
            relative_offset = file_data[read_cursor] & 0x3f
            read_cursor += 1
        elif pof_flags == 0x80:
            # Two byte offset
            relative_offset = (file_data[read_cursor] & 0x3f) << 0x8 | file_data[read_cursor + 1]
            read_cursor += 2
        elif pof_flags == (0x40 | 0x80):
            # Four byte offset
            relative_offset = (
                (file_data[read_cursor] & 0x3f) << 0x18 |
                file_data[read_cursor + 1] << 0x10 |
                file_data[read_cursor + 2] << 0x8 |
                file_data[read_cursor + 3])
            read_cursor += 4
        # Offsets are relative to the previous offset and divided by four (similar to REL)
        pointer_offset += relative_offset * 4
        (pointer, ) = unpack_from(Numeric.endianness_prefix + "L", file_data, offset=pointer_offset)
        pointer_table.append((pointer_offset, pointer))
    return pointer_table
