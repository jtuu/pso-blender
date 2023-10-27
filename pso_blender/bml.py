import os
from dataclasses import dataclass, field
from struct import unpack_from, pack_into
import bpy
from warnings import warn
from .serialization import Serializable, Numeric, FixedArray, ResizableBuffer
from . import prs, util, njcm, xvm, xj
from .nj import nj_to_blender_mesh


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


class CompressionType:
    NONE = 0
    PRS = ord("P")


@dataclass
class IffHeader(Serializable):
    type_name: FixedArray(U8, 4) = field(default_factory=list)
    body_size: U32 = 0


@dataclass
class BmlHeader(Serializable):
    unk1: U32 = 0
    file_count: U32 = 0
    compression_type: U8 = 0
    has_textures: U8 = 0
    unk2: U16 = 0
    unk3: U32 = 0
    unk4: U32 = 0
    unk5: U32 = 0
    unk6: U32 = 0
    unk7: U32 = 0
    unk8: U32 = 0
    unk9: U32 = 0
    unk10: U32 = 0
    unk11: U32 = 0
    unk12: U32 = 0
    unk13: U32 = 0
    unk14: U32 = 0
    unk15: U32 = 0


@dataclass
class FileDescription(Serializable):
    name: FixedArray(U8, 32) = field(default_factory=list)
    compressed_size: U32 = 0
    unk1: U32 = 0
    decompressed_size: U32 = 0
    textures_compressed_size: U32 = 0
    textures_decompressed_size: U32 = 0
    unk2: U32 = 0
    unk3: U32 = 0
    unk4: U32 = 0


def bytes_to_string(b: list[int]) -> str:
    return bytes(b).decode().rstrip("\0")


def align_up(n: int, to: int) -> int:
    return (n + to - 1) // to * to


@dataclass
class BmlItem:
    name: str
    model = None
    texture_list = None
    texture_archive = None
    animation = None
    pointer_table: list[int] = field(default_factory=list)


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
        (pointer, ) = unpack_from("<L", file_data, offset=pointer_offset)
        pointer_table.append((pointer_offset, pointer))
    return pointer_table


def parse_bml(path: str) -> list[BmlItem]:
    with open(path, "rb") as f:
        bml = bytearray(f.read())

    items = []
    (bml_header, _) = BmlHeader.deserialize_from(bml)
    file_description_offset = BmlHeader.type_size()
    file_alignment = 0x20 if bml_header.has_textures else 0x800
    file_offset = align_up(bml_header.file_count * 0x40, 0x800)
    chunk_header_size = IffHeader.type_size()

    for i in range(bml_header.file_count):
        # Read file description
        (file_description, file_description_offset) = FileDescription.deserialize_from(bml, offset=file_description_offset)
        item = BmlItem(name=bytes_to_string(file_description.name))
        items.append(item)

        # Get file from offset, decompress if needed
        file_data = bml[file_offset:file_offset + file_description.compressed_size]
        if bml_header.compression_type == CompressionType.PRS:
            file_data = prs.decompress(file_data)
        
        # Read iff chunks
        chunk_offset = 0
        prev_chunk_offset = None
        prev_chunk_size = None
        while chunk_offset < file_description.decompressed_size:
            (chunk_header, _) = IffHeader.deserialize_from(file_data, offset=chunk_offset)
            chunk_type = bytes_to_string(chunk_header.type_name)
            chunk_body = file_data[chunk_offset + chunk_header_size:chunk_offset + chunk_header_size + chunk_header.body_size]

            if chunk_type == "NJCM":
                item.model = chunk_body
            elif chunk_type == "NJTL":
                item.texture_list = chunk_body
            elif chunk_type == "NMDM":
                item.animation = chunk_body
            elif chunk_type == "POF0":
                if prev_chunk_offset is None:
                    # POF0 must always come after another chunk
                    warn("BML Warning: File '{}' contains a POF0 chunk at index zero".format(item.name))
                else:
                    item.pointer_table = parse_pof0(item.name, file_data, prev_chunk_offset, prev_chunk_size, chunk_offset, chunk_header.body_size)
            else:
                warn("BML Warning: File '{}' has an unknown IFF chunk type '{}'".format(item.name, chunk_type))

            prev_chunk_offset = chunk_offset
            prev_chunk_size = chunk_header.body_size
            chunk_offset += chunk_header.body_size + chunk_header_size

        file_offset += align_up(file_description.compressed_size, file_alignment)

        if file_description.textures_compressed_size > 0:
            # Texture archive is always PRS compressed
            item.texture_archive = prs.decompress(bml[file_offset:file_offset + file_description.textures_compressed_size])
            file_offset += align_up(file_description.textures_compressed_size, file_alignment)

    return items


def to_blender_mesh(bml_item: BmlItem) -> bpy.types.Object:
    if bml_item.name.endswith(".xj"):
        return xj.xj_to_blender_mesh(bml_item.name, bml_item.model, 0)
    if bml_item.name.endswith(".nj"):
        return nj_to_blender_mesh(bml_item.name, bml_item.model, 0)
    raise Exception("BML Error: Failed to identify model format. Expected filename to end with '.nj' or '.xj', but it was '{}'.".format(bml_item.name))


def read(path: str) -> bpy.types.Collection:
    bml = parse_bml(path)
    filename = os.path.basename(path)
    collection = bpy.data.collections.new(filename)

    for bml_item in bml:
        if bml_item.model:
            obj = to_blender_mesh(bml_item)
            if obj:
                collection.objects.link(obj)
        else:
            warn("BML Warning: Skipping unsupported file '{}'.".format(bml_item.name))

    return collection


class BmlChunk(util.AbstractFileArchive):
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
        item_offset = item.serialize_into(self.buf, BmlChunk.ALIGNMENT if ensure_aligned else None) - header_size
        if not self.warned_misalignment and self.buf.offset % BmlChunk.ALIGNMENT != 0:
            self.warned_misalignment = True
            warn("BML warning: Potential misalignment after writing \"{}\"".format(type(item).__name__))
        # Remember where pointers are written
        for member_offset in item.nonnull_pointer_member_offsets():
            ptr_offset = item_offset + member_offset
            if ptr_offset % BmlChunk.ALIGNMENT != 0:
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
        pack_into("<L", self.buf.buffer, size_offset, self.buf.offset - header_size)
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
        pack_into("<L", self.buf.buffer, pof0_offset + size_offset, self.buf.offset - pof0_offset - header_size)
        return self.buf.buffer


def write(bml_path: str, xvm_path: str, objects: list[bpy.types.Object]):
    bml_buf = ResizableBuffer(0)
    files_buf = ResizableBuffer(0)
    textures = xvm.assign_texture_identifiers(objects)

    # Write BML header at the beginning of the file
    bml_header = BmlHeader(
        file_count=len(objects),
        compression_type=CompressionType.NONE,
        has_textures=0
    )
    bml_header.serialize_into(bml_buf)

    file_alignment = 0x20 if bml_header.has_textures else 0x800

    for obj in objects:
        chunks_size_sum = 0
        # Pointers must be relative to current chunk's body
        njcm_chunk = BmlChunk("NJCM")

        # Root node must to be the first thing after the chunk header
        mesh_node = njcm.MeshTreeNode(
            eval_flags=xj.NinjaEvalFlag.UNIT_ANG | xj.NinjaEvalFlag.UNIT_SCL | xj.NinjaEvalFlag.BREAK,
            mesh=0xdeadbeef, # Will be rewritten at the end
            scale_x=1.0,
            scale_y=1.0,
            scale_z=1.0)
        mesh_pointer_offset = njcm_chunk.write(mesh_node) + IffHeader.type_size() + 4

        blender_mesh = obj.to_mesh()
        mesh = xj.make_mesh(njcm_chunk, obj, blender_mesh, textures)

        # Write mesh pointer into root node
        mesh_ptr = njcm_chunk.write(mesh)
        pack_into("<L", njcm_chunk.buf.buffer, mesh_pointer_offset, mesh_ptr)

        # Chunk (+POF0) is done
        files_sum_before = files_buf.offset
        njcm_chunk_buf = njcm_chunk.finish()
        files_buf.append(njcm_chunk_buf)
        chunks_size_sum += len(njcm_chunk_buf)
        compressed_size = chunks_size_sum

        # Add padding between files
        files_buf.grow_to(files_sum_before + align_up(compressed_size, file_alignment))
        files_buf.seek_to_end()

        # Write file descriptions after BML header
        file_desc = FileDescription(
            name=list(bytes(obj.name[0:28] + ".xj", "ascii")),
            compressed_size=compressed_size,
            decompressed_size=chunks_size_sum,
            textures_compressed_size=0,
            textures_decompressed_size=0)
        file_desc.serialize_into(bml_buf)
    
    # Add padding after file descriptions
    bml_buf.grow_to(align_up(bml_header.file_count * 0x40, 0x800))
    files_buf.seek_to_end()
    # Write files after descriptions
    bml_buf.append(files_buf.buffer)
    
    with open(bml_path, "wb") as f:
        f.write(bml_buf.buffer)

    if xvm_path and len(textures) > 0:
        xvm.write(xvm_path, list(textures.values()))
