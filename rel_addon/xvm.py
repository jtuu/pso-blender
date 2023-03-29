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


@dataclass
class Xvr(Serializable):
    magic: list[U8] = util.magic_field("XVRT")
    body_size: U32 = 0
    format1: U32 = 0
    format2: U32 = 0
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
    xvrs: list[Xvr] = field(default_factory=list)


@dataclass
class Texture:
    id: int
    image: bpy.types.Image


def write(path: str, textures: list[Texture]):
    xvrs = []
    for tex in textures:
        width, height = tex.image.size
        has_alpha = tex.image.channels == 4
        if has_alpha:
            if tex.image.alpha_mode != "STRAIGHT":
                raise Exception("XVR Error: Image has unsupported alpha mode \"{}\"".format(tex.image.alpha_mode))
            xvr_format = XvrFormat.DXT5
            data = dxt.dxt5_compress_image(list(tex.image.pixels), width, height)
        else:
            xvr_format = XvrFormat.DXT1
            data = dxt.dxt1_compress_image(list(tex.image.pixels), width, height)
        xvrs.append(Xvr(
            body_size=len(data) + Xvr.type_size() - 4,
            id=tex.id,
            format1=0,
            format2=xvr_format,
            width=width,
            height=height,
            data_size=len(data),
            data=data))
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
