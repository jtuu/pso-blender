from dataclasses import dataclass, field
from struct import pack_into
import bpy
from warnings import warn
from .serialization import Serializable, Numeric, FixedArray, ResizableBuffer
from . import prs, njcm, xvm, xj
from .nj import nj_to_blender_mesh
from .iff import IffChunk, IffHeader, parse_pof0
from .util import align_up, bytes_to_string


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


@dataclass
class BmlItem:
    name: str
    models: list[bytearray] = field(default_factory=list)
    texture_list = None
    texture_archive = None
    animation = None
    pointer_table: list[int] = field(default_factory=list)


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
                item.models.append(chunk_body)
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


def to_blender_mesh(bml_item: BmlItem) -> list[bpy.types.Collection]:
    collections = []
    if bml_item.name.endswith(".xj"):
        for model in bml_item.models:
            collections.append(xj.xj_to_blender_mesh(bml_item.name, model, 0))
    elif bml_item.name.endswith(".nj"):
        for model in bml_item.models:
            collections.append(nj_to_blender_mesh(bml_item.name, model, 0))
    else:
        raise Exception("BML Error: Failed to identify model format. Expected filename to end with '.nj' or '.xj', but it was '{}'.".format(bml_item.name))
    return collections


def read(path: str) -> list[bpy.types.Collection]:
    bml = parse_bml(path)
    collections = []
    for bml_item in bml:
        if len(bml_item.models) > 0:
            collections += to_blender_mesh(bml_item)
        else:
            warn("BML Warning: Skipping unsupported file '{}'.".format(bml_item.name))
    return collections


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
        njcm_chunk = IffChunk("NJCM")

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
