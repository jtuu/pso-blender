import os
from dataclasses import dataclass, field
import bpy
import bpy.types
from .serialization import Serializable, Numeric, ResizableBuffer
from . import util, dxt


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


class XvrFormat:
    A8R8G8B8 = 1
    R5G6B5 = 2
    A1R5G5B5 = 3
    A4R4G4B4 = 4
    P8 = 5
    DXT1 = 6
    DXT2 = 7
    DXT3 = 8
    DXT4 = 9
    DXT5 = 10
    A8R8G8B8 = 11
    R5G6B5 = 12
    A1R5G5B5 = 13
    A4R4G4B4 = 14
    YUY2 = 15
    V8U8 = 16
    A8 = 17
    X1R5G5B5 = 18
    X8R8G8B8 = 19


class XvrFlags:
    MIPMAPS = 1
    ALPHA = 2


@dataclass
class Xvr(Serializable):
    magic: list[U8] = util.magic_field("XVRT")
    body_size: U32 = 0
    flags: U32 = 0
    format: U32 = 0
    id: U32 = 0
    width: U16 = 0
    height: U16 = 0
    data_size: U32 = 0
    unk1: U32 = 0
    unk2: U32 = 0
    unk3: U32 = 0
    unk4: U32 = 0
    unk5: U32 = 0
    unk6: U32 = 0
    unk7: U32 = 0
    unk8: U32 = 0
    unk9: U32 = 0
    data: list[U8] = field(default_factory=list)


@dataclass
class Xvm(Serializable):
    magic: list[U8] = util.magic_field("XVMH")
    body_size: U32 = 0
    xvr_count: U32 = 0
    unk1: U32 = 0
    unk2: U32 = 0
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
    xvrs: list[Xvr] = field(default_factory=list)


@dataclass
class Texture:
    id: int
    generate_mipmaps: bool
    image: bpy.types.Image


def generate_mipmaps(image: bpy.types.Image, has_alpha: bool) -> list[bpy.types.Image]:
    mip_dim, _ = image.size
    levels = []
    level_idx = 0
    alpha_test = 0.75 # Value used by the game

    alpha_test_count = 0
    if has_alpha:
        for px_idx in range(0, len(image.pixels), 4):
            alpha = image.pixels[px_idx + 3]
            if alpha > alpha_test:
                alpha_test_count += 1
    orig_coverage = alpha_test_count / (mip_dim * mip_dim)

    while True:
        level_idx += 1
        mip_dim = mip_dim // 2
        if mip_dim <= 2:
            break
        level = image.copy()
        level.scale(mip_dim, mip_dim)
        if has_alpha:
            alpha_threshold = orig_coverage * alpha_test * mip_dim
            for px_idx in range(0, len(level.pixels), 4):
                alpha = level.pixels[px_idx + 3]
                if alpha > alpha_threshold:
                    level.pixels[px_idx + 3] = 1.0
        levels.append(level)
    return levels


def write(path: str, textures: list[Texture]):
    xvr_ext = ".xvr"
    (dirname, _) = os.path.split(path)
    xvrs = []
    magic_size = 4
    for tex in textures:
        (_, basename) = os.path.split(tex.image.filepath)
        cached_xvr_path = os.path.join(dirname, basename + xvr_ext)
        # First try to load cached textures from destination directory
        if os.path.isfile(cached_xvr_path):
            print("XVM Notice: Loading texture from cache '{}'".format(cached_xvr_path))
            with open(cached_xvr_path, "rb") as f:
                file_contents = f.read()
                (xvr, offset) = Xvr.deserialize_from(file_contents[magic_size:])
                xvr.data = file_contents[offset + magic_size:]
        else:
            # No cache
            img_width, img_height = tex.image.size
            has_alpha = tex.image.channels == 4
            flags = 0
            if tex.generate_mipmaps:
                flags |= XvrFlags.MIPMAPS
            if has_alpha:
                if tex.image.alpha_mode != "STRAIGHT":
                    raise Exception("XVR Error in Image '{}': Image has unsupported alpha mode '{}'".format(tex.image.filepath, tex.image.alpha_mode))
                flags |= XvrFlags.ALPHA
            xvr_format = XvrFormat.DXT1
            data = dxt.compress_image(list(tex.image.pixels), img_width, img_height, tex.image.channels, has_alpha)
            if tex.generate_mipmaps:
                mipmaps = generate_mipmaps(tex.image, has_alpha)
                for level in mipmaps:
                    level_width, level_height = level.size
                    data += dxt.compress_image(list(level.pixels), level_width, level_height, level.channels, has_alpha)
            xvr = Xvr(
                body_size=len(data) + Xvr.type_size() - magic_size,
                id=tex.id,
                flags=flags,
                format=xvr_format,
                width=img_width,
                height=img_height,
                data_size=len(data))
            # Write to cache
            buf = ResizableBuffer(0)
            xvr.serialize_into(buf)
            buf.append(data)
            xvr.data = data
            with open(cached_xvr_path, "wb") as f:
                print("XVM Notice: Saving texture to cache '{}'".format(cached_xvr_path))
                f.write(buf.buffer)
        xvrs.append(xvr)
    buf = ResizableBuffer(0)
    # I'll just explicitly write the lists because it's easier
    xvm = Xvm(
        body_size=Xvm.type_size() - 4,
        xvr_count=len(xvrs))
    xvm.serialize_into(buf)
    for xvr in xvrs:
        data = xvr.data
        xvr.data = []
        xvr.serialize_into(buf)
        buf.append(data)
        buf.seek_to_end()
    with open(path, "wb") as f:
        f.write(buf.buffer)
