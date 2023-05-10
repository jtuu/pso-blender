from dataclasses import dataclass, field
from struct import unpack_from
import bpy
from warnings import warn
from .serialization import Serializable, Numeric, FixedArray
from . import prs


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


def read(path: str) -> list[BmlItem]:
    with open(path, "rb") as f:
        bml = bytearray(f.read())

    items = []
    (bml_header, _) = BmlHeader.deserialize_from(bml)
    file_description_offset = 0x40
    file_alignment = 0x20 if bml_header.has_textures else 0x800
    file_offset = align_up(bml_header.file_count * 0x40, 0x800)

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
        iff_offset = 0
        while iff_offset < file_description.decompressed_size:
            iff_type = bytes(file_data[iff_offset:iff_offset + 4]).decode()
            (iff_size, ) = unpack_from("<L", file_data[iff_offset + 4:iff_offset + 8])
            iff_body = file_data[iff_offset + 8:iff_offset + 8 + iff_size]
            if iff_type == "NJCM":
                item.model = iff_body
            elif iff_type == "NJTL":
                item.texture_list = iff_body
            elif iff_type == "NMDM":
                item.animation = iff_body
            elif iff_type == "POF0":
                pass # Some kind of pointer relocation table, not sure if we need it when reading
            else:
                warn("BML Warning: File '{}' has an unknown IFF chunk type '{}'".format(item.name, iff_type))
            iff_offset += iff_size + 8

        file_offset += align_up(file_description.compressed_size, file_alignment)

        if file_description.textures_compressed_size > 0:
            # Texture archive is always PRS compressed
            item.texture_archive = prs.decompress(bml[file_offset:file_offset + file_description.textures_compressed_size])
            file_offset += align_up(file_description.textures_compressed_size, file_alignment)

    return items


def to_blender(bml_contents: dict[str, bytearray]) -> bpy.types.Collection:
    pass
